# Fase A - conclusao em desenvolvimento

Status: concluida em desenvolvimento. Ainda nao e homologacao de producao.

Data: 2026-05-01

## Objetivo

Consolidar a Fase A de status/splash local minimo. A fase provou que o totem
consegue publicar estado publico sanitizado e exibir uma primeira tela Dadooh
para `config_missing` sem quebrar o player validado por DRM/KMS.

A conclusao vale para a placa de desenvolvimento. A homologacao `v0.1-rc1`
continua sendo uma frente separada.

## Entregas

### A0 - contrato e preview local

- Contrato publico de status definido em `STATUS_CONTRACT_V0.md`.
- Estados publicos iniciais documentados: `booting`, `display_missing`,
  `config_missing`, `starting_player`, `player_running`, `player_error` e
  `maintenance_placeholder`.
- Preview SVG local criado sem MPV, sem internet, sem systemd e sem acesso a
  DRM/KMS.
- Politica de privacidade estabelecida: status e tela nao devem conter config
  privada, URLs privadas, IDs privados, payloads privados, SSID, senha ou paths
  reais de midia.

### A1.1 - status aggregator

- `totem_status_aggregate.py` implementado.
- Geracao de `/tmp/dadooh-status/status.json`.
- Geracao de `/tmp/dadooh-status/status.svg`.
- Agregacao baseada em status bruto do launcher e status do player, sem ler a
  config privada.
- Saida publica reduzida a campos controlados e sanitizados.

### A1.2 - integracao com launcher

- Launcher passou a chamar o agregador apos escrever status bruto.
- Estados `starting`, `display_missing`, `running`, `app_exited` e `stopped`
  passaram a produzir status publico.
- Falha do agregador ficou best-effort, com warning simples e sem derrubar o
  launcher.
- Ainda sem renderer visual nessa subfase.

### A1.2.1 - refresh do status enquanto player roda

- Adicionado refresh periodico do agregador enquanto o processo do player esta
  vivo.
- Corrigida a convergencia de `starting_player` para `player_running` apos o
  status do player passar a indicar playback.
- Fluxo sem HDMI permaneceu em `display_missing` sem app/MPV.

### A1.3 - config_missing seguro

- Launcher passou a validar config minima antes de iniciar `kiosk.py`.
- Config ausente, ilegivel, JSON invalido ou incompleta publica
  `config_missing`.
- Em `config_missing`, o servico permanece `active`, `kiosk.py` nao inicia e o
  MPV principal nao inicia.
- A config real nao e impressa nem copiada para status publico.

### A1.4 - renderer visual experimental

- `totem_status_renderer.sh` criado para exibir o SVG publico por MPV via
  DRM/KMS.
- Renderer habilitado inicialmente apenas em `config_missing`.
- Renderer nao roda junto com o MPV principal do player.
- Antes de iniciar `kiosk.py`, o launcher para o renderer, aguarda sua saida e
  bloqueia o player se nao conseguir liberar o processo visual.
- `display_missing` garante renderer parado e nao tenta desenhar.

## Evidencias principais

Rodadas de referencia:

- `20260501-123806-status-aggregator-hdmi-missing`;
- `20260501-132142-status-aggregator-refresh-hdmi`;
- `20260501-141332-status-aggregator-config-missing`;
- `20260501-145916-status-renderer-config-missing`.

Resultado consolidado da A1.4 na placa de desenvolvimento:

- `config_missing` mostrou tela Dadooh/configuracao pendente.
- `kiosk.py=0` durante `config_missing`.
- MPV principal `0` durante `config_missing`.
- Renderer script `1` e MPV do renderer `1` durante `config_missing`.
- Player e renderer nao rodaram juntos.
- Apos restaurar config valida, renderer `0`, `kiosk.py=1` e MPV principal
  `1`.
- Observer de 180s apos restauracao: `180/180` IPC success, `0` timeout,
  `0` erro e `5/5` aliases avancando.
- `systemctl --failed=0`.
- Filtro critico de kernel `0`.
- Status publico e SVG passaram na checagem de sanitizacao.

## Limites atuais

- O renderer visual esta validado apenas para `config_missing`.
- `player_error` existe no contrato e no preview, mas ainda nao foi habilitado
  no renderer operacional.
- `display_missing` e um estado publico local; sem display fisico, nao ha tela
  para renderizar ate o HDMI voltar.
- O layout visual ainda e simples e tecnico.
- Nao ha rotacao visual validada para telas verticais.
- Nao ha manutencao local operavel por celular.
- Diagnosticos brutos continuam potencialmente sensiveis e ficam fora do Git.
- Validacao foi curta e controlada; teste longo continua pendente.

## Ainda nao e onboarding

A Fase A nao implementa:

- Wi-Fi setup;
- hotspot Dadooh Setup;
- QR code funcional;
- portal local;
- ativacao por backend;
- escrita de config por operador;
- manutencao completa;
- reset leve operacional;
- factory reset real;
- telemetria;
- producao.

## Riscos remanescentes

- Disputa DRM/KMS continua sendo o risco principal sempre que houver renderer
  visual e MPV do player.
- Qualquer novo estado visual precisa preservar a ordem: renderer para antes do
  player iniciar.
- Campos novos em status bruto podem carregar dado privado se forem copiados
  sem allowlist.
- `player_error` pode entrar em loop visual se for habilitado sem regra clara
  de retry e observabilidade.
- Melhorias visuais podem quebrar legibilidade se nao forem validadas em 16:9
  e nos tamanhos de tela esperados.

## Criterios para nao regredir

Antes de considerar qualquer mudanca futura aceitavel:

- `display_missing` nao pode iniciar `kiosk.py`, MPV principal ou renderer.
- `config_missing` nao pode iniciar `kiosk.py` ou MPV principal.
- `player_running` nao pode manter renderer ativo.
- Renderer deve encerrar antes do player tomar DRM/KMS.
- Se renderer nao parar, launcher deve bloquear o player e registrar erro
  controlado.
- `status.json` e `status.svg` nao podem conter secrets, URLs privadas, IDs
  privados, payloads privados, SSID, senha ou paths reais de midia.
- Apos restaurar config valida, player deve voltar a `playing` com IPC sem
  timeout em observer curto.
- `systemctl --failed` deve permanecer em `0`.
- Filtro critico de kernel deve permanecer limpo para os termos ja usados nas
  rodadas de bancada.
