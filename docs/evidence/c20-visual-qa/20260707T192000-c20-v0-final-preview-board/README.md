# C20 V0 Orientation Preview Overlap

Data: 2026-07-07.

Objetivo: validar na placa real a correcao de sobreposicao entre o preview de
orientacao e o painel lateral do wizard.

## Resultado

Status: validada para acumulo em `totem-core`.

- A tela de orientacao em paisagem foi renderizada na placa em `1024x768` sem o
  painel lateral invadindo o preview.
- A sequencia de preview tambem exibiu o caso em retrato sem sobreposicao.
- O runner de preview terminou com `rc=0`.
- A placa foi restaurada ao script original ativo antes do teste.
- O player voltou `active`, `player_running` e `playing`.
- Nao houve writer, Wi-Fi real, config real, OTA, publish ou alteracao
  persistente pretendida.

## Evidencia

- Captura decisiva da tela inicial corrigida:
  `remote-captures/preview-03-visible.jpg`.
- Captura de retrato sem sobreposicao:
  `remote-captures/preview-05-visible.jpg`.
- Estado antes: `status-before.txt`.
- Estado/restauracao: `session-session-status.json`.
- Self-test embarcado: `self-test.txt`.
- Hash do script antes, temporario e restaurado:
  `sha-before.txt`, `sha-temp.txt`, `sha-restored.txt`.

## Limites

- Esta rodada valida renderizacao visual por preview auto-exit na placa, nao um
  fluxo interativo completo por teclado.
- A tentativa de navegacao remota por escrita direta em `/dev/tty2` nao foi
  mantida como evidencia decisiva, porque nao simulou entrada de teclado de
  forma confiavel.
- O SVG local continua sendo evidencia auxiliar; a decisiva aqui e o framebuffer
  real convertido para `*-visible.jpg`.
