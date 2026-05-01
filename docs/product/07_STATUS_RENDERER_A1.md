# Status Renderer A1.4

Status: implementacao experimental para validacao local e placa de
desenvolvimento.

Data: 2026-05-01

## Objetivo

Implementar um renderer visual minimo para exibir o SVG publico do status
Dadooh na tela quando o player nao deve rodar. A primeira integracao operacional
usa o estado `config_missing`.

O renderer e um processo separado do `kiosky-player`. Ele nao inicia
`kiosk.py`, nao le config privada, nao acessa internet e nao altera arquivos em
`/opt`.

## Escopo

Incluido:

- script `totem_status_renderer.sh`;
- exibicao de `/tmp/dadooh-status/status.svg` por MPV via DRM/KMS;
- integracao no launcher para iniciar o renderer em `config_missing`;
- parada obrigatoria do renderer antes de iniciar o player;
- testes locais com renderer fake.

Fora do escopo:

- onboarding Wi-Fi;
- hotspot;
- QR code;
- portal local;
- configuracao de ambiente;
- manutencao completa;
- telemetria;
- producao.

## Regra DRM/KMS

O renderer visual nunca deve rodar ao mesmo tempo que o MPV principal do
player. DRM/KMS e tratado como recurso exclusivo nesta fase.

Antes de iniciar `kiosk.py`, o launcher:

1. envia `TERM` ao renderer, se ele estiver ativo;
2. aguarda a saida por `TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC`;
3. envia `KILL` se o processo nao sair no prazo;
4. so inicia o player se o renderer tiver encerrado.

Se o renderer continuar ativo apos a tentativa de parada, o launcher registra
erro controlado e nao inicia o player.

## Estados Que Renderizam

Na A1.4, apenas `config_missing` inicia o renderer.

Esse estado acontece quando ha display conectado, mas a config minima nao esta
presente, nao e legivel, nao e JSON valido ou nao contem os campos essenciais
para o player. O launcher publica o status bruto, chama o agregador, gera
`status.json` e `status.svg`, inicia o renderer se houver SVG disponivel e segue
tentando novamente no intervalo configurado.

O script do renderer tambem e adequado para `player_error`, mas esse estado nao
foi habilitado nesta subfase.

## Estados Que Nao Renderizam

- `display_missing`: nao ha tela fisica; o launcher garante o renderer parado.
- `starting_player`: o renderer deve estar encerrando ou ja encerrado.
- `player_running`: o renderer nao deve estar ativo.
- `booting`: ainda nao habilitado como tela visual nesta subfase.
- `maintenance_placeholder`: reservado para fase futura.

## Integracao Com Launcher

Variaveis novas:

- `TOTEM_STATUS_RENDERER`, padrao `/opt/totem/bin/totem_status_renderer.sh`;
- `TOTEM_STATUS_SVG`, padrao `/tmp/dadooh-status/status.svg`;
- `TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC`, padrao `3`;
- `TOTEM_STATUS_RENDERER_WARN_INTERVAL_SEC`, padrao `60`.

Funcoes novas:

- `start_status_renderer`;
- `stop_status_renderer`.

`start_status_renderer` e best-effort. Ele so inicia se houver display
conectado, se o player nao estiver rodando, se o SVG existir e se o renderer
estiver executavel. Falhas geram warning simples e nao derrubam o launcher.

`stop_status_renderer` e mandataria antes do player. Ela retorna falha se o
processo visual nao puder ser encerrado, e nesse caso o app nao e iniciado.

## Comportamento Em Falha

- Renderer ausente: warning simples, launcher continua ativo, app continua
  bloqueado em `config_missing`.
- SVG ausente: renderer nao inicia; launcher continua tentando.
- Renderer lento: launcher aguarda o timeout e envia `KILL`.
- Renderer que nao encerra: launcher nao inicia `kiosk.py` e publica erro
  controlado.
- Agregador ausente ou lento: comportamento A1.2/A1.3 permanece best-effort;
  isso nao deve derrubar o launcher.

## Criterios De Aceite

- `config_missing` com HDMI conectado gera `status.json` e `status.svg`.
- Renderer fica ativo em `config_missing`.
- `kiosk.py` nao roda durante `config_missing`.
- MPV principal do player nao roda durante `config_missing`.
- Ao restaurar config valida, o renderer para antes do player iniciar.
- `player_running` nao tem renderer ativo.
- `display_missing` nao tenta renderizar.
- `systemctl --failed` permanece sem falhas.
- Status publico e SVG nao contem secrets, URLs privadas, IDs privados, SSID,
  payloads privados ou paths reais de midia.

## Rollback

Rollback operacional:

1. remover ou renomear `/opt/totem/bin/totem_status_renderer.sh`;
2. reiniciar `kiosky-player.service`.

Como `start_status_renderer` e best-effort, renderer ausente nao impede o
launcher de continuar publicando `config_missing`. Para voltar ao comportamento
A1.3 puro, tambem e possivel reimplantar o launcher anterior sem as chamadas de
start/stop do renderer.

Rollback e considerado aprovado se:

- config valida volta para `player_running`;
- sem HDMI continua `display_missing`;
- config ausente continua sem iniciar `kiosk.py` ou MPV principal.

## Proximos Passos

- validar visualmente `config_missing` na placa de desenvolvimento;
- decidir se `player_error` deve usar o mesmo renderer;
- refinar layout do SVG sem alterar contrato publico;
- manter onboarding, QR code e manutencao para fases posteriores.
