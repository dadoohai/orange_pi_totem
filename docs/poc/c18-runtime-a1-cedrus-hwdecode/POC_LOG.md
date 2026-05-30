# C18.RUNTIME.A1 — Cedrus/V4L2 Request HW decode PoC (PDCA log)

**Branch/worktree isolada:** `c18-runtime-a1-cedrus-hwdecode-poc`. Commits
experimentais SO aqui. `appliance-v0.1` e `foundation-v0.1` NAO recebem build
quebrado; foundation recebe apenas doc/evidencia final. Nunca produção, nunca
imagem final, nunca deploy em placa de cliente, nunca C12/read-only.

## Objetivo
Construir e validar, isolado, uma stack de userspace que dirija o Cedrus
(H.264, V4L2 Request API) no Orange Pi Zero 3/H618, e medir se o HW decode engaja
e se reduz/elimina `media_load_failed`/restarts. Saida = decisao codificada.

## Decisao (saidas possiveis)
- **A_PASS** — HW decode engaja E media_load_failed ~0/reduz muito, CPU/visual ok
  => seguir para imagem candidata (rodada separada).
- **A_BLOCKED_STACK** — userspace atual (mpv/ffmpeg/VA) nao consegue usar o Cedrus
  e nao ha caminho contido (drop-in) viavel.
- **A_BLOCKED_BUILD** — caminho existe em tese, mas o build nao fecha neste
  ambiente (sem cross-toolchain/sem apt-upgrade/sem prebuilt confiavel).
- **A_FAIL_RUNTIME** — hwdec engaja mas NAO resolve (falhas persistem) ou custo
  inaceitavel (CPU/visual).
- **C_ONLY** — A inviavel agora => limitacao temporaria vira opcao restante
  (somente com decisao humana).

## Criterios de aceite (A_PASS)
1. `hwdec-current` != `no` (caminho Cedrus) p/ H.264.
2. `media_load_failed`/restart ~0 numa janela >=25 min (baseline ~2.1%).
3. Sem spike de CPU do main-thread > janela de timeout IPC em transicoes.
4. CPU regime aceitavel (idealmente << ~54%).
5. Verificacao VISUAL no HDMI (render correto, rotacao 270, sem artefato, todas
   resolucoes reais 480x688..1080x1920).
6. Estabilidade em soak (>=1 h): sem hang/leak/watchdog thrashing.

## Plano (P) — etapas
- **D1 recon (read-only):** capacidades reais de decode do userspace na placa —
  ffmpeg build flags / `-hwaccels` / decoders v4l2/vaapi; libva + VA drivers;
  /dev/dri + GPU; uAPI do /dev/video0 (Cedrus, stateful vs stateless); toolchain
  de build presente?
- **D2 selecao do menor caminho viavel:** (a) drop-in de VA driver
  (libva-v4l2-request) sem mexer no sistema; (b) ffmpeg com `request` hwaccel;
  (c) rebuild completo (image-lab). Escolher o menor que caiba **sem apt-upgrade,
  sem mutar producao, reversivel**.
- **D3 montar bundle contido:** binarios/.so em `/data/.../a1poc` ou `/tmp`
  (NUNCA system-wide), executavel off-display p/ provar decode, depois (se
  seguro) no player via swap reversivel de /opt.
- **D4 teste:** `hwdec-current`, media_load_failed em janela, CPU, (visual via
  proxies + nota de que HDMI exige olho humano).
- **C (check):** comparar com criterios. **A (act):** ajustar caminho ou concluir.
- **Conclusao:** codigo de decisao + evidencia; foundation recebe doc/evidencia
  final; bundle removido e placa restaurada.

## Guardrails (desta rodada)
sem apt upgrade/full/dist/armbian-upgrade ; sem publicar secrets/URLs/api_key/
api_url/environment_id/SSID/senha/IP/MAC/DNS ; sem poweroff/corte seco ; sem
release GitHub ; sem deploy em placa de cliente ; sem C12/read-only ; sem alterar
config real/secrets/Wi-Fi/writer/dados de cliente ; placa dev restaurada ao fim
de cada teste ; C nao aceita sem decisao humana.

---
# Execucao

## D1 — recon do userspace (read-only, placa)
- arch aarch64, glibc 2.36 (Debian bookworm).
- **ffmpeg 5.1.8** (Debian): hwaccels = vdpau/cuda/vaapi/drm/opencl/vulkan;
  decoders v4l2 = SOMENTE `*_v4l2m2m` (wrapper **stateful**). **Sem
  `v4l2-request`/stateless.** (mainline removeu o hwaccel v4l2-request ha anos.)
- **libva presente** (libva.so.2) mas **diretorio de VA drivers VAZIO** (sem
  `*_drv_video.so`); `vainfo` ausente. Sem driver VA p/ Cedrus
  (libva-v4l2-request ausente).
- GPU = **panfrost** (Mali) + sun4i-drm; render node `/dev/dri/renderD128`.
- Cedrus = `/dev/video0` + `/dev/media0` (name=cedrus). `v4l2-ctl` ausente.
- **Sem toolchain de build na placa** (gcc/cc/clang/make/meson/ninja/pkg-config/
  cmake = nenhum).
- mpv 0.35.1 (hwdec: vaapi/vaapi-copy/v4l2m2m-copy).

## D1b — ambiente de build deste sessao
- dev machine x86_64; `aarch64-linux-gnu-gcc` + qemu-user presentes, MAS **sem
  sysroot/headers aarch64** (cross-compile trivial falha em
  `bits/libc-header-start.h`); sem docker. => cross-build exigiria apt-install de
  cross-dev + (p/ o stack real) um ffmpeg downstream casado com a uAPI do kernel.
- repo tem pipeline de imagem (`scripts/build/run_*image*`).

## D2/D3 — prova direta da uAPI do Cedrus (pure-Python ioctl, read-only, placa)
Sem compilar (placa nao tem toolchain): probe Python via `fcntl.ioctl` em
/dev/video0 (VIDIOC_QUERYCAP + ENUM_FMT).
```
driver=cedrus card=cedrus device_caps=0x04208000  is_m2m=1 streaming=1
OUTPUT(coded-in): [S264] H.264 Parsed Slice Data ; [S265] HEVC ; [MG2S] MPEG-2 ; [VP8F] VP8
CAPTURE(decoded): [NV12] ; [ST12]
VERDICT: h264_slice(stateless)=True  h264_stateful=False  hevc_slice=True
```
=> Cedrus expoe decode **stateless** (Request API): H.264 `S264` OUTPUT -> `NV12`
CAPTURE. **Stateless-only** (sem H264 stateful) — exatamente por isso o
`h264_v4l2m2m` (stateful) do ffmpeg falhava ("Could not find a valid device").

## C — check vs criterios de aceite
- Kernel/Cedrus: **PRONTO** (stateless H.264 S264->NV12 confirmado em hardware
  real). Criterio de viabilidade do lado kernel: OK.
- Userspace end-to-end (hwdec engaja, media_load_failed~0, visual): **NAO
  alcancavel nesta sessao** — falta a stack de userspace; nao ha bundle contido
  viavel.

## A — act / decisao
**A_BLOCKED_BUILD** (primaria) — o stack de decode (ffmpeg/mpv falando V4L2
stateless Request) **nao pode ser produzido/rodado como bundle contido nesta
sessao**: placa sem toolchain; cross-env sem sysroot; e o caminho real exige um
**ffmpeg downstream/patched** casado com a uAPI stateless do kernel + build via
pipeline de imagem-lab. **A_BLOCKED_STACK** (causa provada) — userspace mainline
(ffmpeg 5.1.8/mpv 0.35.1) nao tem o caminho Cedrus stateless; so o v4l2m2m
stateful (incompativel). **NAO** e C_ONLY: A segue viavel via rodada de
imagem-lab (kernel pronto). **NAO** e A_PASS/A_FAIL_RUNTIME (nao rodou hwdec
end-to-end).

## Receita p/ a rodada de imagem-lab (desbloqueio de A) — NAO executar agora
Alvo (provado): V4L2 **stateless** H.264 `S264`(OUTPUT) -> `NV12`(CAPTURE) via
Request API + `/dev/media0`, em kernel 6.12.58-sunxi64; rotacao 270 pos-decode
na GPU panfrost.
1. Construir, no pipeline de imagem-lab (NUNCA producao), um userspace com **decode
   stateless Cedrus**: opcao preferida = **ffmpeg com suporte V4L2 stateless/
   Request** (downstream: arvore de media do Armbian/LibreELEC ou ffmpeg patcheado;
   mainline NAO serve) + **mpv** linkado a ele. (libva-v4l2-request e
   deprecada e provavelmente incompativel com a uAPI mainline — baixa prioridade.)
2. Casar com os headers de uAPI do kernel da placa (V4L2 stateless H264 controls).
3. Runtime: `totem` no grupo `video` (abrir /dev/video0+media0); mpv `--hwdec`
   no caminho stateless; conferir `hwdec-current` != `no`.
4. Validar contra os criterios A_PASS (incl. **olho no HDMI**) numa placa de
   TESTE; soak >=1h. Se passar -> planejar imagem candidata (rodada separada).
   Se falhar -> A_FAIL_RUNTIME e reabrir A-vs-C com evidencia.

## Estado
Placa: tudo read-only (recon + probe ioctl); **nada alterado**; segue original
`307d986`/`vo=gpu`. Bundle contido: nao criado (build bloqueado). C nao aceito.
Sem imagem/kernel/release/backend/config. Commits experimentais nesta branch;
foundation recebe apenas o doc/evidencia final (185).
