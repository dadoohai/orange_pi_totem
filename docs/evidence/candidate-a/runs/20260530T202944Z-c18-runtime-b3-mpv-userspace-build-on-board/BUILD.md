# Reproducible recipe — full mpv + V4L2-Request userspace stack (cross, no flash)

Extends B1's `BUILD.md`. Host = Ubuntu 24.04 (GCC-13 cross + meson/ninja in a venv).
Target = Orange Pi Zero 3, Bookworm (glibc 2.36), Cedrus. All into one `$PREFIX`
(=/tmp/ffbuild/prefix), dynamic, board-ABI-matched. `cross.ini` + `isoc23_compat.c`
are archived alongside this file.

## 0. Prereqs
- Bookworm arm64 sysroot `$SR` (B1 step 1, incl. relativized symlinks + 6.x UAPI).
- `python3 -m venv venv && venv/bin/pip install meson ninja`; put `venv/bin` on PATH.
- ffmpeg fork built **shared** and installed to `$PREFIX` (B1 configure + `--enable-shared
  --disable-static --disable-programs`, `make install`).

## 1. C++ cross toolchain (only needed for libplacebo's fast_float)
Host has no g++ cross; fetch + relocate it, and neutralize the glibc-2.39 ABI:
```
# amd64 packages (no foreign arch):
curl -O http://archive.ubuntu.com/.../g++-13-aarch64-linux-gnu_..._amd64.deb
curl -O http://archive.ubuntu.com/.../libstdc++-13-dev-arm64-cross_..._all.deb
dpkg-deb -x <each> /tmp/ffbuild/gxx
# complete the relocated prefix (headers/crt/libgcc/lto plugin) from the system gcc:
cp -an /usr/lib/gcc-cross/aarch64-linux-gnu/13/. /tmp/ffbuild/gxx/usr/lib/gcc-cross/aarch64-linux-gnu/13/
# cross as/ld so the relocated g++ doesn't grab the host assembler:
mkdir -p /tmp/ffbuild/gxx/xbin; for t in as ld ld.bfd ar ranlib strip nm objcopy objdump; do
  ln -sf /usr/bin/aarch64-linux-gnu-$t /tmp/ffbuild/gxx/xbin/$t; done
# wrapper that ALWAYS passes the flags meson's bare checks omit:
printf '#!/bin/sh\nexec /tmp/ffbuild/gxx/usr/bin/aarch64-linux-gnu-g++-13 -B/tmp/ffbuild/gxx/xbin --sysroot=%s -fno-use-linker-plugin "$@"\n' "$SR" > /tmp/ffbuild/gxx/gxx-wrap
chmod +x /tmp/ffbuild/gxx/gxx-wrap
# __isoc23_* shim (glibc>=2.38 symbols -> classic libc), built for the board:
aarch64-linux-gnu-gcc --sysroot=$SR -O2 -c isoc23_compat.c -o /tmp/ffbuild/isoc23_compat.o
```
`cross.ini` sets `cpp = gxx-wrap`; `cpp_link_args` carry `-static-libstdc++
-static-libgcc <isoc23_compat.o>` ⇒ C++ `.so`s NEED only libc/libm.
(Cleaner alternative: build the whole stack in a Bookworm GCC-12 chroot — no shim needed.)

## 2. Dependency chain (all `meson --cross-file cross.ini --prefix $PREFIX`, install)
- **fribidi 1.0.13**: `-Ddocs=false -Dtests=false -Dbin=false`
- **freetype 2.13.3**: `-Dharfbuzz/png/brotli/bzip2/zlib=disabled -Dtests=disabled`
- **libass 0.13.7** (autotools, NOT meson — newer libass forces harfbuzz/C++):
  `./configure --host=aarch64-linux-gnu --disable-harfbuzz --disable-fontconfig
  --disable-require-system-font-provider --disable-test CC=aarch64-linux-gnu-gcc
  CFLAGS=--sysroot=$SR ... ` (PKG_CONFIG_LIBDIR=$PREFIX/lib/pkgconfig). mpv only needs
  libass≥0.12.2 and version-guards newer features, so 0.13.7 links cleanly.
- **libplacebo 6.338.2** (`--recurse-submodules`): `-Ddemos=false -Dtests=false
  -Dbench=false -Dfuzz=false -Dxxhash=disabled -Dvulkan/opengl/d3d11/vk-proc-addr/
  gl-proc-addr/shaderc/glslang/lcms/libdovi/unwind=disabled`

## 3. mpv (`Kwiboo/mpv@v4l2request-test-20240808`)
```
meson setup build --cross-file cross.ini --prefix $PREFIX -Dv4l2request=enabled \
  -Dlibmpv=false -Dcplayer=true -Dgpl=true -Dlua=disabled -Djavascript=disabled \
  -Dvulkan=disabled -Dlibbluray=disabled -Duchardet=disabled -Dvapoursynth=disabled \
  -Dzimg=disabled -Dshaderc=disabled -Dspirv-cross=disabled
meson compile -C build   # -> build/mpv ; gate prints "v4l2request: enabled"
```
For PRODUCTION add the display path: build libplacebo+mpv with EGL/GBM/DRM
(`-Degl-drm`,`-Dgbm`) so `--hwdec=v4l2request --vo=gpu --gpu-context=drm` does
zero-copy drm_prime→panfrost (do NOT rely on `v4l2request-copy` — readback kills the win).

## 4. Run on board (no install)
```
tar czf bundle.tgz -C $PREFIX/.. (mpv + lib/*.so*); scp to /tmp; LD_LIBRARY_PATH=.../lib
mpv --no-config --vo=null --hwdec=v4l2request-copy --untimed --frames=N clip.h264
# verbose vd=v shows "Trying hardware decoding via h264-v4l2request-copy" + drm_prime.
```
