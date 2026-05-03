# Status Atual

Data: 2026-05-01

Atualizacao C6.5: 2026-05-02.

## Estado consolidado atual

### Atualizacao de desenvolvimento - C6 config real + player_running

C6 avancou em desenvolvimento depois da documentacao de status/splash B1. A
rodada C6.3A escreveu a config real em `/data/config/config.json` com
`kiosky-player.service` parado, backup restrito, validacao `real-dry-run` e
permissoes observadas `root:totem` `0640`. O usuario `totem` le a config e nao
grava nela. Nenhum conteudo da config real, token, `api_url` real, IDs reais ou
payload foi publicado.

C6.4 iniciou o servico controladamente com a config real ja escrita e passou em
smoke curto de desenvolvimento: observer de 120s, estado publico
`player_running`, playback `playing`, MPV ativo, `kiosk.py` ativo e
`NRestarts=0`. Renderer junto com player nao foi observado na checagem final.

Testes longos foram movidos para fila de homologacao separada:
`docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md`. Producao continua
bloqueada. A homologacao `v0.1-rc1` continua frente separada e nao e
substituida por C6.3A/C6.4.

Consolidacao: `docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md`.

### Homologacao v0.1-rc1

A homologacao `v0.1-rc1` permanece uma frente propria, separada do
desenvolvimento posterior. Ela congela a configuracao candidata validada no app
real por 300s com `mpv_query_uses_fresh_ipc=true`, `mpv_vo=gpu`,
`mpv_gpu_context=drm`, `mpv_ao=null` e `low_resource_mode=false`.

Essa homologacao ainda deve ser reproduzida em segunda placa/cartao e nao
inclui automaticamente os avancos posteriores de `systemd`, launcher,
status/splash ou B1 visual.

### Desenvolvimento pos-RC1

Na placa de desenvolvimento, depois da definicao da RC1, foram validados
`systemd` start/stop, boot automatico, HDMI ausente/reconexao, status aggregator
com refresh periodico, `config_missing`, renderer visual Dadooh e a tela B1
"Configuracao pendente" por observacao humana. Player e renderer nao rodam
juntos no caminho validado; ao restaurar config valida, o sistema volta para
`player_running`.

Esses resultados sao marco de desenvolvimento, nao homologacao e nao producao.
Consolidacao: `docs/product/11_MARCO_DESENVOLVIMENTO_STATUS_SPLASH.md`.

### Producao futura

Producao continua bloqueada. Ainda faltam homologacao completa, teste longo,
revisao do ruido amplo de kernel da rodada B1, validacao visual de
`player_error`, onboarding Wi-Fi/configuracao, hotspot, portal local, ativacao
backend, root read-only, corte seco, monitoramento, update e rollback.

Nota posterior: C0 foi o proximo passo historico naquele momento, mas a frente
produto/UX ja avancou por C1/C2/C3/C4/C5/C6. Novas sessoes devem escolher a
proxima frente a partir do roadmap produto/UX atual, do marco C6.5 e da fila de
homologacao, sem assumir automaticamente C0 como proxima fase.

Nota C0: a frente de onboarding deve comecar por documentacao e arquitetura.
Wi-Fi setup, hotspot, portal local, QR funcional, ativacao backend e escrita
de config pelo fluxo de onboarding/operador continuam nao implementados. A
escrita tecnica controlada de config real ja foi validada em C6.3A/C6.4 como
marco de desenvolvimento, nao homologacao e nao producao. A homologacao
`v0.1-rc1` segue separada.

## Resumo executivo

O Candidato A avancou da validacao de base para uma versao de homologacao `v0.1-rc1`, ainda nao producao. A placa passou por boot inicial, reboots curtos, rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, layout `/data`, Wi-Fi cliente 5 GHz e desativacao dos servicos Bluetooth conhecidos sem regressao observada. O Wi-Fi cliente 5 GHz permaneceu funcional apos as desativacoes de Bluetooth/AW859A. Tambem foi feita a preparacao inicial de usuario/diretorios para o `kiosky-player`, a instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, a garantia de `/tmp/kiosky`, a aprovacao do `check_app_prereqs.sh` e o teste manual de MPV via DRM/KMS com confirmacao visual HDMI.

O app ja foi deployado em `/opt/totem/kiosky-player`, a config privada ja foi criada em `/data/config/config.json` fora do Git, e o `kiosk.py` ja rodou manualmente como usuario `totem`. O app baixou midias em `/data/media/kiosky-player`, criou estado em `/data/state/kiosky-player`, criou status em `/tmp/kiosky-status.json`, nao escreveu em `/opt/totem/kiosky-player` durante os probes e encerrou sem processos reais remanescentes depois do timeout controlado.

Ainda nao ha homologacao para producao. A camada OS continua saudavel: `systemctl --failed` permaneceu em `0 loaded units listed` e as rodadas recentes nao mostraram `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`. O bloqueio app-MPV curto foi resolvido para a candidata atual: `mpv_query_uses_fresh_ipc=true` estabilizou IPC, pings, restart e `loadfile`, e a saida explicita `--vo=gpu --gpu-context=drm --ao=null` fez todos os 5 aliases avancarem `time-pos` e `estimated-frame-number` no app real por 300s. A configuracao aprovada na rodada `20260430-133130` vira base da homologacao `v0.1-rc1` em segunda placa/cartao.

Atualizacao da placa de desenvolvimento: apos a definicao da RC1, o servico
`kiosky-player.service` foi validado com `systemd` em start/stop controlado,
autoboot com HDMI conectado e launcher para HDMI ausente/reconexao. Sem HDMI, o
launcher registra `display_missing` e nao inicia app/MPV; ao reconectar HDMI, o
app inicia automaticamente. Essa validacao nao muda o escopo da homologacao
`v0.1-rc1`, que continua separada em outra placa/cartao.

A Fase A de produto/UX foi concluida em desenvolvimento. O agregador de status
gera `/tmp/dadooh-status/status.json` e `status.svg`; o launcher publica
`display_missing`, `config_missing` e `player_running`; e o renderer visual
experimental A1.4 exibiu a primeira tela Dadooh para `config_missing`. Depois,
B1 refinou a tela publica para "Configuracao pendente" e foi validada por
observacao humana na placa de desenvolvimento. Ao restaurar a config valida, o
renderer parou antes do player, o app voltou a `playing`, o observer curto teve
IPC success, `0` timeout e `5/5` aliases avancando.

A frente C0 foi recomendada como proximo passo historico apos B1; depois disso,
C1-C6 avancaram como desenvolvimento produto/UX. Wi-Fi setup, hotspot, portal
local e ativacao backend continuam nao implementados. A homologacao `v0.1-rc1`
permanece separada.

## Composicao do Candidato A

- Armbian Build v25.11.
- Debian Bookworm Minimal.
- Orange Pi Zero 3.
- Kernel `6.12.58-current-sunxi64`.
- U-Boot `2025.04`.
- BSP congelado com `BSPFREEZE=yes`.
- Rede gerenciada por NetworkManager.
- Desktop ausente.

## O que foi aprovado

- Boot inicial.
- Reboots curtos.
- Baseline de rede cabeada/NetworkManager.
- Stress leve CPU/RAM de 30 minutos.
- Criacao idempotente do layout `/data`.
- Wi-Fi cliente 5 GHz com conexao NetworkManager existente, mantido funcional apos desabilitar Bluetooth/AW859A.
- Desativacao de `bluetooth.service` sem regressao observada.
- Desativacao de `aw859a-bluetooth.service` com `systemctl --failed` voltando para `0 loaded units listed`.
- Criacao de usuario/grupo `totem` e diretorios iniciais para a aplicacao.
- Instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, sem upgrades/removes e sem tocar em kernel/Armbian.
- `/tmp/kiosky` criado como `totem:totem`, modo `0750`.
- `check_app_prereqs.sh` aprovado apos o runtime minimo e a garantia de `/tmp/kiosky`.
- MPV manual aprovado via DRM/KMS direto, com `vo=drm` e `vo=gpu --gpu-context=drm` funcionando como root e como usuario `totem`, e com confirmacao visual HDMI.
- Deploy manual do `kiosky-player` em `/opt/totem/kiosky-player`.
- Criacao da config privada em `/data/config/config.json`, fora do Git e sem publicacao de secrets.
- Primeiro run manual do app como usuario `totem`, aprovado com ressalvas: o app iniciou, baixou midias, criou estado/status, exibiu algumas midias e permaneceu ativo ate o timeout controlado.
- Instrumentacao de diagnostico MPV/IPC e logs MPV por geracao, sem publicar conteudo sensivel.
- Confirmacao de que os probes manuais nao escreveram em `/opt/totem/kiosky-player`.
- Confirmacao recorrente de `systemctl --failed` em `0 loaded units listed` nas rodadas de app.
- Confirmacao recorrente de ausencia de `Oops`, `panic`, erro EXT4, remount read-only e `mmc timeout/reset` nas rodadas de app.
- `mpv_query_uses_fresh_ipc=true` validado como candidata principal para estabilizar consultas IPC do watchdog: `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0` e `Failed to load media=0` na rodada fresh IPC.
- Midias e transicoes manuais testadas sem evidencia de corrupcao de arquivo ou falha basica de DRM/KMS.
- Matriz de flags MPV isolou a menor alteracao candidata atual: saida explicita `--vo=gpu --gpu-context=drm --ao=null`.
- Observer de 300s do app real aprovado com commit `c71318a`, `mpv_query_uses_fresh_ipc=true`, `mpv_vo=gpu`, `mpv_gpu_context=drm`, `mpv_ao=null` e `low_resource_mode=false`: timeouts, falhas de ping, restarts e falhas de load ficaram em 0; todos os 5 aliases avancaram `time-pos` e frame.
- `systemd` start/stop aprovado na placa de desenvolvimento com HDMI conectado.
- Autoboot aprovado na placa de desenvolvimento em dois reboots controlados com HDMI conectado.
- Launcher de HDMI ausente aprovado na placa de desenvolvimento: `display_missing` sem app/MPV no boot sem HDMI e inicio automatico apos reconexao.
- Agregador de status A1 aprovado em desenvolvimento: status publico
  sanitizado em `/tmp/dadooh-status/status.json` e SVG publico em
  `/tmp/dadooh-status/status.svg`.
- `config_missing` aprovado em desenvolvimento: config ausente/invalida nao
  inicia `kiosk.py` nem MPV principal e mantem o servico `active`.
- Renderer visual A1.4 aprovado em desenvolvimento para `config_missing`:
  tela Dadooh/configuracao pendente observada, renderer e MPV principal nao
  rodaram juntos, restauracao voltou para `player_running`, observer de 180s
  teve `180/180` IPC success, `0` timeout e `5/5` aliases avancando.
- B1 visual aprovado em desenvolvimento: tela publica "Configuracao pendente"
  observada por humano, sem QR funcional, sem onboarding, sem hotspot, sem
  portal, sem ativacao backend e sem mudanca no `kiosky-player`.

## Rodadas recentes do kiosky-player

- Primeiro run manual: app iniciou como `totem`, atualizou playlist, baixou 5 arquivos de midia, criou estado/status e exibiu algumas midias. Aprovado com ressalvas por 21 `MPV IPC unresponsive` e 5 `Failed to load media`.
- Analise do primeiro run: reforcou a hipotese de watchdog/IPC/restart, com base saudavel e status final `playing`/`mpv_running=true`.
- Run instrumentado: adicionou `mpv_log_file`, `mpv_msg_level` e `mpv_debug_events`; manteve 21 `MPV IPC unresponsive`, aumentou falhas de load para 10 e mostrou 31 restarts/32 processos MPV.
- Logs por geracao: preservou 32 logs `mpv-g*.log`; `MPV IPC startup wait complete` foi 32/32, enfraquecendo falha de startup do IPC e concentrando o problema na responsividade posterior.
- A/B timeout IPC 5s: reduziu levemente pings/timeouts, mas manteve 31 restarts/32 processos MPV e piorou `Failed to load media` para 13; timeout agressivo puro ficou menos provavel.
- Watchdog threshold 2: reduziu `Restarting MPV` de 31 para 18, `MPV process started` de 32 para 19 e `Failed to load media` de 10 para 7; confirmou que watchdog agressivo era parte do problema.
- Threshold 2 com reset por geracao: corrigiu a semantica do contador e trouxe ganho pequeno; restaram timeouts e 3 `Bad file descriptor`.
- Coordenacao IPC/restart com commit `9bdb38c`: zerou `Bad file descriptor` e `MPV IPC command send failed`, reduziu `Restarting MPV` para 13, `MPV process started` para 14, `Failed to load media` para 2 e `Media load retry failed` para 0. Naquele momento, o problema remanescente ainda era `MPV IPC ping failed`/`MPV IPC command timeout` frequente.
- Midia isolada suspeita: o alias `<media-path:e7efe47f02>` tocou com `vo=null` e via DRM/KMS como usuario `totem`, encerrando por EOF; a hipotese de arquivo corrompido perdeu forca.
- Transicao manual de midia: `loadfile` sequencial controle -> suspeita -> controle retornou `success` para os tres aliases e nao reproduziu a falha anterior de `loadfile`.
- Playlist watchdog sem app: playlist completa, duracoes configuradas e pings concorrentes passaram com `loadfile success=5`, ping timeout 0 e base OS limpa.
- MPVController playlist probe: `load_file` passou 5/5 sem restart, mas `ping()` e `get_property()` pelo socket persistente do controller deram timeouts; isso apontou para a estrategia de IPC persistente.
- Fresh IPC query com commit `8c3b420`: `mpv_query_uses_fresh_ipc=true` estabilizou a rodada do app real, com `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1` e `Failed to load media=0`.
- Playback observer do app real: com IPC estabilizado, o observador externo mostrou que 4 aliases ficavam no primeiro frame, apesar de `pause=false`, `idle-active=false` e `eof-reached=false`; somente `<media-path:e7efe47f02>` avancou `time-pos` e frame.
- Flags progress probe: as 4 midias problematicas nao avancaram com flags app/low-resource atuais, nem removendo isoladamente `--correct-pts=no` ou `--video-sync=audio`; todas avancaram com o perfil simples aprovado.
- `low_resource_mode=false`: removeu as flags low-resource fortes do app, mas nao resolveu o problema visual; os mesmos 4 aliases continuaram sem avancar no app real.
- Remaining flags matrix: remover isoladamente `--loop-file=inf`, `--keep-open=yes`, `--image-display-duration=inf` ou adicionar `--no-config` nao resolveu; V5, adicionando `--vo=gpu --gpu-context=drm --ao=null`, fez os aliases problematicos avancarem e preservou o alias que ja funcionava.
- Observer do app real com saida MPV explicita e commit `c71318a`: a configuracao candidata passou por 300s com `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1`, `Failed to load media=0` e todos os 5 aliases avancando `time-pos`/frame. Sem `systemd`, sem escrita em `/opt`, sem processo remanescente real e com OS limpa.
- Systemd dev smoke: unit simples com launcher aprovada para `systemctl start/stop` na placa de desenvolvimento, com HDMI conectado, sem escrita em `/opt` e sem processo remanescente apos stop.
- Systemd dev autoboot: servico habilitado e aprovado em dois reboots controlados com HDMI conectado; observers curtos mantiveram IPC timeout 0, ping failed 0, restart 0 e 5/5 aliases avancando.
- Systemd dev HDMI missing: boot sem HDMI manteve o servico `active`, escreveu `display_missing`, nao iniciou `kiosk.py`/MPV e iniciou automaticamente apos reconexao HDMI.
- Status aggregator A1: status publico sanitizado gerado a partir do launcher e
  player, com refresh periodico enquanto o player esta vivo para convergir para
  `player_running`.
- Config missing A1.3: override temporario de config inexistente na placa de
  desenvolvimento resultou em `config_missing`, servico `active`,
  `kiosk.py=0`, MPV principal `0`, `status.json` e `status.svg` gerados e
  sanitizacao OK.
- Status renderer A1.4: renderer MPV separado exibiu o SVG publico em
  `config_missing`; durante esse estado, `kiosk.py=0`, MPV principal `0`,
  renderer script `1` e MPV do renderer `1`. Apos remover o override
  temporario, renderer `0`, `kiosk.py=1`, MPV principal `1`, app `playing`,
  `systemctl --failed=0` e filtro critico de kernel `0`.
- Status renderer visual B1: tela publica Dadooh "Configuracao pendente"
  validada por observacao humana. Em `config_missing`, `kiosk.py=0`, MPV
  principal `0`, renderer MPV `1`; apos restaurar config valida, renderer `0`,
  `kiosk.py=1`, MPV principal `1`, `systemctl --failed=0` e observer curto com
  `180/180` IPC success, `0` timeout e `5/5` aliases avancando. O filtro amplo
  de kernel da rodada teve ruido nao bloqueante e precisa de revisao antes de
  qualquer decisao de producao.

## O que foi alterado na placa

- Criado layout persistente em `/data`.
- Criado usuario/grupo `totem`.
- Criados diretorios de aplicacao em `/opt/totem`, `/data/.../kiosky-player` e `/tmp/kiosky`.
- Ajustado ownership de diretorios mutaveis para `totem:totem` onde previsto.
- Usuario `totem` adicionado aos grupos existentes `audio`, `video` e `render`.
- Instalados pacotes de runtime `mpv`, `ffmpeg` e `python3-requests` com `--no-upgrade --no-install-recommends`.
- Criado `/tmp/kiosky` como `totem:totem`, modo `0750`.
- `bluetooth.service` foi desabilitado.
- `aw859a-bluetooth.service` foi desabilitado e o estado falhado foi limpo.
- Deployado `kiosky-player` em `/opt/totem/kiosky-player`, com a rodada aprovada usando commit `c71318a Add configurable MPV output flags`.
- Criada config privada em `/data/config/config.json`, fora do Git.
- Atualizados temporariamente campos de diagnostico/controle da config privada para probes curtos, sem publicar conteudo da config.
- Criados/preservados arquivos de midia em `/data/media/kiosky-player`.
- Criados/preservados arquivos de estado em `/data/state/kiosky-player`.
- Criado/copiado status temporario em `/tmp/kiosky-status.json` durante os probes.
- Criados logs temporarios do MPV em `/tmp/kiosky` durante as rodadas instrumentadas.
- Na placa de desenvolvimento, instalada unit `kiosky-player.service` e launcher `kiosky_service_launcher.sh` para validacao controlada de `systemd`, autoboot e HDMI ausente.
- Na placa de desenvolvimento, deployado o agregador de status e o renderer
  visual experimental em `/opt/totem/bin` para validacao A1.4.

Nenhum comando `apt` foi executado nas rodadas recentes de app/systemd. A auditoria dos probes nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app. A placa de homologacao continua tratada separadamente.

## O que ainda esta pendente

- `pip` ausente por decisao desta fase.
- `/opt/totem/venv` ainda sem `bin/python` e `bin/pip` executaveis, esperado enquanto `python3-pip`/venv ficam fora.
- `python3-pip` e `python3-venv` continuam fora desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase; nao ha indicacao atual para instala-los apos o teste MPV via DRM/KMS.
- Homologar a configuracao `v0.1-rc1` em uma segunda placa/cartao.
- Repetir observer de 300s na segunda placa/cartao com a config candidata aprovada.
- Fazer teste manual observado de 30 a 60 minutos na homologacao.
- Repetir validacao de `systemd`/autoboot/HDMI ausente na placa de homologacao antes de qualquer producao.
- Desenvolver a frente produto/UX/onboarding sem misturar com os criterios da RC1.
- Escolher proxima frente de produto/UX a partir do roadmap atual e do marco
  C6.5, sem assumir C0 como proxima fase automatica.
- Documentar riscos e ADR proposta de onboarding antes de qualquer alteracao de
  NetworkManager, portal local ou escrita de config.
- Revisar ruido amplo de kernel da rodada B1 antes de qualquer decisao de
  producao.
- `player_error` visual ainda nao validado operacionalmente.
- Monitoramento, update e rollback ainda pendentes.
- Teste longo do app ainda nao liberado.
- Root read-only ainda nao validado.
- Corte seco ainda nao validado.

## Proximos 3 passos tecnicos

1. Manter a homologacao `v0.1-rc1` separada em segunda placa/cartao com a
   imagem base e o `kiosky-player` no commit `c71318a`.
2. Escolher a proxima frente de desenvolvimento a partir do roadmap atual:
   C7 diagnostico/status, C8 rollback/parada controlada, UX/setup/onboarding,
   `player_error`, integracao writer/onboarding ou update/rollback.
3. Tratar observer prolongado, reboot/autoboot, segunda placa/cartao, root
   read-only, corte seco e rollback real na fila de homologacao separada.

## Regras que continuam proibidas

Nao executar na placa:

- `apt upgrade`
- `apt full-upgrade`
- `apt dist-upgrade`
- `armbian-upgrade`

## Artefatos brutos

Os artefatos brutos `.tar.gz` permanecem fora do Git. Eles podem existir localmente como arquivos ignorados para auditoria, mas nao devem ser adicionados ao repositorio.
