# ADR-0007 - Launcher, status agregado e splash Dadooh

## Status

Aceito em desenvolvimento. Ainda nao e homologacao e nao libera producao.

## Contexto

A homologacao `v0.1-rc1` congelou a configuracao candidata do player manual
apos a rodada de 300s com IPC/loadfile estaveis e todos os aliases avancando.
Depois disso, na placa de desenvolvimento, a frente status/splash validou
`systemd`, boot automatico, HDMI ausente/reconexao, status agregado,
`config_missing` e renderer visual Dadooh para a tela B1.

O problema de produto restante nao e apenas tocar midia. O totem precisa
explicar estados locais sem terminal, sem expor dados privados e sem quebrar o
caminho DRM/KMS ja validado para o MPV principal.

## Decisao

- `systemd` inicia o launcher do appliance.
- O launcher supervisiona display, config e player.
- O status aggregator publica estado publico sanitizado em JSON/SVG.
- O renderer so roda quando o player nao deve rodar.
- O renderer deve parar antes do MPV principal iniciar.
- `config_missing` mostra uma tela Dadooh de configuracao pendente.
- `display_missing` nao tenta renderizar sem display.
- O `kiosky-player` permanece focado em playlist, cache, MPV, watchdog e status
  proprio.

## Alternativas consideradas

### Player como configurador

Adicionar Wi-Fi, ativacao e manutencao ao `kiosky-player` reduziria o numero de
processos, mas misturaria responsabilidades e aumentaria o risco de regressao
no loop de reproducao.

### Renderer sempre ativo

Manter um renderer permanente simplificaria a troca de telas, mas criaria
disputa continua por DRM/KMS com o MPV principal. O caminho aceito e iniciar o
renderer somente quando o player deve ficar parado.

### Chromium/compositor

Chromium, desktop ou compositor facilitariam UI rica, mas adicionariam uma stack
grafica nao validada, maior consumo e nova superficie de falha. Permanecem fora
desta fase.

### Terminal/manual

Operacao por terminal e suficiente para bancada, mas nao atende operador nao
tecnico e aumenta risco de vazamento ou digitacao incorreta de dados privados.

## Consequencias

- A decisao preserva o caminho MPV via DRM/KMS direto.
- Estados locais ficam legiveis sem iniciar o player quando ele nao deve rodar.
- O status publico passa a ser contrato entre launcher, renderer, suporte e
  fases futuras.
- Qualquer novo estado visual precisa respeitar a ordem de processos: renderer
  fora antes do player.
- A manutencao futura deve operar sobre comandos limitados e estado publico, nao
  sobre shell arbitrario.

## Riscos

- Disputa DRM/KMS se o renderer nao parar antes do MPV principal.
- Vazamento de dado privado se campos novos escaparem da allowlist do status.
- `player_error` ainda nao tem validacao operacional de retry/render.
- Ruido amplo de kernel na rodada B1 exige revisao antes de decisao de
  producao.
- Onboarding Wi-Fi/configuracao ainda nao existe e pode exigir novas decisoes
  de rede, seguranca e persistencia.

## Validacoes

- [Observer com saida MPV explicita](../evidence/candidate-a/runs/20260430-133130-kiosky-playback-observer-explicit-mpv-output/README.md):
  base da RC1 aprovada por 300s.
- [Systemd dev smoke](../evidence/candidate-a/runs/20260430-174718-systemd-dev-smoke/README.md):
  start/stop controlado aprovado.
- [Systemd dev autoboot](../evidence/candidate-a/runs/20260430-185824-systemd-dev-autoboot/README.md):
  boot automatico aprovado na placa de desenvolvimento.
- [Systemd dev HDMI missing](../evidence/candidate-a/runs/20260430-194110-systemd-dev-hdmi-missing/README.md):
  `display_missing` sem app/MPV e recuperacao apos reconexao.
- [Status aggregator refresh HDMI](../evidence/candidate-a/runs/20260501-132142-status-aggregator-refresh-hdmi/README.md):
  status agregado converge para `player_running`.
- [Status aggregator config_missing](../evidence/candidate-a/runs/20260501-141332-status-aggregator-config-missing/README.md):
  config ausente/invalida bloqueia player.
- [Status renderer config_missing](../evidence/candidate-a/runs/20260501-145916-status-renderer-config-missing/README.md):
  renderer e player nao rodam juntos.
- [Status renderer visual B1](../evidence/candidate-a/runs/20260501-190932-status-renderer-visual-b1/README.md):
  tela B1 validada por observacao humana e restauracao para player limpa.

## Proximos passos

1. Manter a homologacao `v0.1-rc1` separada.
2. Revisar o ruido amplo de kernel da rodada B1 antes de qualquer decisao de
   producao.
3. Planejar C0: onboarding Wi-Fi/configuracao, sem implementar hotspot, portal
   ou ativacao backend ainda.
4. Validar `player_error` visual em rodada propria antes de habilitar
   operacionalmente.
5. Levar teste longo, root read-only, corte seco, monitoramento, update e
   rollback para fases posteriores com criterios proprios.
