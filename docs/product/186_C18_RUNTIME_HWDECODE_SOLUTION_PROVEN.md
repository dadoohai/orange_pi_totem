# 186 — C18.RUNTIME.A2..B9 — HW decode + display zero-copy PROVADO end-to-end

Consolidacao da resolucao tecnica do `media_load_failed`. **Supera o veredito
A_BLOCKED_BUILD do doc 185** (A1): o build foi feito e a solucao esta **provada de
ponta a ponta na placa real** — decode HW (Cedrus) + exibicao zero-copy (panfrost) +
rotacao 270 + CPU baixa, inclusive sob **estresse de transicao** (o gatilho real do bug).
Trabalho experimental na branch `c18-runtime-a1-cedrus-hwdecode-poc` (commits A1..B9 so la;
foundation recebe so este resultado). **Nenhuma imagem construida, nenhuma release, placa
restaurada ao fim de cada teste, C nao aceito.**

## Decisao: **HWDECODE_SOLUTION_PROVEN** (falta so produtizacao + flash fisico)

## Causa-raiz (confirmada)
O player decodifica H.264 em **software** (`--hwdec=auto` cai em SW); na transicao
`loadfile` a CPU satura (~3+ nucleos) e a thread principal — que serve o IPC — estoura o
timeout de 2 s => falso `media_load_failed` => restart do MPV (congela/pisca). Todos os
workarounds de player-config (soft-retry, recv/send-timeout, normalizacao de resolucao,
vo=drm, shader-cache) foram **refutados** (docs 179-183). O fix correto e **HW decode**.

## O que foi provado na placa (A2..B9)
- **A2** — decoder Cedrus stateless escrito do zero decodifica via userspace (0,5 ms/frame).
- **B1** — ffmpeg (fork Kwiboo `v4l2request-2024-v2`, hwaccel `v4l2request`) decodifica
  conteudo real 1080p **High/CABAC/B-frames** a **~24x menos CPU** (0,41 s vs 9,98 s).
- **B2/B3** — stack userspace inteira cross-buildada (ffmpeg-fork + libplacebo + mpv +
  libass/freetype/fribidi); mpv roda na placa e engaja o decode HW (`v4l2request`).
- **B4-B6** — root-cause do display: o caminho zero-copy precisa do interop de VO certo
  (vo_drm rejeita DRMPRIME; e via **vo=gpu**).
- **B7** — **display zero-copy PROVADO** no HDMI: `--vo=gpu --gpu-context=drm
  --hwdec=v4l2request` carrega o interop `v4l2request-overlay`, frames ficam `drm_prime`
  (sem autoconvert/download), exibidos no plano de overlay do panfrost. **~7x menos CPU**.
- **B8** — **rotacao 270 + zero-copy**: com `--video-rotate=270` o mpv usa o interop
  EGLImage (`GL_EXT_EGL_image_storage`) — importa o dmabuf como textura GL (sem readback) e
  rotaciona na GPU. CPU baixa (user 2,2 s vs SW 13,3 s / 300 frames).
- **B9** — **soak de transicao `ZERO_COPY_LOADFILE_SOAK_PASSED`**: 30 min, **867 transicoes
  `loadfile`** (a cada ~2 s, ciclando 3 resolucoes p/ forcar reconfig de VO). ACK do
  loadfile **avg 1,5 ms / max 13 ms** (vs timeout de 2000 ms) => **0** `media_load_failed`,
  **0** stalls, hwdec `v4l2request` **867/867** (0 quedas p/ SW), zero-copy mantido,
  **20,2% de um nucleo**. Placa restaurada. **A causa-raiz esta eliminada sob o estresse de
  transicao que originava o bug.**

## O que falta — rodada de imagem-lab (GATED em acesso fisico)
Detalhe em `docs/evidence/candidate-a/runs/<B9>/IMAGE-LAB-PLAN.md`. Resumo:
1. Build num **chroot Bookworm GCC-12** (elimina o shim de libstdc++ do PoC; libass com
   harfbuzz, linking limpo, packaging nativo).
2. `kiosk.py`/launcher: trocar `--hwdec=auto` por **`--hwdec=v4l2request`** (manter
   `--vo=gpu --gpu-context=drm --video-rotate=270`).
3. `totem` no grupo `video`; empacotar a stack na imagem; manter read-only/overlayroot.
4. Validar numa placa de **TESTE fisica**: engaja hwdec, zero-copy (sem autoconvert),
   **corretude visual (olho humano no HDMI)**, **30 fps real estavel**, soak em-imagem
   (`media_load_failed`~0 >=25 min), CPU baixa; rollback p/ imagem known-good.
5. **Flash**: so existe **uma placa, viva, remota (SSH)** — flash exige acesso fisico ou
   placa reserva; nao feito remotamente (risco de brick).

## Risco tecnico: RETIRADO
Decode + zero-copy display + rotacao 270 + sobrevivencia a 867 transicoes estao provados na
placa. O que resta e empacotamento + flash fisico — sem incognita tecnica.

## Trilha de evidencia (branch `c18-runtime-a1-cedrus-hwdecode-poc`)
Runs em `docs/evidence/candidate-a/runs/`: `*-c18-runtime-a2-...` (A2),
`*-b1-ffmpeg-v4l2request-crossbuild`, `*-b2-mpv-link-spike`, `*-b3-mpv-userspace-build`,
`*-b4..b6-...`, `*-b7-zerocopy-display-PROVEN`, `*-b8-rotate270-zerocopy-PASS`,
`*-b9-zerocopy-loadfile-soak-PASS` (+ `BUILD.md`, `IMAGE-LAB-PLAN.md`, `dadooh_soak.py`).

## Guardrails
```
image_built=false flash=false live_board_overwritten=false release=false backend_changed=false
real_config_changed=false c12_readonly_touched=false client_board_deploy=false
board_restored=true (player active, hdmi connected) ; limitation_C_accepted=false
secrets/urls/api_key/api_url/environment_id/ssid/wifi/ip/mac/dns_published=false
```

## Produtizado → C18.IMAGE-LAB.1
A stack provada aqui foi incorporada numa **imagem-lab privada** (derivada offline da
C17.4.2), com o player apontando para o mpv custom e `--hwdec=v4l2request --vo=gpu
--gpu-context=drm`. Ver **doc 187** e a evidencia
`docs/evidence/candidate-a/runs/20260531T145557Z-c18-image-lab-1-hwdecode-build/`.
Imagem `...-c18-hwdecode-lab-1_minimal.img` (sha256 `a1103ba8...`); `final_image=false`,
`not_for_production=true`. Validacao em hardware (C18.IMAGE-LAB.2 clean-board) **obrigatoria**.
**Correção (2026-06-01):** a `1` falhou no 1º boot em hardware (kiosk.py `SyntaxError` por
banner do debugfs + panfrost deferred-probe race) → **gravar a `1b`**
(`...-c18-hwdecode-lab-1b_minimal.img`, sha256 `27ed2906...`), não a `1`. Ver doc 187 (seção
Correção) e a evidência `...-c18-image-lab-1b-hwdecode-rebuild/`.

**Nota pós-image-lab (2026-06-02):** B7/B8/B9 continuam provando tecnicamente o caminho
zero-copy usado na PoC, mas a validação de imagem com o conjunto real encontrou `panfrost js
faults` em algumas mídias portrait no caminho `v4l2request`/`drm_prime`. A
**C18.IMAGE-LAB.1d** troca o wrapper para **`v4l2request-copy`** como fallback de estabilidade
e preserva o HW decode Cedrus. Não tratar zero-copy como caminho final de produto até nova
validação com mídias reais; ver doc 187/188.
