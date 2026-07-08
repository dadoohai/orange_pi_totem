# C20.9 Totem-Core Board Apply

C20.9 foi aplicado na placa por `totem-updatectl apply-local` com sucesso.

- Pacote: `c20.9-wifi-step-copy-20260708T060338Z-34a9537`
- Payload SHA256:
  `410a38fcff874c329906f2abf654b84050265d787451d3a058f8e40bbad9eb3e`
- Depois/current:
  `releases/c20.9-wifi-step-copy-20260708T060338Z-34a9537`
- Rollback/previous:
  `releases/c20.8-clock-all-steps-20260708T045317Z-661c582`
- Gate OTA: verde, 66 checks.

## Mudanca Validada

- A etapa superior `2. Conexao` passou a aparecer como `2. Wi-Fi`.
- O titulo da etapa tambem passou a ser `Wi-Fi`, com texto curto:
  `Escolha o Wi-Fi.`
- A revisao passou a usar `Wi-Fi` como rotulo de resumo.
- Foram removidas do rodape as indicacoes confusas:
  `Esquerda/Direita etapas`, `Baixo opcoes` e `Baixo revisao`.
- O rodape de foco no topo agora fica simples: `Enter abre | Esc volta`.

## Evidencias

- `c18-ota-release-gate.json`: gate de release reproduzido em arvore limpa.
- `board/post-apply-status.txt`: status da placa depois do apply, self-test da
  versao instalada, player ativo, settings inativo e apply guard verde.
- `board/preview-copy-grep.txt`: prova textual sobre os SVGs gerados na placa.
- `direct-preview-svgs/`: galeria gerada diretamente na placa por
  `totem_setup_visual_wizard.py --preview-screens`.
- `direct-preview-svgs/0005-02-connection.svg`: etapa de Wi-Fi atualizada.

## Observacao

A conversao local de SVG para PNG nao foi anexada nesta rodada porque o ambiente
local nao tem o delegate `rsvg-convert` usado pelo ImageMagick. A evidencia
visual canonica desta rodada sao os SVGs gerados diretamente na placa.

## Non-Claims

- Nao altera Wi-Fi real, NetworkManager ou credenciais.
- Nao altera player-runtime, midias, MPV, kernel ou imagem base.
- Nao promove `stable` nem muda politica de auto-pull.
