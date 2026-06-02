# 187 — C18.IMAGE-LAB.1 — HW decode image-lab build

Incorpora a stack de HW decode (provada em PoC no C18.RUNTIME, doc 186) numa **imagem-lab
privada**, derivada offline da última imagem validada em hardware (**C17.4.2**). **Isto NAO
e producao**, `final_image=false`; a validacao em hardware (C18.IMAGE-LAB.2) continua
**obrigatoria**. O usuario grava o cartao manualmente via Armbian Imager.

> Build recuperado apos falha de I/O do WSL: o WSL teve `EIO` recorrente em `/tmp/claude`
> durante a checagem ELF *pos-build*; a imagem ja estava escrita + SHA256 antes da falha.
> Apos reinicio, o SHA foi reconferido **identico** e a validacao offline+ELF reexecutou
> limpa. Status = `recovered_after_wsl_io_failure`. Nenhum rebuild foi feito.

## Imagem
```
image=Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1_minimal.img
sha256=a1103ba822d3bdba1b637a8e602677ee503369d85e8bc8b307d4863bf620e587
bytes=1971322880
artifact_private=true final_image=false not_for_production=true not_for_distribution=true
base_image_line=c17.4.2  c17_7_used_as_base=false
kernel_touched=false u_boot_touched=false dtb_touched=false c12_readonly_touched=false
ready_for_manual_card_flash=true  ready_for_c18_image_lab_2_clean_board_validation=true
```

## O que foi integrado (offline, rootless via debugfs — sem rebuild Armbian/kernel)
- **Stack HW decode** em `/opt/totem/hwdecode/{bin,lib}`: mpv custom + ffmpeg (libav*) com
  **V4L2 Request/Cedrus**, libplacebo (EGL/GBM/DRM/OpenGL), libass/freetype/fribidi.
  Fontes: FFmpeg `Kwiboo@2af4006` (v4l2request-2024-v2), mpv `Kwiboo@8670d2e`
  (v4l2request-test-20240808), libplacebo `@64c1954`. Stack reaproveitada do C18.RUNTIME
  (B1..B9), **provada em hardware** (B9: 867 transicoes loadfile, 0 falhas).
- **Wrapper** `/opt/totem/bin/totem-mpv-hwdecode`: define `LD_LIBRARY_PATH` para a stack e
  executa o mpv custom forcando **`--vo=gpu --gpu-context=drm --hwdec=v4l2request`**
  (apendado por ultimo, sobrepoe), preservando IPC, `--video-rotate`, etc.
- **Player aponta para o wrapper**: `kiosk.py` `DEFAULT_CONFIG["mpv_path"]` corrigido de
  `"mpv"` para o wrapper. `--video-rotate=270` segue vindo do config/wizard (homolog=270).
  IPC/playlist/duration/sync/C18.2/F10/NetworkManager **preservados**.
- **R4 updater-perms injetado** (`_make_world_traversable`): a C17.4.2 e anterior ao R4.
- **`totem` no grupo `video`**: ja provisionado na C17.4.2 (`video:x:44:totem`).
- Marcador `/etc/dadooh/c18-hwdecode-lab-1-image` (artifact_private/final_image=false/...).

## Validacao offline (passou; ELF resolvido)
`offline_validation_passed=true`, `fsck clean`, **`elf_missing_libs=[]`**: toda NEEDED lib
resolve — stack em `/opt/totem/hwdecode/lib`; sistema (`libEGL/libdrm/libgbm/libudev/libm/
libc/ld-linux`) presente no rootfs. `no_real_config` (sem `/data/config/config.json`),
sem secrets. Evidencia:
`docs/evidence/candidate-a/runs/20260531T145557Z-c18-image-lab-1-hwdecode-build/`.

## Nota de toolchain (desvio registrado)
A stack e GCC-13 + sysroot Bookworm-2.36 (`static-libstdc++` + shim `__isoc23` apenas na
libplacebo; libass sem harfbuzz) — **provada em hardware (B9)**. O build GCC-12 limpo/sem
shim preferido (chroot Bookworm GCC-12) fica **recomendado para a imagem de producao**.
Para esta imagem-lab, optou-se pela stack ja provada em hardware para minimizar variaveis
nao testadas antes da validacao obrigatoria em placa (C18.IMAGE-LAB.2).

## Sequencia
1. **C18.RUNTIME** provou a solucao do `media_load_failed` em PoC (decode HW + zero-copy +
   rotacao 270 + soak de transicao), doc 186.
2. **C18.IMAGE-LAB.1** (este) incorpora a stack numa imagem-lab privada (offline).
3. **Falta**: o usuario grava o cartao (Armbian Imager) e roda
   **C18.IMAGE-LAB.2 — clean-board validation**: hwdec engaja, zero-copy (sem autoconvert),
   visual no HDMI + rotacao 270, `media_load_failed`~0 em soak, 30 fps estavel.

## Guardrails
```
release_published=false remote_update_applied=false board_touched=false ssh_used=false
card_written=false poweroff=false c12_readonly_touched=false apt_upgrade=false pip_install=false
real_config_written=false media_or_cache_embedded=false secrets_published=false
limitation_C_accepted=false
```

## Correção → C18.IMAGE-LAB.1b (2026-06-01)
A imagem `1` mostrou-se **defeituosa no 1º boot em hardware** (início da C18.IMAGE-LAB.2):
(1) **player travado em "iniciando player"** = `kiosk.py` com `SyntaxError` na linha 3425 — o
deriver leu o arquivo via `cat`, que concatena o **banner do `debugfs`** (stderr) ao conteúdo,
poluindo o fim do arquivo; (2) **`panfrost -110`** (deferred-probe race) no boot, sem
`/dev/dri/renderD128` — GPU **sã** (re-bind `echo 1800000.gpu > .../panfrost/bind` sobe na
hora). Correções na **`1b`** (offline/rootless, deriva da C17.4.2, sem kernel/DTB/C12):
kiosk.py lido via **`debugfs dump`** + **`py_compile`** na validação; serviço oneshot
**`totem-panfrost-rebind`** (userspace, antes do player) que faz bind do panfrost se faltar
`renderD128`. Imagem **`...-c18-hwdecode-lab-1b_minimal.img`** sha256
`27ed29064a087091bdfc448560c93f217d032d9104a753b04c5ae7f65e701bf3`. Validação offline passou
(inclui `kiosk_py_compiles` + checks do panfrost). **Gravar a `1b`** (não a `1`). Evidência:
`docs/evidence/candidate-a/runs/20260602T011057Z-c18-image-lab-1b-hwdecode-rebuild/`.
Diagnóstico (Round A/B em hardware) na memória `c18-image-lab-2-firstboot-obs`.
