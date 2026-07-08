# C20.7 Totem-Core Board Apply

## Resultado

C20.7 foi aplicado na placa por `totem-updatectl apply-local` com sucesso.

- Pacote: `c20.7-clock-metadata-20260708T042733Z-b9d8a00`
- Payload SHA256: `01ab5cc921379366597719857ed55ab0360b052001d50c1ced896c4f881d5ec5`
- Antes: `releases/c20.6-top-step-preview-20260708T031956Z-5686f83`
- Depois/current: `releases/c20.7-clock-metadata-20260708T042733Z-b9d8a00`
- Rollback/previous: `releases/c20.6-top-step-preview-20260708T031956Z-5686f83`

## Mudanca Validada

O wizard agora exibe data/hora como metadado passivo do cabecalho:

- etapa 0 preserva `Layout paisagem/retrato`;
- etapas 1-4 exibem `DD/MM/YYYY HH:MM`;
- data implausivel cai para `Hora nao ajustada`;
- sem botao, sem rodape, sem segundos, sem relogio vivo;
- sem alterar hora, timezone, NTP, RTC ou systemd.

## Evidencia

- `c18-ota-release-gate.json`: gate OTA verde, 66 checks.
- `board/post-apply-status.txt`: current/previous, self-test pos-apply e player active.
- `captures/clock-preview.png`: captura real do framebuffer da placa com a hora no cabecalho.
- `board-preview-svgs/0001-01-orientation.svg`: etapa Tela preserva `Layout paisagem`.
- `board-preview-svgs/0005-02-connection.svg`, `0012-03-environment.svg`, `0016-05-review.svg`: etapas com data/hora no cabecalho.
- `board/preview-session.log` e `board/preview-session.rc`: preview real encerrou com rc=0.

## Estado Operacional

A sessao preview encerrou, `kiosky-player.service` voltou `active`, o apply guard ficou
`settings_session_inactive`, e a placa permaneceu em C20.7.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull, stable, hora do sistema, timezone,
NTP ou RTC.
