# Prod14 core stable and final reboot

Resultado: a imagem `c18-hwdecode-prod-14` completou o roundtrip real de
`totem-core` e o reboot final sem regressao observada no player.

## Escopo provado

- a release stable C21.12 foi publicada como `latest`, com seis assets
  baixados e conferidos por SHA256;
- o timer real, ja habilitado no boot, disparou e aplicou C21.12 sobre o
  C20.14 embutido;
- uma segunda execucao foi no-op: o SHA256 de `state.json`, `current`,
  `previous` e a invocacao do player permaneceram inalterados;
- o rollback governado restaurou C20.14 e a reaplicacao restaurou C21.12;
- os gates de apply, rollback e estado restaurado passaram sem blockers;
- apos reboot, C21.12 e C25B continuaram atuais, os dois timers ficaram
  habilitados/ativos, o player ficou ativo com zero restart e o freeze publico
  de `player-runtime` permaneceu em `rc=44`;
- o deep-health pos-reboot passou com 52 amostras, quatro episodios de video,
  quatro aliases MPV, transicoes observadas, HW decode
  `v4l2request-copy` em 52/52 amostras e zero falha de midia, MPV, servico,
  IPC, panfrost, MMC ou ext4;
- as tres chaves publicas SSH mantiveram os mesmos hashes antes e depois do
  reboot, e a configuracao privada continuou presente com modo `0640`.

## Diagnosticos preservados

O timer do core foi inicialmente habilitado depois que a janela `OnBootSec`
ja tinha passado. O systemd o mostrou como `active (elapsed)`, sem proximo
disparo, e nenhuma atualizacao ocorreu. Para provar o caminho real sem iniciar
o apply manualmente, a placa foi reiniciada com o timer habilitado; ele entao
disparou normalmente. O estado esta em `timer-enabled-elapsed-summary.json`.

`diagnostic-post-reboot-operation-gate.json` e vermelho apenas porque o gate
de operacao procura, no journal do boot atual, a tag e o sucesso do apply.
Depois do reboot esse journal de servico esta vazio. O mesmo gate passou nas
fases em que e aplicavel: `post-timer-gate.json`,
`rollback-complete-gate.json` e `restored-gate.json`. O diagnostico vermelho
nao e apresentado como gate final verde.

## Non-claims

- nao autoriza futuros alvos de `player-runtime` nem `latest` amplo do player;
- nao prova grupos de rollout, telemetria de frota ou assinatura consumida no
  device;
- nao atualiza MPV, ffmpeg, kernel, imagem base, midia ou configuracao por OTA;
- nao resolve a espera ocasional do portal de ativacao que exigiu `F5`; essa
  frente permanece registrada separadamente;
- nao transforma o gate operacional, dependente do journal do apply, em gate
  de persistencia pos-reboot.

## Arquivos principais

- `pre-summary.json`: C20.14 embutido antes da aplicacao;
- `post-timer-summary.json` e `post-timer-gate.json`: apply pelo timer real;
- `noop-before.txt`, `noop-after.txt` e `noop-summary.json`: no-op;
- `post-rollback-summary.json` e `rollback-complete-gate.json`: rollback;
- `restored-summary.json` e `restored-gate.json`: reaplicacao;
- `pre-final-reboot-state.json`: estado sanitizado antes do reboot;
- `post-reboot-core-summary.json`: core persistido apos reboot;
- `post-reboot-player.json` e `post-reboot-player-deep-health/`: player
  persistido e reproduzindo;
- `final-state.json`: estado final sanitizado;
- `operation-summary.json`: resumo estruturado da campanha;
- `remote-assets.sha256`: hashes dos seis assets publicados.
