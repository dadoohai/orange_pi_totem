# Reproducible recipe — cross-build ffmpeg w/ V4L2-Request hwaccel for Orange Pi Zero 3 (H618)

Host: x86_64 Linux with `aarch64-linux-gnu-gcc`, `make`, `pkg-config`, `git`, `curl`,
`dpkg-deb`. No sudo, no apt-on-board, no qemu required. Target board: Armbian/Debian
**Bookworm** (glibc 2.36), kernel 6.12.58-sunxi64, Cedrus stateless V4L2 driver.

## 1. Bookworm arm64 sysroot (dynamic link → matches board exactly)
Download these Bookworm arm64 `.deb`s from `http://ftp.debian.org/debian/pool/main/`
and extract with `dpkg-deb -x <deb> $SYSROOT`:
- `g/glibc/libc6_2.36-9+deb12u14_arm64.deb`, `g/glibc/libc6-dev_2.36-9+deb12u14_arm64.deb`
- `libd/libdrm/libdrm2_2.4.114-1+b1_arm64.deb`, `libd/libdrm/libdrm-dev_2.4.114-1+b1_arm64.deb`
- `s/systemd/libudev1_252.39-1~deb12u2_arm64.deb`, `s/systemd/libudev-dev_252.39-1~deb12u2_arm64.deb`

Then add kernel UAPI headers (libc6-dev does NOT ship `linux/*`): copy `linux/ asm/
asm-generic/` from a **≥6.0** `linux-libc-dev` (the V4L2 stateless H.264 controls +
Request API uAPI; we used a 6.8 set) into `$SYSROOT/usr/include/`.

CRITICAL FIX — Debian `.so` dev symlinks are absolute (`/lib/.../libm.so.6`) and
dangle when the sysroot isn't at `/`, so `-lm`/`-ldrm`/`-ludev` link tests fail
(symptom: ffmpeg `libm.h: static declaration of 'cbrt' follows non-static`).
Relativize every absolute symlink in the sysroot:
```
cd $SYSROOT
find . -type l -lname '/*' | while read -r l; do
  t=$(readlink "$l"); d=$(dirname "$l")
  ln -sf "$(realpath -m --relative-to="$d" ".${t}")" "$l"
done
```

## 2. Source
```
git clone --depth 1 -b v4l2request-2024-v2 https://github.com/Kwiboo/FFmpeg
```
(HEAD 2af4006 = "avcodec: Add V4L2 Request API hevc hwaccel". Upstream FFmpeg has
NOT merged this hwaccel as of 2025 — the Kwiboo fork / 2024 patch series is required.)

## 3. Configure (minimal: h264 decode + v4l2request only)
```
export PKG_CONFIG_SYSROOT_DIR=$SYSROOT
export PKG_CONFIG_LIBDIR=$SYSROOT/usr/lib/aarch64-linux-gnu/pkgconfig:$SYSROOT/usr/share/pkgconfig
./configure \
  --enable-cross-compile --cross-prefix=aarch64-linux-gnu- --arch=aarch64 --cpu=cortex-a53 \
  --target-os=linux --sysroot=$SYSROOT --pkg-config=pkg-config \
  --enable-v4l2-request --enable-libdrm --enable-libudev \
  --disable-everything --disable-autodetect --disable-doc --disable-network --disable-debug \
  --disable-ffprobe --disable-ffplay \
  --enable-decoder=h264 --enable-hwaccel=h264_v4l2request \
  --enable-encoder=wrapped_avframe,rawvideo \
  --enable-parser=h264 --enable-demuxer=h264,mpegts,mov --enable-protocol=file \
  --enable-muxer=null,rawvideo,framemd5 --enable-filter=null,hwdownload,format \
  --enable-bsf=h264_mp4toannexb \
  --extra-cflags="-I$SYSROOT/usr/include" \
  --extra-ldflags="-L$SYSROOT/usr/lib/aarch64-linux-gnu -Wl,-rpath-link,$SYSROOT/usr/lib/aarch64-linux-gnu -Wl,-rpath-link,$SYSROOT/lib/aarch64-linux-gnu"
make -j$(nproc) ffmpeg && aarch64-linux-gnu-strip ffmpeg
```
Result: ~3 MB dynamic binary; `readelf -d` NEEDED = libm/libdrm/libudev/libc + ld-linux
(all present on the Bookworm board). For production, add back the codecs/filters/muxers
the player needs (this minimal set is decode-validation only).

## 4. Validate on board (no install)
```
scp ffmpeg root@<board>:/tmp/dadooh_ffmpeg
# HW decode benchmark (drm_prime keeps frames on the VPU, no CPU copyback):
/tmp/dadooh_ffmpeg -benchmark -hwaccel v4l2request -init_hw_device v4l2request:/dev/media0 \
  -hwaccel_output_format drm_prime -i clip.h264 -map 0:v -f null -
# expect: "Using V4L2 media driver cedrus", frame=<all>, bench utime ~24x lower than SW.
```

## 5. Productization (image round, gated)
- mpv linked against this fork (`--hwdec=v4l2request`/`drm`); mpv PR #14511 = v4l2request hwdevice.
- `totem` user in `video` group.
- Package fork's `libav*` + ffmpeg + mpv into the candidate image; validate on TEST board.
