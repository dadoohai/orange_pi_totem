# 183 — C18.RUNTIME Decode Strategy Decision Round

**Rodada de DECISAO (comparacao), nao de execucao.** Objetivo: escolher a
estrategia para eliminar a percepcao de "repeticao/loop + flash" causada pelo
custo de init do **software decode** no Orange Pi Zero 3 / H618. Comparar tres
caminhos. **Nesta rodada NAO se constroi imagem/kernel, NAO se publica release,
e NAO se aceita a limitacao em definitivo.**

Base: docs 179 (diagnostico de duracao — OK), 182 (consolidacao da causa raiz +
3 fixes de player refutados + teste hwdec). R4 (fix de permissoes do updater)
segue em branch propria (`c18-runtime-updater-perms-fix`), para rodada posterior.

## O que ja esta estabelecido (nao re-decidir)

- Duracao OK: API retorna `exposure_time_ms`, player honra 1:1.
- Causa raiz: MPV **software-decodifica H.264** (`hwdec-current=no`) no A53. O
  init de um `loadfile` novo (open do decoder SW + 1o keyframe + reconfig do VO
  DRM/KMS com rotacao 270) satura o **main thread** do MPV a ~100% por tempo
  variavel **que pode passar de 8s**; durante isso o MPV nao serve o IPC -> o
  `sendall` do player estoura -> `media_load_failed` -> reinicio do MPV.
- Efeito visivel: item corrente congela/loopa ~2-8s + flash no restart, ~1-2x a
  cada ~17min. Restart recarrega o item alvo em offset 0 (nao e repeticao de
  playlist).
- Fixes de timeout/retry no player: **refutados** (camada errada).
- HW: o decoder Cedrus existe (`/dev/video0`=cedrus, driver staging do kernel
  presente), porem `hwdec=v4l2m2m-copy` **NAO engata** com o MPV 0.35.1/ffmpeg
  atuais: `h264_v4l2m2m` (wrapper stateful) e incompativel com o Cedrus
  (decoder **stateless**, V4L2 Request API) -> "Could not find a valid device"
  -> fallback p/ software. `hwdec=auto` nem tenta v4l2m2m.
- Conteudo medido: H.264, ~576x1024 / 480x848, ~30 fps, ~892 kbps; sw decode em
  regime estavel ~54% de 1 core (sem frame drops). O problema e o **init**, nao
  o regime.

## Opcoes a comparar

### Opcao A — Hardware decode via Cedrus / V4L2 Request API
- **O que:** ffmpeg+mpv com o caminho **stateless** (V4L2 Request) para o Cedrus
  (ex.: ffmpeg `v4l2-request` hwaccel + `libva-v4l2-request`, ou mpv/ffmpeg mais
  novos com suporte Cedrus), e `totem` no grupo `video` para abrir `/dev/video0`.
  Kernel ja tem o Cedrus (staging).
- **Prós:** ataca a causa na raiz; init e CPU caem muito; melhor UX; resolve o
  flash/lingering e os falsos `media_load_failed`.
- **Contras/incertezas:** trabalho de **imagem/BSP/userspace-build** (fora desta
  rodada); maturidade do driver staging; cobertura de codecs/perfis/resolucoes
  do Cedrus (H.264 ok; confirmar perfis/420 e as resolucoes em uso; HEVC se
  surgir); exige PoC + validacao em hardware; rebuild de imagem.
- **Avaliacao necessaria (PoC, sem alterar a placa de producao):** build offline
  de ffmpeg/mpv com V4L2 Request; provar que o Cedrus engata num board de teste;
  medir tempo de init, CPU e estabilidade; confirmar todos os formatos das
  campanhas.

### Opcao B — Otimizacao/transcode das midias para software decode
- **O que:** no pipeline de conteudo (Habitat), transcodar as campanhas para um
  perfil que o A53 decodifica e **inicia** barato (ex.: limitar resolucao/bitrate,
  perfil baseline/main, GOP/keyframe menor, possivelmente fps); reduzir o custo
  de init por item.
- **Prós:** sem mudar dispositivo/imagem; controlado no backend; rollout por
  conteudo; reversivel.
- **Contras/incertezas:** pode **reduzir** o init abaixo da janela de IPC, mas
  talvez nao elimine (o custo de reconfig do VO/DRM+rotacao independe da midia);
  trabalho de pipeline; tradeoff de qualidade; precisa achar empiricamente o
  perfil que torna o init confiavelmente < ~2s.
- **Avaliacao necessaria:** transcodar amostras com parametros variados; medir o
  tempo de `loadfile`/init **na placa**; achar um perfil com init estavel curto.

### Opcao C — Aceitacao temporaria da limitacao
- **O que:** documentar o restart como limitacao de HW conhecida; opcionalmente
  ajuste menor no player que **nao finge corrigir** (garantir recarga com
  `offset` preservado p/ minimizar a repeticao visivel; reduzir o flash). Manter
  o comportamento atual.
- **Prós:** risco zero agora; imediato.
- **Contras:** o glitch visivel persiste (~1-2x/17min).
- **Avaliacao necessaria:** confirmar tolerancia operacional; definir escopo do
  ajuste de recarga-com-offset se for adotado como paliativo.

## Criterios de decisao
Impacto na UX • esforco/prazo • risco • reversibilidade • cobertura (todas as
midias/formatos) • manutenibilidade. (B e C podem ser **interim** enquanto A e
construido e validado.)

## Criterios de aceite desta rodada (decisao)
1. As 3 opcoes comparadas com prós/contras e o que cada PoC exige.
2. Caminho primario escolhido (e interim, se aplicavel), com evidencia minima
   exigida por opcao.
3. Nenhuma imagem/kernel construida nesta rodada.
4. Nenhuma aceitacao finalizada nesta rodada.
5. R4 mantido em branch propria.

## Guardrails desta rodada
image_built=false ; kernel_touched=false ; release_published=false
limitation_accepted=false ; board_modified=false ; r4_kept_on_own_branch=true
decision_only=true

## Proximos passos sugeridos (apos a decisao)
- Se A: abrir rodada de PoC de build ffmpeg/mpv V4L2-Request num board de teste.
- Se B: abrir rodada de transcode-experiment medindo init na placa.
- Se C: abrir rodada do paliativo (recarga com offset) + documentacao formal.
