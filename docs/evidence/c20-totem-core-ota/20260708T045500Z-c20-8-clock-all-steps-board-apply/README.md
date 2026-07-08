# C20.8 Totem-Core Board Apply

C20.8 foi aplicado na placa por `totem-updatectl apply-local` com sucesso.

- Pacote: `c20.8-clock-all-steps-20260708T045317Z-661c582`
- Payload SHA256: `78604b737baba1afc16c93075c6a3a5979e221d7f6999b1dd53e9408b0484ff8`
- Depois/current: `releases/c20.8-clock-all-steps-20260708T045317Z-661c582`
- Rollback/previous: `releases/c20.7-clock-metadata-20260708T042733Z-b9d8a00`
- Gate OTA: verde, 66 checks.

## Mudanca Validada

Na etapa `Tela`, o slot superior direito do cabecalho passou a ser somente para
data/hora ou `Hora nao ajustada`. A tag redundante `Layout paisagem/retrato` nao
aparece mais nesse local. A orientacao continua disponivel no conteudo e no
preview da propria etapa.

## Evidencias

- `board/post-apply-status.txt`: status da placa depois do apply, self-test da
  versao instalada, servico ativo e guard verde.
- `direct-preview-svgs/`: galeria gerada diretamente na placa por
  `totem_setup_visual_wizard.py --preview-screens`.
- `rendered/`: PNGs renderizados localmente a partir dos SVGs gerados na placa.
- `direct-preview-svgs/0001-01-orientation.svg`: etapa `Tela`; contem data/hora
  e nao contem `Layout paisagem`.
- `c18-ota-release-gate.json`: gate de release reproduzido para o pacote.

## Observacao

Tambem foi tentada captura de framebuffer em `captures/`, mas ela saiu preta
neste ambiente. Por isso, o aceite visual desta rodada usa a galeria SVG gerada
na placa e os PNGs renderizados a partir dela.

