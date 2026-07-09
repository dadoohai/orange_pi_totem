# C21 Player Runtime Image Transcode RCA

Data: 2026-07-09T04:55:04Z  
Placa: Orange Pi lab via SSH `192.168.18.154`  
Release aplicado: `c18.player-runtime-homolog-20260709-image-transcode-50919f5`

## Resumo

O QR/auth funcionou e a API entregou uma playlist valida com 1 midia PNG. O player antigo baixava o PNG, tentava enviar direto ao MPV C18 e a midia ficava bloqueada: `waiting_for_media`, `black_screen_risk_reason=all_media_temporarily_blocked`, `blocked_media_count=1`.

A causa tecnica verificada foi incompatibilidade entre midia de imagem estatica e o MPV/FFmpeg custom C18: o stack custom nao decodificava PNG nesse caminho. A correcao prepara imagens estaticas como sidecar local H.264 MP4 antes de admitir na playlist, mantendo `source_path` para rastreabilidade.

## Evidencia Antes/Depois

Antes:
- `playback_state=waiting_for_media`
- `black_screen_risk_reason=all_media_temporarily_blocked`
- `current_item.path=/data/media/kiosky-player/20198b0e7dd71ec7b0b830214d441ab46f25444d.png`

Depois:
- `apply_rc=0`
- `candidate_health_result.passed=true`
- `playback_state=playing`
- `black_screen_risk_reason=null`
- `current_item.path=/data/media/kiosky-player/20198b0e7dd71ec7b0b830214d441ab46f25444d.png.h264.mp4`
- `current_item.source_path=/data/media/kiosky-player/20198b0e7dd71ec7b0b830214d441ab46f25444d.png`
- MPV IPC: `path=.h264.mp4`, `idle-active=false`, `vo-configured=true`

## Arquivos Principais

- `lab-apply-result.json`: resultado completo do apply lab e before/after.
- `candidate-health-result.json`: deep-health do candidato.
- `post-kiosky-status.json`: status final do player.
- `current-release-verified.json`: marker verificado do release ativo.
- `kms-bgra.png`: captura KMS do plano real do MPV apos correcao.
- `fb0-post.jpg`: captura fbdev; mostra splash de fundo e nao representa o plano DRM do MPV neste caso.
- `lab_apply_player_runtime_image_transcode.py`: script usado para apply lab controlado.

## Observacao De Produto

A midia atual renderiza, mas e visualmente muito escura e pequena. A correcao elimina a falha tecnica de playback do PNG; qualidade visual da arte deve ser tratada em validacao/UX de conteudo separada.
