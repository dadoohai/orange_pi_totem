# 182 — C18.RUNTIME Hardware Validation Consolidation (root cause + refuted fixes)

Consolidacao da campanha de validacao em hardware (Orange Pi Zero 3 / Allwinner
H618, imagem C17.4.2) que seguiu os docs 179 (diagnostico) e 180 (fix soft-retry).
**Conclusao:** a causa real do `media_load_failed` esta na **decodificacao de
video (software decode)**, NAO na camada de IPC/timeout do player. Tres tentativas
de fix no `kiosky-player` foram **refutadas em hardware**. O soft-retry (commit
`7ca6691`, doc 180) foi **revertido** (`kiosky-player@e76204a`). Rodada **pausada**
para decisao de equipe sobre o fix correto (habilitar HW decode = trabalho de
imagem/BSP, ou aceitar o restart).

Evidencia: `docs/evidence/candidate-a/runs/20260530T003326Z-c18-runtime-hw-validation-consolidation/`.

## O que estava em jogo

- 179 concluiu (corretamente) que **duracao esta OK**: a API retorna
  `exposure_time_ms` e o player o honra 1:1. E **inferiu** que a repeticao vinha
  de `media_load_failed -> reinicio do MPV -> recarga do item`.
- 180 implementou um **soft-retry** (reenviar `loadfile` antes do restart) como fix.

## Campanha de validacao em hardware (cirurgica, reversivel, /opt)

Cada fix foi instalado como `307d986 + APENAS o fix` em `/opt` (a placa sempre
cai no /opt; backup+restore; sem release, sem imagem). Observacao por janela de
~15-17 min. Resumo:

| Rodada | Fix testado | Resultado | Evidencia-chave |
|--------|-------------|-----------|-----------------|
| R3 | soft-retry (reenvio loadfile) | **REFUTADO** | 0 recoveries; 1 restart mesmo assim; +~4.6s de lingering |
| R5 | (probe passivo) | dado | stall NAO e I/O (sem D-state, io=0); main thread busy |
| R6 | recv-timeout 8s | **REFUTADO** | falha e no SEND, nao no recv; duracao seguiu 2.0s |
| R7 | (probe por thread) | dado | thread `mpv` (main/playloop) a **99% CPU** durante o stall |
| R8 | send-timeout 8s | **REFUTADO** | `sendall` bloqueou **8.0s** e ainda falhou => stall > 8s |
| query | mpv decode props | causa raiz | **hwdec-current=no** (software H264), 576x1024@30, ~54% CPU steady |
| R9 | hwdec=v4l2m2m-copy (off-display) | **NAO ENGATA** | Cedrus presente (/dev/video0); ffmpeg `h264_v4l2m2m` (stateful) incompativel com Cedrus stateless => "Could not find a valid device" -> software |

## R9 — teste hwdec=v4l2m2m-copy (cirurgico, off-display, read-only)

MPV standalone com `--vo=null` (sem DRM, sem tocar o player) sobre um arquivo em
cache. Achados:
- Hardware presente: `/dev/video0`=`cedrus`; dmesg
  `cedrus 1c0e000.video-codec: Device registered as /dev/video0` (driver staging).
- MPV 0.35.1 aceitou `--hwdec=v4l2m2m-copy` e tentou `h264_v4l2m2m`, mas:
  `Could not find a valid device` -> `can't configure decoder` -> **Falling back
  to software decoding** (mesmo como root => nao e permissao).
- `hwdec=auto-copy` nem tenta v4l2m2m (so nvdec/vaapi/vdpau) => por isso a placa
  fica em software (`hwdec-current=no`).
- **Causa:** Cedrus e um decoder **stateless** (V4L2 Request API); o
  `h264_v4l2m2m` do ffmpeg e o wrapper **stateful** — incompativeis. Habilitar HW
  decode exige o caminho **V4L2 Request / Cedrus stateless** no userspace
  (ffmpeg/mpv com `v4l2-request`/`libva-v4l2-request` ou build mais novo) — e
  **trabalho de imagem/build, NAO um flag de config**. (Secundario: o player roda
  como `totem`, que precisaria estar no grupo `video` para abrir `/dev/video0`.)
- Placa **nao alterada** pelo teste (mpv standalone off-display, auto-removido).

## Causa raiz (confirmada)

```
hwdec-current = no            # HW decode NAO engata (apesar de --hwdec=auto)
video-codec   = h264   576x1024 @30fps  ~892 kbps
mpv %CPU steady = ~54% (1 core A53)   frame-drop = 0
```

O MPV **decodifica H.264 em software** no A53. O regime estavel e OK (sem drops).
Porem um **`loadfile` novo** precisa inicializar o decoder de software + decodar o
primeiro keyframe + reconfigurar o VO DRM/KMS (com rotacao 270) de forma
**sincrona no main thread**, que e o mesmo thread que serve o IPC JSON. Esse init
**satura o main thread a ~100% por um tempo VARIAVEL que pode passar de 8s**.
Durante esse tempo o MPV nao le o socket IPC -> o buffer de envio enche -> o
`sendall` do `loadfile` do player bloqueia e estoura o timeout do socket ->
`media_load_failed` -> reinicio do MPV.

Sequencia exata do `_send` (kiosk.py):
`MPV IPC command send failed command=loadfile ... error=timed out` — a falha e no
**envio** (`sendall`), governada pelo timeout do socket (`_open_ipc` settava 2.0s;
R8 elevou p/ 8.0s e ainda estourou). Nao e o `_recv_response`.

## Por que nenhum fix de player resolve

Os tres fixes atacavam a camada de IPC/timeout, mas o gargalo e o **custo de init
do decode de software (>8s)**:
- soft-retry: reenviar para um MPV que nao le o IPC so estoura de novo.
- recv-timeout: a falha e no send, nao no recv.
- send-timeout: esperar mais so prolonga o lingering antes do restart inevitavel
  (o stall excede 8s).

## Efeito visivel real (refina o 179)

A ligacao "media_load_failed -> repeat" do 179 e **fraca**. Medido: as recargas
pos-restart ocorrem em **offset 0 do item alvo** (102-103 plays em offset 0), ou
seja **nao** e repeticao de item no nivel de playlist. O que o operador percebe e:
o **item corrente fica congelado/em loop ~2-8s** durante o stall (o MPV ainda
mostra o item anterior, loop-file=inf) + um **flash preto** no restart, ~1-2x a
cada ~17 min. A playlist em si avanca previsivel (179) e a duracao e respeitada.

## Fix correto (direcao; fora do kiosky-player)

1. **Habilitar HW decode no H618 (Cedrus)**: o kernel ja tem o Cedrus
   (`/dev/video0`, staging), mas o teste R9 mostrou que `hwdec=v4l2m2m-copy`
   **NAO engata** com o MPV/ffmpeg atuais (Cedrus e **stateless/V4L2 Request**;
   `h264_v4l2m2m` e stateful -> incompativel). Habilitar exige o caminho **V4L2
   Request / Cedrus stateless** no userspace (ffmpeg/mpv com `v4l2-request` /
   `libva-v4l2-request` ou build mais novo) + `totem` no grupo `video`. Ou seja,
   **trabalho de imagem/build, NAO um flag de config**.
2. **Otimizar/transcodar as midias** para software decode barato/init rapido
   (nivel backend/conteudo Habitat) — sem mudar imagem.
3. **Aceitar o restart** como limitacao de HW: recupera em ~1-2s, recarrega o item
   alvo em offset 0; documentar e seguir.

As tres opcoes foram **abertas como rodada de decisao** no doc
`183_C18_RUNTIME_DECODE_STRATEGY_DECISION_ROUND.md` (comparacao; sem construir
imagem/kernel, sem aceitar a limitacao ainda). R4 (perms do updater) segue em
branch propria `c18-runtime-updater-perms-fix`.

## Estado atual

- `kiosky-player`: soft-retry **revertido** (`e76204a`), de volta a baseline C18.2
  (`d4e4c4e`). Nenhum fix de runtime embarcado. Testes 99 OK.
- Placa: restaurada ao original `307d986` (`/opt`), limpa, sem instrumentacao.
- 180 marcado como **refutado** (ver banner no doc 180).
- Nenhuma release publicada, nenhuma imagem, nenhum config real alterado.

## Guardrails

secrets_published=false ; api_key/api_url/environment_id/ssid/wifi_password=false
media_urls_published=false ; apt/pip/upgrade=false ; image_built=false ; card_written=false
kernel_touched=false ; read_only/c12_touched=false ; writer_called=false ; real_config_written=false
poweroff=false ; power_cut=false ; ssh_password_persisted=false
board_restored_to_original=true ; board_left_clean=true
