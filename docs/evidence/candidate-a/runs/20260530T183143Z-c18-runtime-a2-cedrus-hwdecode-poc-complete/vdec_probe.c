/* C18.RUNTIME F1/F2 — compiled V4L2 stateless probe + format negotiation.
 * QUERYCAP, ENUM_FMT, then S_FMT OUTPUT=H264_SLICE / CAPTURE=NV12 (no streaming).
 * Proves cross-toolchain->board pipeline AND that stateless decode setup negotiates. */
#include <stdio.h>
#include <fcntl.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/ioctl.h>
#include <linux/videodev2.h>
#ifndef V4L2_PIX_FMT_H264_SLICE
#define V4L2_PIX_FMT_H264_SLICE v4l2_fourcc('S','2','6','4')
#endif
static void fc(char*b,unsigned f){b[0]=f;b[1]=f>>8;b[2]=f>>16;b[3]=f>>24;b[4]=0;}

int main(void){
    int fd=open("/dev/video0",O_RDWR|O_NONBLOCK);
    if(fd<0){printf("open errno=%d\n",errno);return 2;}
    struct v4l2_capability cap; memset(&cap,0,sizeof cap);
    if(!ioctl(fd,VIDIOC_QUERYCAP,&cap))
        printf("QUERYCAP driver=%s card=%s device_caps=0x%08x\n",cap.driver,cap.card,cap.device_caps);

    /* negotiate OUTPUT (coded input) = H264 slice */
    struct v4l2_format ofmt; memset(&ofmt,0,sizeof ofmt);
    ofmt.type=V4L2_BUF_TYPE_VIDEO_OUTPUT;
    ofmt.fmt.pix.pixelformat=V4L2_PIX_FMT_H264_SLICE;
    ofmt.fmt.pix.width=1920; ofmt.fmt.pix.height=1088;
    ofmt.fmt.pix.sizeimage=1024*1024;
    char b[8];
    if(!ioctl(fd,VIDIOC_S_FMT,&ofmt)){ fc(b,ofmt.fmt.pix.pixelformat);
        printf("S_FMT OUTPUT ok pixfmt=%s %ux%u sizeimage=%u\n",b,ofmt.fmt.pix.width,ofmt.fmt.pix.height,ofmt.fmt.pix.sizeimage);
    } else printf("S_FMT OUTPUT failed errno=%d\n",errno);

    /* negotiate CAPTURE (decoded output) */
    struct v4l2_format cfmt; memset(&cfmt,0,sizeof cfmt);
    cfmt.type=V4L2_BUF_TYPE_VIDEO_CAPTURE;
    if(!ioctl(fd,VIDIOC_G_FMT,&cfmt)){ fc(b,cfmt.fmt.pix.pixelformat);
        printf("G_FMT CAPTURE pixfmt=%s %ux%u\n",b,cfmt.fmt.pix.width,cfmt.fmt.pix.height);
    } else printf("G_FMT CAPTURE failed errno=%d\n",errno);

    /* stateless decode-mode control present? (V4L2_CID_STATELESS_H264_DECODE_MODE) */
#ifdef V4L2_CID_STATELESS_H264_DECODE_MODE
    struct v4l2_query_ext_ctrl q; memset(&q,0,sizeof q);
    q.id=V4L2_CID_STATELESS_H264_DECODE_MODE;
    if(!ioctl(fd,VIDIOC_QUERY_EXT_CTRL,&q))
        printf("H264_DECODE_MODE ctrl present: name=%s min=%lld max=%lld\n",q.name,(long long)q.minimum,(long long)q.maximum);
    else printf("H264_DECODE_MODE query failed errno=%d\n",errno);
#else
    printf("H264_DECODE_MODE: not in headers\n");
#endif
    close(fd);
    printf("PROBE2_DONE\n");
    return 0;
}
