# Estrategia produto/UX

Status: proposta tecnica para a proxima fase. Nao implementa mudancas.

Data: 2026-04-30

## Objetivo da fase produto

Transformar a base tecnica validada do totem em um produto operavel por pessoas
nao tecnicas. A proxima fase deve remover a dependencia de terminal para
operacao diaria, instalacao assistida, manutencao basica e recuperacao de
falhas comuns.

O alvo nao e criar uma interface completa de marketing. O alvo imediato e
garantir que o operador veja identidade visual Dadooh e caminhos claros para:

- configurar Wi-Fi;
- ativar ambiente, unidade e totem;
- ajustar rotacao de tela;
- entender inicializacao e falhas recuperaveis;
- reiniciar player ou placa;
- coletar diagnostico;
- executar reset leve ou factory reset;
- operar sem expor secrets, URLs privadas, IDs privados ou paths reais de
  midia.

## Estado tecnico atual

A base atual usa Armbian Build v25.11, Debian Bookworm Minimal e kernel
`6.12.58-current-sunxi64` na Orange Pi Zero 3. O runtime validado e minimo:
`mpv`, `ffmpeg` e `python3-requests`, sem desktop, sem Xorg, sem Wayland, sem
compositor e sem Chromium.

O `kiosky-player` foi validado com MPV via DRM/KMS direto. A configuracao
candidata estabilizou IPC/watchdog/loadfile com `mpv_query_uses_fresh_ipc=true`
e resolveu a progressao visual com `mpv_vo=gpu`, `mpv_gpu_context=drm` e
`mpv_ao=null`.

Na placa de desenvolvimento, a camada `systemd` avancou alem da RC1 manual:

- `systemctl start/stop` do `kiosky-player.service` aprovado com HDMI conectado;
- autoboot aprovado em dois reboots controlados com HDMI conectado;
- launcher aprovado para HDMI ausente/reconexao: sem HDMI, registra
  `display_missing` e nao inicia app/MPV; ao reconectar HDMI, inicia o app.

A homologacao `v0.1-rc1` em segunda placa/cartao continua sendo uma frente
separada. Ela deve validar reprodutibilidade antes de qualquer liberacao de
producao.

## Auditoria do que ja existe

### Launcher systemd atual

Arquivos no `orange_pi_totem`:

- `scripts/board/kiosky-player.service`
- `scripts/board/kiosky_service_launcher.sh`

A unit atual roda como `totem:totem`, usa `WorkingDirectory=/opt/totem/kiosky-player`,
define `PYTHONDONTWRITEBYTECODE=1`, `XDG_RUNTIME_DIR=/tmp/kiosky` e
`KIOSKY_RUNTIME_DIR=/tmp/kiosky`, cria `/tmp/kiosky` e
`/data/state/kiosky-player` no `ExecStartPre`, preserva `/opt/totem` como
somente leitura para o servico e permite escrita em `/data` e `/tmp`.

O launcher:

- verifica conectores DRM em `/sys/class/drm/*/status`;
- se houver display `connected`, inicia `/usr/bin/python3 /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json`;
- se nao houver display conectado, registra `display_missing`, atualiza status
  e aguarda nova tentativa;
- reinicia o app apos saida inesperada, mantendo o servico controlavel pelo
  `systemd`;
- trata `SIGTERM`/`SIGINT` para encerrar o filho.

### Status files existentes

Status do player:

- configurado por `status_file`;
- no perfil appliance e nas rodadas de bancada: `/tmp/kiosky-status.json`;
- escrito por `status_writer()` em intervalo configuravel;
- contem campos como `playback_state`, `mpv_running`, `playlist_size`,
  `current_index`, `current_item`, `next_item`, `consecutive_failures`,
  `last_poll_error`, `last_render_error`, `black_screen_risk_reason`,
  `blocked_media_count`, campos de sync e `uptime_sec`.

Status do launcher:

- alvo principal atual: `/data/state/kiosky-player/launcher-status.json`;
- fallback: `/tmp/kiosky-launcher-status.json`;
- campos atuais: `schema_version`, `updated_at`, `state`,
  `display_connected`, `last_app_exit_code` e `launcher_pid`;
- estados atuais observados: `starting`, `running`, `display_missing`,
  `app_exited` e `stopped`.

O consumidor futuro de UX deve tratar esses arquivos como fonte local e
sanitizar qualquer campo que possa conter URL, path real de midia, nome privado
ou payload privado.

### Config flags do kiosky-player

No `kiosky-player`:

- `config_ui_enabled`: padrao `true` no exemplo generico, `false` no appliance;
  quando ativo, sobe um HTTP server local para editar `environment_id` e
  `rotation_deg`.
- `hotkeys_enabled`: padrao `true` no exemplo generico, `false` no appliance;
  quando ativo, cria `hotkeys.conf` no `runtime_dir` e usa hotkey para abrir
  navegador local.
- `telemetry_enabled`: `false` nos exemplos atuais; quando ativo, envia payload
  para `telemetry_url` usando token do config ou `KIOSKY_TELEMETRY_TOKEN`.
- `sync_enabled`: padrao `true` no exemplo generico, `false` no appliance; com
  `false`, o player nao executa resync UTC nem comando NTP.

Leitura de produto: esses recursos existem, mas a UI atual do player nao deve
virar o configurador principal do appliance. Ela depende de navegador/hotkey e
nao resolve primeiro boot, Wi-Fi, ativacao segura, manutencao ou recovery.

### Scripts de reset/manutencao existentes

Nao ha script de factory reset, reset leve, painel de manutencao ou servico de
manutencao pronto para operador.

Ha scripts de provisionamento e bancada que podem ser reaproveitados como base
tecnica, mas nao sao UX de campo:

- `setup_data_layout.sh`
- `setup_app_dirs.sh`
- `setup_runtime_tmp.sh`
- `disable_bluetooth.sh`
- probes de MPV/player/systemd.

### Scripts de Wi-Fi existentes

Existem scripts de bancada:

- `scripts/board/wifi_snapshot.sh`: coleta estado Wi-Fi/NetworkManager;
- `scripts/board/wifi_client_test.sh`: testa subir uma conexao Wi-Fi ja salva.

Nao existe ainda:

- hotspot Dadooh Setup;
- portal local via celular;
- criacao/troca de credencial Wi-Fi por operador;
- fluxo para senha incorreta, rede indisponivel ou reconexao.

### Scripts de diagnostico existentes

Existem bons blocos de diagnostico de bancada:

- `scripts/board/collect_diag.sh`;
- `scripts/board/network_snapshot.sh`;
- `scripts/board/display_runtime_probe.sh`;
- observers do app e servico.

Eles geram artefatos brutos e `.tar.gz`, potencialmente sensiveis. Para produto,
precisam virar diagnostico sanitizado, acionavel por interface de manutencao e
com politica clara para baixar ou enviar pacote.

### Unit systemd atual

A unit atual efetiva para a placa fica em `scripts/board/kiosky-player.service`.
O `kiosky-player` tambem possui `scripts/linux/systemd/kiosky-system.service`,
mas esse arquivo e historico/generico para appliance e nao inclui o launcher de
HDMI ausente validado no `orange_pi_totem`.

## Principios

- Sem terminal para operador.
- Sem desktop, compositor ou Chromium por enquanto.
- Player separado de setup/manutencao.
- Tudo mutavel em `/data` ou `/tmp`.
- Sem secrets em logs, docs, status publico ou diagnostico compartilhavel.
- Recovery primeiro, beleza visual depois.
- Estado local deve ser legivel por humanos e por servicos pequenos.
- A UX deve degradar bem sem internet, sem HDMI, sem config ou com erro do
  player.
- O player deve continuar sendo um reprodutor robusto, nao um monolito de
  configuracao.

## Estados de tela desejados

- Boot/splash Dadooh: identidade visual imediatamente apos o sistema estar apto
  a desenhar na tela, escondendo terminal/logs.
- Inicializando: sistema subiu, servicos locais carregando, ainda sem promessa
  de reproducao.
- Aguardando HDMI: estado local registrado quando nao ha display. Como nao ha
  tela fisica nessa condicao, deve aparecer no status local, telemetria e
  manutencao; se o HDMI for conectado, a tela deve transicionar sem terminal.
- Sem internet: Wi-Fi/rede sem conectividade; mostrar acao simples para abrir
  setup local quando necessario.
- Configuracao ausente: sem `/data/config/config.json` valido ou sem ativacao;
  mostrar QR code/rede local de setup.
- Baixando midia: config valida, conectividade ok, preparando cache.
- Reproduzindo: player ativo; a UX visual pode sair de cena ou virar overlay
  minimo apenas quando necessario.
- Erro recuperavel: player falhou, midia invalida, API temporariamente fora,
  disco cheio parcial ou restart em andamento.
- Manutencao: modo local para ver estado, reiniciar player, reiniciar placa,
  baixar diagnostico e executar reset leve.
- Factory reset: fluxo explicito e protegido para limpar config, Wi-Fi,
  estado, cache opcional e voltar ao setup.

## Arquitetura proposta

### Launcher

Continua sendo o supervisor local do player e do estado de display. Deve evoluir
para escrever status mais rico, detectar config ausente e coordenar qual
componente aparece na tela: splash/status, setup, manutencao ou player.

O launcher nao deve carregar regras de negocio de ativacao, Wi-Fi ou portal. Ele
deve orquestrar estados e processos.

### Player

O `kiosky-player` continua focado em buscar playlist, baixar/cachear midias,
controlar MPV e escrever `/tmp/kiosky-status.json`.

Mudancas futuras no player devem ser pequenas e justificadas por contrato de
status/config. O setup nao deve depender de Ctrl+S, hotkey ou navegador aberto
por MPV.

### Status/splash

Novo componente local, leve e sem desktop/compositor, responsavel por mostrar
logo Dadooh e estado atual antes do player estar pronto ou quando o player nao
deve iniciar.

Opcoes a avaliar na fase A:

- renderizador simples em DRM/KMS/framebuffer;
- MPV exibindo assets locais estaticos, separado do player principal;
- imagem/splash de boot mais status posterior por servico local.

O criterio da fase A e confiabilidade: nao pode quebrar o player nem criar
disputa permanente pelo DRM.

### Setup Wi-Fi/config

Novo servico de setup por celular, acessivel por hotspot local Dadooh Setup
quando nao houver rede/config. Deve usar NetworkManager por baixo, sem expor
terminal.

Esse servico deve salvar apenas dados permitidos em `/data`, com permissoes
restritas e validacao de entrada. O operador nao deve digitar `api_key`.

### Manutencao/reset

Novo servico local para acoes limitadas:

- ver estado agregado;
- reiniciar player;
- reiniciar placa;
- baixar diagnostico sanitizado;
- reset leve;
- factory reset com confirmacao forte.

Nao deve permitir shell arbitrario.

### Telemetria

Telemetria de produto deve agregar status do launcher, player, rede, disco,
temperatura, versoes e ultimo erro. O `telemetry_enabled` do player pode ser
reaproveitado parcialmente, mas o produto precisa de telemetria do appliance,
nao apenas do loop de midia.

## O que reaproveitar

- Unit `scripts/board/kiosky-player.service` como base do servico principal.
- Launcher `scripts/board/kiosky_service_launcher.sh` como base para estados
  de display e orquestracao.
- `/tmp/kiosky-status.json` do player.
- `/data/state/kiosky-player/launcher-status.json` e fallback em `/tmp`.
- Config appliance com paths em `/data` e `/tmp`.
- `rotation_deg` e aplicacao de `video-rotate` no MPV.
- `strict_paths_enabled`.
- Offline fallback, cache, limites de download e limpeza do player.
- `collect_diag.sh`, `network_snapshot.sh`, `wifi_snapshot.sh` e observers como
  base para diagnostico sanitizado.
- Evidencias de MPV via DRM/KMS sem desktop/compositor.

## O que criar novo

- Contrato de status agregado do totem, sem dados privados.
- Componente status/splash Dadooh.
- Servico local de manutencao com API/comandos limitados.
- Hotspot Dadooh Setup e portal local.
- Fluxo de ativacao por codigo, trocado no backend por config segura.
- Escrita atomica e validada de `/data/config/config.json`.
- Reset leve e factory reset.
- Diagnostico sanitizado de produto.
- Telemetria do appliance com spool futuro se necessario.
- Politica de update/rollback em `/opt/totem/releases`.

## Riscos

- Disputa pelo DRM/KMS entre splash/status e MPV principal.
- Transformar o player em configurador e aumentar acoplamento.
- Expor secrets via status, diagnostico, logs ou portal local.
- Hotspot/setup interferir na rede do cliente ou no NetworkManager.
- Factory reset apagar evidencias necessarias para suporte.
- Estado persistente mal separado atrasar root read-only.
- Telemetria sem spool mascarar falhas de conectividade.
- UX bonita demais antes de recovery confiavel.
- RC1/homologacao e desenvolvimento de produto se misturarem e perderem
  rastreabilidade.

## Sequencia incremental recomendada

1. Definir contrato de status agregado e status/splash minimo.
2. Mostrar Dadooh + estado atual sem Chromium e sem onboarding.
3. Criar manutencao local basica para reinicio, diagnostico e reset leve.
4. Implementar hotspot/setup Wi-Fi por celular.
5. Implementar ativacao por codigo e provisionamento de config.
6. Integrar rotacao/resolucao com teste visual.
7. Consolidar telemetria do appliance.
8. Adicionar update/rollback.
9. Validar root read-only e corte seco somente depois que config, cache, logs e
   recovery estiverem estabilizados.
