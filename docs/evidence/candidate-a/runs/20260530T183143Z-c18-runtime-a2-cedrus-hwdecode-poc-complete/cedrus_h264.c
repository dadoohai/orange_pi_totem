/* C18.RUNTIME F2 — minimal Cedrus stateless H.264 decode of ONE IDR frame.
 * Reads an Annex-B .h264 (single baseline IDR), parses SPS/PPS/slice, fills the
 * V4L2 stateless H.264 controls, drives the Request API, and dequeues an NV12
 * frame. Proves HW decode on /dev/video0 + measures time. Read-only on the board
 * (own fds; player doesn't use /dev/video0). Verbose per-step for debugging. */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <errno.h>
#include <unistd.h>
#include <poll.h>
#include <time.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <linux/videodev2.h>
#include <linux/media.h>

#ifndef V4L2_PIX_FMT_H264_SLICE
#define V4L2_PIX_FMT_H264_SLICE v4l2_fourcc('S','2','6','4')
#endif

/* ---- tiny bit reader (RBSP, skips emulation-prevention 0x03) ---- */
typedef struct { const unsigned char*d; int size, bytep, bitp; } BR;
static void br_init(BR*b,const unsigned char*d,int n){b->d=d;b->size=n;b->bytep=0;b->bitp=0;}
static int br_u1(BR*b){
    if(b->bytep>=b->size) return 0;
    /* emulation prevention: 00 00 03 -> drop 03 */
    if(b->bitp==0 && b->bytep>=2 && b->d[b->bytep]==3 && b->d[b->bytep-1]==0 && b->d[b->bytep-2]==0)
        b->bytep++;
    if(b->bytep>=b->size) return 0;
    int bit=(b->d[b->bytep]>>(7-b->bitp))&1;
    if(++b->bitp==8){b->bitp=0;b->bytep++;}
    return bit;
}
static unsigned br_u(BR*b,int n){unsigned v=0;while(n--)v=(v<<1)|br_u1(b);return v;}
static unsigned br_ue(BR*b){int z=0;while(!br_u1(b)&&z<32)z++;return ((1u<<z)-1)+br_u(b,z);}
static int br_se(BR*b){unsigned k=br_ue(b);return (k&1)?(int)((k+1)/2):-(int)(k/2);}

static double now_ms(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec*1000.0+t.tv_nsec/1e6;}
#define CK(call,msg) do{ if((call)<0){ printf("FAIL %s errno=%d(%s)\n",msg,errno,strerror(errno)); return 10; } }while(0)

int main(int argc,char**argv){
    const char*path = argc>1?argv[1]:"/tmp/dadooh_idr.h264";
    FILE*f=fopen(path,"rb"); if(!f){printf("open_stream_fail %s\n",path);return 2;}
    static unsigned char buf[1<<20]; int n=fread(buf,1,sizeof buf,f); fclose(f);
    printf("stream_bytes=%d\n",n);

    /* find NALs */
    int sps_o=-1,pps_o=-1,idr_o=-1, sps_e=0,pps_e=0,idr_e=0;
    int offs[64],types[64],nn=0;
    for(int i=0;i+4<n;i++){
        int sc=0; if(buf[i]==0&&buf[i+1]==0&&buf[i+2]==1)sc=3; else if(buf[i]==0&&buf[i+1]==0&&buf[i+2]==0&&buf[i+3]==1)sc=4;
        if(sc){offs[nn]=i+sc;types[nn]=buf[i+sc]&0x1f;nn++;i+=sc;}
    }
    for(int k=0;k<nn;k++){int end=(k+1<nn)?offs[k+1]- (buf[offs[k+1]-4]==0?4:3):n;
        if(types[k]==7){sps_o=offs[k];sps_e=end;} if(types[k]==8){pps_o=offs[k];pps_e=end;} if(types[k]==5){idr_o=offs[k];idr_e=end;}}
    printf("nals=%d sps@%d pps@%d idr@%d\n",nn,sps_o,pps_o,idr_o);
    if(sps_o<0||pps_o<0||idr_o<0){printf("missing_nal\n");return 3;}

    /* ---- parse SPS (baseline subset) ---- */
    BR b; br_init(&b,buf+sps_o+1,sps_e-sps_o-1); /* skip nal header byte */
    unsigned profile=br_u(&b,8); br_u(&b,8); unsigned level=br_u(&b,8);
    unsigned sps_id=br_ue(&b);
    if(profile==100||profile==110||profile==122||profile==244||profile==44||profile==83||profile==86||profile==118||profile==128){
        unsigned chroma=br_ue(&b); if(chroma==3)br_u1(&b); br_ue(&b); br_ue(&b); br_u1(&b);
        if(br_u1(&b)){ for(int i=0;i<8;i++){ if(br_u1(&b)){ /* scaling list skip (assume baseline; not hit) */ } } }
    }
    unsigned log2_max_frame_num = br_ue(&b)+4;
    unsigned poc_type=br_ue(&b);
    unsigned log2_max_poc_lsb=0;
    if(poc_type==0) log2_max_poc_lsb=br_ue(&b)+4;
    else if(poc_type==1){ br_u1(&b); br_se(&b); br_se(&b); unsigned ncyc=br_ue(&b); for(unsigned i=0;i<ncyc;i++)br_se(&b);}
    unsigned max_ref=br_ue(&b); br_u1(&b);
    unsigned w_mbs=br_ue(&b)+1; unsigned h_map=br_ue(&b)+1;
    unsigned frame_mbs_only=br_u1(&b); if(!frame_mbs_only)br_u1(&b);
    br_u1(&b); /* direct_8x8 */
    if(br_u1(&b)){ br_ue(&b);br_ue(&b);br_ue(&b);br_ue(&b);} /* crop */
    unsigned width=w_mbs*16, height=h_map*16*(frame_mbs_only?1:2);
    printf("SPS profile=%u level=%u %ux%u log2_max_frame_num=%u poc_type=%u log2_poc=%u max_ref=%u\n",
           profile,level,width,height,log2_max_frame_num,poc_type,log2_max_poc_lsb,max_ref);

    /* ---- parse PPS (subset) ---- */
    BR p; br_init(&p,buf+pps_o+1,pps_e-pps_o-1);
    unsigned pps_id=br_ue(&p); unsigned pps_sps=br_ue(&p);
    unsigned cabac=br_u1(&p); unsigned bottom=br_u1(&p);
    unsigned nslicegroups=br_ue(&p)+1; (void)nslicegroups;
    unsigned nref0=br_ue(&p)+1, nref1=br_ue(&p)+1;
    unsigned wpred=br_u1(&p); unsigned wbipred=br_u(&p,2);
    int pic_init_qp=br_se(&p)+26; int pic_init_qs=br_se(&p)+26; int chroma_qp=br_se(&p);
    unsigned deblock=br_u1(&p), constr_intra=br_u1(&p), redundant=br_u1(&p);
    printf("PPS cabac=%u nref0=%u nref1=%u wpred=%u init_qp=%d deblock_ctrl=%u constr_intra=%u\n",
           cabac,nref0,nref1,wpred,pic_init_qp,deblock,constr_intra);

    /* ---- parse IDR slice header (baseline I-slice, full, for header_bit_size) ---- */
    BR s; br_init(&s,buf+idr_o+1,idr_e-idr_o-1);
    unsigned nal_ref_idc=(buf[idr_o]>>5)&3;
    unsigned first_mb=br_ue(&s); unsigned slice_type=br_ue(&s); unsigned spps=br_ue(&s); (void)spps;
    unsigned frame_num=br_u(&s,log2_max_frame_num);
    unsigned idr_pic_id=br_ue(&s);
    unsigned poc_lsb=0; if(poc_type==0)poc_lsb=br_u(&s,log2_max_poc_lsb);
    if(redundant) br_ue(&s);
    /* I-slice: no ref_idx override / ref_pic_list_mod / pred_weight */
    unsigned drpm_start = s.bytep*8 + s.bitp;
    if(nal_ref_idc){ br_u1(&s); br_u1(&s); } /* IDR dec_ref_pic_marking: 2 flags */
    unsigned drpm_bits = (s.bytep*8 + s.bitp) - drpm_start;
    int slice_qp_delta=br_se(&s);
    int disable_dbf=0, alpha=0, beta=0;
    if(deblock){ disable_dbf=br_ue(&s); if(disable_dbf!=1){ alpha=br_se(&s); beta=br_se(&s); } }
    unsigned header_bits = s.bytep*8 + s.bitp;       /* slice_header() bits, in RBSP after nal hdr */
    unsigned hdr_bit_size = header_bits + 8;          /* + 1-byte nal header (buffer starts at nal hdr) */
    printf("SLICE first_mb=%u type=%u frame_num=%u idr=%u qp_delta=%d disable_dbf=%d header_bits=%u(+nal=%u) drpm_bits=%u nal_ref_idc=%u\n",
           first_mb,slice_type,frame_num,idr_pic_id,slice_qp_delta,disable_dbf,header_bits,hdr_bit_size,drpm_bits,nal_ref_idc);

    /* ============ V4L2 stateless setup ============ */
    int vfd=open("/dev/video0",O_RDWR|O_NONBLOCK); if(vfd<0){printf("open_video errno=%d\n",errno);return 4;}
    int mfd=open("/dev/media0",O_RDWR|O_NONBLOCK); if(mfd<0){printf("open_media errno=%d\n",errno);return 4;}

    /* decode mode + start code controls */
    struct v4l2_ext_control c0[2]; memset(c0,0,sizeof c0);
    c0[0].id=V4L2_CID_STATELESS_H264_DECODE_MODE; c0[0].value=V4L2_STATELESS_H264_DECODE_MODE_SLICE_BASED;
    c0[1].id=V4L2_CID_STATELESS_H264_START_CODE;  c0[1].value=V4L2_STATELESS_H264_START_CODE_NONE;
    struct v4l2_ext_controls ec0; memset(&ec0,0,sizeof ec0); ec0.count=2; ec0.controls=c0;
    CK(ioctl(vfd,VIDIOC_S_EXT_CTRLS,&ec0),"set decode_mode/start_code");

    struct v4l2_format of; memset(&of,0,sizeof of);
    of.type=V4L2_BUF_TYPE_VIDEO_OUTPUT; of.fmt.pix.pixelformat=V4L2_PIX_FMT_H264_SLICE;
    of.fmt.pix.width=width; of.fmt.pix.height=height; of.fmt.pix.sizeimage=1<<20;
    CK(ioctl(vfd,VIDIOC_S_FMT,&of),"S_FMT OUTPUT");
    struct v4l2_format cf; memset(&cf,0,sizeof cf); cf.type=V4L2_BUF_TYPE_VIDEO_CAPTURE;
    cf.fmt.pix.width=width; cf.fmt.pix.height=height;
    CK(ioctl(vfd,VIDIOC_S_FMT,&cf),"S_FMT CAPTURE");
    { char fc[5]={cf.fmt.pix.pixelformat,cf.fmt.pix.pixelformat>>8,cf.fmt.pix.pixelformat>>16,cf.fmt.pix.pixelformat>>24,0};
      printf("CAPTURE negotiated %s %ux%u sizeimage=%u\n",fc,cf.fmt.pix.width,cf.fmt.pix.height,cf.fmt.pix.sizeimage); }

    /* request buffers (MMAP) */
    struct v4l2_requestbuffers rb;
    memset(&rb,0,sizeof rb); rb.count=1; rb.type=V4L2_BUF_TYPE_VIDEO_OUTPUT; rb.memory=V4L2_MEMORY_MMAP;
    CK(ioctl(vfd,VIDIOC_REQBUFS,&rb),"REQBUFS OUTPUT");
    memset(&rb,0,sizeof rb); rb.count=2; rb.type=V4L2_BUF_TYPE_VIDEO_CAPTURE; rb.memory=V4L2_MEMORY_MMAP;
    CK(ioctl(vfd,VIDIOC_REQBUFS,&rb),"REQBUFS CAPTURE");

    /* mmap OUTPUT buf0 */
    struct v4l2_buffer ob; memset(&ob,0,sizeof ob); ob.type=V4L2_BUF_TYPE_VIDEO_OUTPUT; ob.memory=V4L2_MEMORY_MMAP; ob.index=0;
    CK(ioctl(vfd,VIDIOC_QUERYBUF,&ob),"QUERYBUF OUTPUT");
    void*omem=mmap(0,ob.length,PROT_READ|PROT_WRITE,MAP_SHARED,vfd,ob.m.offset);
    if(omem==MAP_FAILED){printf("mmap_out_fail\n");return 5;}
    /* copy whole frame bitstream (annex-b: SPS..IDR) into output buffer */
    int slice_len=idr_e-idr_o; if(slice_len>(int)ob.length)slice_len=ob.length; /* slice NAL, no start code */
    memcpy(omem,buf+idr_o,slice_len); ob.bytesused=slice_len;

    /* mmap CAPTURE bufs */
    void*cmem[2]; struct v4l2_buffer cb[2];
    for(int i=0;i<2;i++){ memset(&cb[i],0,sizeof cb[i]); cb[i].type=V4L2_BUF_TYPE_VIDEO_CAPTURE; cb[i].memory=V4L2_MEMORY_MMAP; cb[i].index=i;
        CK(ioctl(vfd,VIDIOC_QUERYBUF,&cb[i]),"QUERYBUF CAPTURE");
        cmem[i]=mmap(0,cb[i].length,PROT_READ|PROT_WRITE,MAP_SHARED,vfd,cb[i].m.offset);
        if(cmem[i]==MAP_FAILED){printf("mmap_cap_fail\n");return 5;} }

    /* fill H.264 controls (constant across all frames in this PoC) */
    struct v4l2_ctrl_h264_sps S; memset(&S,0,sizeof S);
    S.profile_idc=profile; S.level_idc=level; S.seq_parameter_set_id=sps_id;
    S.log2_max_frame_num_minus4=log2_max_frame_num-4;
    S.pic_order_cnt_type=poc_type;
    S.log2_max_pic_order_cnt_lsb_minus4= poc_type==0?(log2_max_poc_lsb-4):0;
    S.max_num_ref_frames=max_ref;
    S.pic_width_in_mbs_minus1=w_mbs-1; S.pic_height_in_map_units_minus1=h_map-1;
    if(frame_mbs_only)S.flags|=V4L2_H264_SPS_FLAG_FRAME_MBS_ONLY;

    struct v4l2_ctrl_h264_pps P; memset(&P,0,sizeof P);
    P.pic_parameter_set_id=pps_id; P.seq_parameter_set_id=pps_sps;
    P.num_ref_idx_l0_default_active_minus1=nref0-1; P.num_ref_idx_l1_default_active_minus1=nref1-1;
    P.pic_init_qp_minus26=pic_init_qp-26; P.pic_init_qs_minus26=pic_init_qs-26;
    P.chroma_qp_index_offset=chroma_qp;
    if(cabac)P.flags|=V4L2_H264_PPS_FLAG_ENTROPY_CODING_MODE;
    if(deblock)P.flags|=V4L2_H264_PPS_FLAG_DEBLOCKING_FILTER_CONTROL_PRESENT;
    if(constr_intra)P.flags|=V4L2_H264_PPS_FLAG_CONSTRAINED_INTRA_PRED;
    if(wpred)P.flags|=V4L2_H264_PPS_FLAG_WEIGHTED_PRED;
    P.weighted_bipred_idc=wbipred;

    struct v4l2_ctrl_h264_scaling_matrix SM; memset(&SM,0,sizeof SM); /* flat */
    struct v4l2_ctrl_h264_decode_params DP; memset(&DP,0,sizeof DP);
    DP.frame_num=frame_num; DP.idr_pic_id=idr_pic_id; DP.nal_ref_idc=nal_ref_idc;
    DP.top_field_order_cnt=0; DP.bottom_field_order_cnt=0; DP.pic_order_cnt_lsb=poc_lsb;
    DP.dec_ref_pic_marking_bit_size=drpm_bits; DP.pic_order_cnt_bit_size=0;
    DP.flags=V4L2_H264_DECODE_PARAM_FLAG_IDR_PIC;
    /* dpb empty for IDR */

    struct v4l2_ctrl_h264_slice_params SL; memset(&SL,0,sizeof SL);
    SL.header_bit_size=hdr_bit_size;
    SL.first_mb_in_slice=first_mb; SL.slice_type=slice_type%5;
    SL.slice_qp_delta=slice_qp_delta; SL.cabac_init_idc=0;
    SL.disable_deblocking_filter_idc=disable_dbf;
    SL.slice_alpha_c0_offset_div2=alpha; SL.slice_beta_offset_div2=beta;
    SL.num_ref_idx_l0_active_minus1=0; SL.num_ref_idx_l1_active_minus1=0;
    /* ref lists empty (I slice) */

    struct v4l2_ctrl_h264_pred_weights PW; memset(&PW,0,sizeof PW);

    struct v4l2_ext_control ctl[6]; memset(ctl,0,sizeof ctl);
    ctl[0].id=V4L2_CID_STATELESS_H264_SPS;            ctl[0].ptr=&S;  ctl[0].size=sizeof S;
    ctl[1].id=V4L2_CID_STATELESS_H264_PPS;            ctl[1].ptr=&P;  ctl[1].size=sizeof P;
    ctl[2].id=V4L2_CID_STATELESS_H264_SCALING_MATRIX; ctl[2].ptr=&SM; ctl[2].size=sizeof SM;
    ctl[3].id=V4L2_CID_STATELESS_H264_DECODE_PARAMS;  ctl[3].ptr=&DP; ctl[3].size=sizeof DP;
    ctl[4].id=V4L2_CID_STATELESS_H264_SLICE_PARAMS;   ctl[4].ptr=&SL; ctl[4].size=sizeof SL;
    ctl[5].id=V4L2_CID_STATELESS_H264_PRED_WEIGHTS;   ctl[5].ptr=&PW; ctl[5].size=sizeof PW;
    struct v4l2_ext_controls ecr; memset(&ecr,0,sizeof ecr);
    ecr.which=V4L2_CTRL_WHICH_REQUEST_VAL; ecr.count=6; ecr.controls=ctl;

    /* STREAMON both */
    int t=V4L2_BUF_TYPE_VIDEO_OUTPUT;  CK(ioctl(vfd,VIDIOC_STREAMON,&t),"STREAMON OUTPUT");
    t=V4L2_BUF_TYPE_VIDEO_CAPTURE;     CK(ioctl(vfd,VIDIOC_STREAMON,&t),"STREAMON CAPTURE");

    /* queue both CAPTURE buffers up front */
    for(int i=0;i<2;i++){ CK(ioctl(vfd,VIDIOC_QBUF,&cb[i]),"QBUF CAPTURE"); }

    /* ===== measured decode loop: same IDR re-fed N times (HW cost per frame + CPU) ===== */
    int loops = argc>2?atoi(argv[2]):1; if(loops<1)loops=1;
    double dt_sum=0,dt_max=0,y_first=0; unsigned by_first=0,fl_first=0; int ok=0;
    struct rusage ru0; getrusage(RUSAGE_SELF,&ru0);
    double wall0=now_ms();
    for(int it=0; it<loops; it++){
        int req_fd=-1; if(ioctl(mfd,MEDIA_IOC_REQUEST_ALLOC,&req_fd)<0){printf("FAIL alloc it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 10;}
        ecr.request_fd=req_fd;
        if(ioctl(vfd,VIDIOC_S_EXT_CTRLS,&ecr)<0){printf("FAIL setctrls it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 10;}
        ob.flags=V4L2_BUF_FLAG_REQUEST_FD; ob.request_fd=req_fd; ob.bytesused=slice_len;
        if(ioctl(vfd,VIDIOC_QBUF,&ob)<0){printf("FAIL qbuf_out it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 10;}
        double t0=now_ms();
        if(ioctl(req_fd,MEDIA_REQUEST_IOC_QUEUE,0)<0){printf("FAIL queue it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 10;}
        struct pollfd pf={.fd=vfd,.events=POLLIN|POLLOUT}; poll(&pf,1,2000);
        struct v4l2_buffer dq; memset(&dq,0,sizeof dq); dq.type=V4L2_BUF_TYPE_VIDEO_CAPTURE; dq.memory=V4L2_MEMORY_MMAP;
        if(ioctl(vfd,VIDIOC_DQBUF,&dq)<0){printf("FAIL dqbuf_cap it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 11;}
        double dt=now_ms()-t0; dt_sum+=dt; if(dt>dt_max)dt_max=dt;
        /* dequeue OUTPUT so we can reuse it (poll-wait, never busy-spin -> keeps CPU honest) */
        struct v4l2_buffer dqo; memset(&dqo,0,sizeof dqo); dqo.type=V4L2_BUF_TYPE_VIDEO_OUTPUT; dqo.memory=V4L2_MEMORY_MMAP;
        if(ioctl(vfd,VIDIOC_DQBUF,&dqo)<0){
            if(errno==EAGAIN){ struct pollfd po={.fd=vfd,.events=POLLOUT}; poll(&po,1,2000);
                memset(&dqo,0,sizeof dqo); dqo.type=V4L2_BUF_TYPE_VIDEO_OUTPUT; dqo.memory=V4L2_MEMORY_MMAP;
                if(ioctl(vfd,VIDIOC_DQBUF,&dqo)<0){printf("FAIL dqbuf_out it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 11;} }
            else {printf("FAIL dqbuf_out it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 11;} }
        if(it==0){ unsigned char*Y=cmem[dq.index]; unsigned long sum=0; for(unsigned i=0;i<dq.bytesused&&i<width*height;i++)sum+=Y[i];
            y_first=(double)sum/(width*height); by_first=dq.bytesused; fl_first=dq.flags; }
        /* requeue the CAPTURE buffer just consumed */
        struct v4l2_buffer rqc; memset(&rqc,0,sizeof rqc); rqc.type=V4L2_BUF_TYPE_VIDEO_CAPTURE; rqc.memory=V4L2_MEMORY_MMAP; rqc.index=dq.index;
        if(ioctl(vfd,VIDIOC_QBUF,&rqc)<0){printf("FAIL requeue_cap it=%d errno=%d(%s)\n",it,errno,strerror(errno));return 11;}
        close(req_fd);
        ok++;
    }
    double wall=now_ms()-wall0;
    struct rusage ru1; getrusage(RUSAGE_SELF,&ru1);
    double ut=(ru1.ru_utime.tv_sec-ru0.ru_utime.tv_sec)*1000.0+(ru1.ru_utime.tv_usec-ru0.ru_utime.tv_usec)/1000.0;
    double st=(ru1.ru_stime.tv_sec-ru0.ru_stime.tv_sec)*1000.0+(ru1.ru_stime.tv_usec-ru0.ru_stime.tv_usec)/1000.0;
    printf("DECODED ok frames=%d %ux%u bytesused=%u flags=0x%x Y_mean=%.1f\n",ok,width,height,by_first,fl_first,y_first);
    printf("TIMING wall_ms=%.1f avg_decode_ms=%.3f max_decode_ms=%.3f fps=%.1f\n",wall,dt_sum/ok,dt_max,ok*1000.0/wall);
    printf("CPU user_ms=%.1f sys_ms=%.1f cpu_per_frame_ms=%.4f cpu_pct_of_1core=%.1f\n",ut,st,(ut+st)/ok,(ut+st)*100.0/wall);
    printf("HWDECODE_PROOF=PASS\n");
    return 0;
}
