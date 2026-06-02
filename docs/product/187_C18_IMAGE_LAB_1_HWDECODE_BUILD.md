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

## → C18.IMAGE-LAB.1c (2026-06-02) — 3º fix + VALIDADO em hardware
A `1b` corrigiu kiosk.py + panfrost, mas o player ainda travava em "iniciando player".
**3ª causa:** o player passa `--no-osc` (válido no mpv 0.35.1), mas o mpv custom é
`-Dlua=disabled` → a opção `--osc` (script Lua) **não existe** → mpv **aborta antes de criar
o socket IPC** → timeout de 10s → loop. **Fix (`1c`):** o wrapper `totem-mpv-hwdecode` agora
**filtra `--no-osc`** antes do exec. **Validação AO VIVO** (placa 192.168.18.131, fix aplicado
in-place): `hwdec-current=v4l2request`, tocando H.264 real, **`media_load_failed=0`**, mpv
estável (1 pid), transições limpas, CPU ~13,6%. A raiz `/` é **ext4 rw** e `overlayroot=tmpfs`
**não está ativo** → o fix in-place **persiste** → a placa **funciona e sobrevive a reboot,
sem regravação urgente**. Imagem canônica limpa **`...-c18-hwdecode-lab-1c_minimal.img`**
sha256 `766a3eb2071e599df5561918c8308f9559fb8d24ee65168839a8cf6a75d85c29` (as defeituosas
`1` e `1b` foram removidas de `output/images`). Os **3 defeitos eram bugs do meu deriver**; a
stack de HW decode (B1..B9) sempre esteve correta. **A solução C18 de HW decode está PROVADA
numa imagem em hardware.** Evidência:
`docs/evidence/candidate-a/runs/20260602T022925Z-c18-image-lab-1c-noosc-fix-and-hw-validation/`.
Secundário (não-bloqueante): boot ~2min + tela preta antes do wizard (otimizar depois);
terminal-no-boot **não** reapareceu na 1b/1c.

## → C18.IMAGE-LAB.1d (2026-06-02) — fallback de estabilidade + validação inicial
A `1c` provou o fix do bug original (`media_load_failed` por saturação de CPU), mas a
validação ao vivo seguinte isolou dois problemas que contaminavam o diagnóstico de tela
preta/ordem:

- o caminho zero-copy `v4l2request`/`drm_prime` gerou `panfrost js fault` em algumas mídias
  portrait;
- o cartão usado na `1c` apresentou erros `mmc`/I-O e depois falhou no `h2testw`.

**Fix (`1d`):** o wrapper `totem-mpv-hwdecode` passa a forçar
`--hwdec=v4l2request-copy`, mantendo `--vo=gpu --gpu-context=drm`, IPC, rotação e filtro de
`--no-osc`. A imagem também adiciona o drop-in
`/etc/systemd/system/kiosky-player.service.d/30-c18-stability.conf`, movendo o trace
diagnóstico C17.4 para `/run/totem/c17-4-firstboot` via
`TOTEM_C17_4_FIRSTBOOT_TRACE_DIR`, para não bloquear o startup em `/data` se houver I/O
lento.

Imagem **`...-c18-hwdecode-lab-1d_minimal.img`** sha256
`82a1717f56be8b6aeb8a6b55f43ab5b694d05ce3c751c47dee524c1aed386ca0`.
Validação offline passou (`OFFLINE_VALIDATION_PASSED=True`, fsck clean). Em cartão novo
aprovado pelo usuário, o boot ficou sensivelmente mais rápido e a validação inicial ao vivo
mostrou: config real aplicada pelo writer guardado a partir do seed local com `mpv_path`
corrigido para o wrapper, 8 mídias baixadas, `state=player_running`,
`hwdec-current=v4l2request-copy`, `video pixelformat=nv12`, **24 eventos `Playing media`
(3 voltas 0→7 em ordem)**, `panfrost_js_faults=0`, erros `mmc`/I-O = 0,
`media_load_failed=0`, `mpv_restart=0`, `hard_resync=0`.

Status: **imagem-lab privada**, `final_image=false`, `not_for_production=true`. A 1d é o
candidato atual para continuar C18; ainda falta confirmação visual humana do HDMI para
qualidade perceptual da transição/tela preta antes de declarar imagem final.
