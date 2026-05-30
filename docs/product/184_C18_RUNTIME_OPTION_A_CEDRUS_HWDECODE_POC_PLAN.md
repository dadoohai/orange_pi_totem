# 184 — C18.RUNTIME Option-A PoC Plan: Cedrus HW decode via V4L2 Request

**PLANO apenas. NAO construir imagem/kernel agora.** Define a PoC para provar (ou
refutar) que habilitar decode por hardware (Cedrus, V4L2 Request API) no H618
elimina os `media_load_failed` com CPU/qualidade aceitaveis — de forma isolada,
antes de comprometer uma imagem de producao.

Contexto: docs 179/182/183. Todas as tentativas baratas de player-config/conteudo
foram **esgotadas e refutadas**: soft-retry, recv-timeout, send-timeout,
normalizacao de resolucao, `vo=drm` (CPU 308% + ~88 restarts), `gpu-shader-cache-dir`
(sem efeito; cache nunca populou). A causa (GPU/VO reconfig + software decode
saturando o main thread do MPV) so e atacavel na camada de **imagem/userspace com
HW decode**.

## Objetivo
Numa PoC isolada (image-lab / placa de TESTE, nao a de producao), demonstrar
decode H.264 por hardware via Cedrus e medir se os stalls desaparecem com custo
aceitavel. Saida: PASS (planejar rodada de imagem) ou FAIL (escalar A-vs-C com
evidencia).

## Fundo tecnico (ja confirmado)
- Kernel tem o Cedrus (staging): `/dev/video0` = decoder V4L2 **stateless**
  (Request API).
- MPV 0.35.1 / ffmpeg atuais: `hwdec=auto` -> `no`; `v4l2m2m` (stateful) e
  **incompativel** com o Cedrus ("Could not find a valid device").
- Falta: stack de userspace que dirige o Cedrus stateless — ffmpeg com **V4L2
  Request** (hwaccel `drm`/v4l2-request) + **libva-v4l2-request** (VA-API sobre
  V4L2 Request), e MPV usando esse caminho (ex.: `--hwdec=vaapi` via driver VA
  v4l2-request, ou `--hwdec=drm`). Mais: usuario `totem` no grupo `video` para
  abrir `/dev/video0`.

## Escopo da PoC (o que montar; OFF-producao)
1. Obter/montar (offline; sem apt/pip no device) um bundle de userspace p/ H618:
   ffmpeg + libva + libva-v4l2-request (ou pacote conhecido de Armbian/LibreELEC
   com Cedrus) + mpv que use esse caminho.
2. Encenar numa placa de TESTE (ou na dev de forma contida/reversivel), **nunca**
   na imagem de producao, **nunca** em C12/read-only.
3. Configurar o hwdec do MPV para o caminho V4L2 Request; `totem` no grupo `video`.

## Criterios de aceite (definir ANTES de rodar)
- `hwdec-current` mostra o caminho Cedrus (nao `no`) para H.264.
- `media_load_failed`/restart cai para **~0** numa janela >= 25 min (baseline ~2.1%).
- Sem spikes de CPU do main thread > a janela de timeout de IPC em transicoes.
- CPU em regime aceitavel (idealmente << ~54%).
- **Verificacao VISUAL no HDMI**: render correto, rotacao 270 intacta, sem
  artefatos/tearing, todas as resolucoes reais (480x688 .. 1080x1920).
- Estabilidade em soak (1-2 h): sem hang do decoder, sem leak, sem watchdog
  thrashing.
- Cobertura de todos os codecs/perfis/resolucoes reais (H.264 Baseline/Main;
  confirmar suporte do Cedrus).

## Riscos / incertezas
- Cedrus e staging (maturidade/estabilidade).
- Disponibilidade/build de libva-v4l2-request p/ o kernel exato.
- Rotacao 270 sob o caminho hwdec (pode exigir GPU/pos-proc — risco de reintroduzir
  CPU).
- Interop hwdec x `vo=gpu` (zero-copy) vs variante `-copy`.

## Higiene de repo/processo
- Artefatos da PoC em image-lab / branch dedicado; **nao** merjar nas branches de
  producao ate passar nos criterios.
- **Nenhuma imagem de producao** a partir disto ate a PoC passar + sign-off humano.
- Se a PoC falhar -> decisao C (aceitar) **somente com sign-off humano**.

## Portao de decisao (apos a PoC)
- PASS -> planejar rodada de imagem (C18.RUNTIME.x) integrando o stack de decode + ship.
- FAIL -> escalar A-vs-C ao time com a evidencia da PoC.

## Fora de escopo deste doc
Construir qualquer imagem, mexer em kernel/U-Boot/DTB/BSP, publicar release,
alterar config de producao. Este e o PLANO; execucao depende de aprovacao.
