# 185 — C18.RUNTIME.A1 Cedrus HW decode PoC — RESULT

Resultado da PoC isolada (PDCA) da opcao A (HW decode Cedrus/V4L2 Request).
Trabalho experimental na branch `c18-runtime-a1-cedrus-hwdecode-poc` (log completo
em `docs/poc/c18-runtime-a1-cedrus-hwdecode/POC_LOG.md` *naquela branch*). Aqui
fica apenas o resultado/decisao final. **Nenhuma imagem construida, nenhuma
release, placa intocada (tudo read-only), C nao aceito.**

## Decisao: **A_BLOCKED_BUILD** (causa: **A_BLOCKED_STACK**)

- **Kernel/Cedrus: PRONTO.** Probe V4L2 (pure-Python ioctl, read-only) em
  `/dev/video0` confirmou: `driver=cedrus`, decode **stateless** (Request API) com
  `OUTPUT [S264] H.264 Parsed Slice Data` (e S265/HEVC, MG2S/MPEG-2, VP8F) ->
  `CAPTURE [NV12]`. **Stateless-only** (sem H264 stateful).
- **Userspace: bloqueado (A_BLOCKED_STACK).** ffmpeg 5.1.8 (Debian) so tem o
  wrapper **stateful** `*_v4l2m2m` (incompativel com o Cedrus stateless — por isso
  dava "Could not find a valid device"); sem `v4l2-request`; libva presente mas
  **sem VA driver** (libva-v4l2-request ausente/deprecado). mpv 0.35.1 nao alcanca
  o Cedrus.
- **Build: bloqueado nesta sessao (A_BLOCKED_BUILD).** Placa sem toolchain;
  cross-gcc do dev-host sem sysroot aarch64; o caminho real exige um **ffmpeg
  downstream/patched** (com V4L2 stateless/Request) casado com a uAPI do kernel +
  build via **pipeline de imagem-lab** — fora de um bundle contido em sessao.

Nao e **C_ONLY**: a opcao A continua viavel porque o **lado kernel ja esta pronto**
— o que falta e uma stack de userspace, produzivel numa rodada de imagem-lab.

## Receita p/ desbloquear A (rodada de imagem-lab — NAO executada aqui)
Alvo provado: V4L2 **stateless** H.264 `S264`(OUTPUT) -> `NV12`(CAPTURE), Request
API + `/dev/media0`, kernel 6.12.58-sunxi64; rotacao 270 pos-decode na GPU
panfrost.
1. No pipeline de imagem-lab (nunca producao): userspace com decode stateless
   Cedrus — **ffmpeg com V4L2 stateless/Request** (downstream Armbian/LibreELEC ou
   patcheado; mainline nao serve) + **mpv** linkado a ele. (libva-v4l2-request:
   baixa prioridade, provavel incompatibilidade de uAPI.)
2. Casar headers de uAPI com o kernel da placa.
3. Runtime: `totem` no grupo `video`; mpv `--hwdec` no caminho stateless; conferir
   `hwdec-current` != `no`.
4. Validar A_PASS numa placa de TESTE (hwdec engaja; `media_load_failed`~0 em
   >=25min; CPU/visual ok incl. **olho no HDMI**; soak >=1h). PASS -> planejar
   imagem candidata (rodada separada). FAIL -> A_FAIL_RUNTIME, reabrir A-vs-C.

## Relacao com o resto
- Causa raiz e tentativas refutadas: docs 179/182/183 (player-config esgotado).
- Plano A: doc 184. Este doc (185) = resultado da PoC A1.
- R4 (perms do updater) ja integrado (C18.RUNTIME.4) — independente; nao misturar.

## Guardrails (A1)
image_built=false ; kernel_touched=false ; release_published=false ; backend_changed=false
real_config_changed=false ; apt_upgrade=false ; poweroff=false ; c12_readonly_touched=false
client_board_deploy=false ; urls/secrets/api/ssid/ip/mac/dns_published=false
board_state=read_only_only_unchanged (307d986/vo=gpu) ; limitation_C_accepted=false
poc_commits_isolated_on_branch=c18-runtime-a1-cedrus-hwdecode-poc
