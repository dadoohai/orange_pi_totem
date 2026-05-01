# Roadmap de implementacao produto/UX

Status: proposta incremental. Nao implementa mudancas.

Data: 2026-05-01

Este roadmap separa a evolucao de produto/UX da homologacao `v0.1-rc1`. A RC1
continua focada em reproduzir a base tecnica validada em outra placa/cartao. As
fases abaixo devem ser implementadas em passos pequenos, sempre mantendo o
player atual recuperavel.

## Fase A - status/splash local minimo

Status: concluida em desenvolvimento. Ver
`docs/product/08_FASE_A_CONCLUSAO.md`.

Objetivo:

- mostrar Dadooh e estado atual;
- esconder terminal/logs do operador;
- continuar sem Chromium, desktop ou compositor;
- ainda sem onboarding;
- nao quebrar o player.

Subfases concluidas em desenvolvimento:

- A0 - contrato/status/render preview: documentar o contrato sanitizado,
  detalhar estados publicos e criar preview local nao integrado;
- A1.1 - agregador de status: gerar `status.json` e `status.svg` publicos em
  `/tmp/dadooh-status`;
- A1.2 - integracao launcher: chamar agregador apos status bruto do launcher;
- A1.2.1 - refresh periodico: convergir `starting_player` para
  `player_running` enquanto o player esta vivo;
- A1.3 - `config_missing`: bloquear app/MPV quando a config minima nao existe
  ou nao e valida;
- A1.4 - renderer visual: exibir SVG publico em `config_missing` e parar antes
  do MPV principal do player.

Arquivos principais:

- `docs/product/03_FASE_A_STATUS_SPLASH.md`;
- `docs/product/STATUS_CONTRACT_V0.md`;
- `docs/product/04_STATUS_AGGREGATOR_A1.md`;
- `docs/product/05_LAUNCHER_STATUS_INTEGRATION_A1.md`;
- `docs/product/06_CONFIG_MISSING_A1.md`;
- `docs/product/07_STATUS_RENDERER_A1.md`;
- `docs/product/08_FASE_A_CONCLUSAO.md`;
- `scripts/board/kiosky_service_launcher.sh`;
- `scripts/board/kiosky-player.service`;
- `scripts/board/totem_status_render_preview.py`;
- `scripts/board/totem_status_aggregate.py`;
- `scripts/board/totem_status_renderer.sh`.

Validacao consolidada em desenvolvimento:

- `config_missing` mostra tela Dadooh/configuracao pendente;
- `kiosk.py=0` e MPV principal `0` enquanto renderer esta ativo;
- renderer e MPV principal nao rodam juntos;
- ao restaurar config valida, renderer para e player volta a `playing`;
- observer curto apos restauracao com IPC success, timeout `0` e `5/5`
  aliases avancando;
- boot sem HDMI continua em `display_missing` sem iniciar app/MPV;
- reconectar HDMI inicia app automaticamente;
- `systemctl --failed=0`;
- status publico sanitizado.

Riscos:

- disputa pelo DRM/KMS entre splash e MPV;
- splash atrasar ou bloquear o player;
- status mostrar dados privados.

Criterios de nao regressao:

- `display_missing` nao inicia app, MPV principal ou renderer;
- `config_missing` nao inicia app ou MPV principal;
- `player_running` nao mantem renderer ativo;
- renderer sempre para antes do player tomar DRM/KMS;
- status publico e SVG continuam sem dados sensiveis;
- metricas do player permanecem iguais as rodadas aprovadas.

Criterio de rollback:

- desabilitar o servico/componente de splash e voltar ao launcher atual que
  inicia apenas o player quando ha HDMI.

## Fase B - status visual e manutencao minima

Status: proxima fase planejada. Ver
`docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md`.

Objetivo:

- transformar a tela tecnica de `config_missing` em uma experiencia visual
  mais clara;
- padronizar mensagens e codigos publicos Dadooh;
- preparar area visual para QR code futuro, sem QR funcional ainda;
- definir manutencao minima antes de implementar comandos reais;
- manter a regra DRM/KMS validada na Fase A.

Escopo:

- melhorar `config_missing`;
- desenhar estados `player_error` e `maintenance_placeholder`;
- definir codigos publicos como `CONFIG_MISSING`, `DISPLAY_MISSING` e
  `PLAYER_EXITED`;
- especificar manutencao minima: ver estado publico, identificar erro e
  preparar reinicio de player/diagnostico sanitizado para fase posterior.

Fora de escopo:

- hotspot Wi-Fi;
- portal local completo;
- ativacao backend;
- factory reset real;
- reset leve operacional;
- telemetria.

Arquivos provaveis:

- `docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md`;
- extensao do preview SVG;
- possivel tabela de mensagens/codigos publicos;
- ajustes futuros no agregador apenas se o contrato publico precisar de novos
  campos allowlisted;
- ajustes futuros no renderer/launcher somente apos revisao de processo
  DRM/KMS.

Validacao minima:

- previews locais para `config_missing`, `player_error` e
  `maintenance_placeholder`;
- sanitizacao de SVG e JSON;
- renderer nao roda em `player_running`;
- renderer para antes de `kiosk.py`;
- restauracao para player com observer curto sem timeout;
- `systemctl --failed=0`.

Riscos:

- refinamento visual quebrar legibilidade;
- adicionar campo publico que vaze dado privado;
- habilitar `player_error` sem testar retry e ordem de processos;
- introduzir manutencao que pareca pronta antes de haver comandos seguros.

Criterios de aceite:

- operador entende que a configuracao esta pendente sem terminal;
- codigos publicos estao documentados;
- area de QR code futuro existe sem acionar setup real;
- nenhuma acao de manutencao executa shell arbitrario;
- Fase A nao regride.

Criterio de rollback:

- voltar ao layout A1.4 de `config_missing` e manter o launcher atual.

## Fase C - Wi-Fi/setup

Objetivo:

- criar hotspot Dadooh Setup;
- exibir QR code;
- permitir configuracao via celular;
- salvar Wi-Fi;
- testar conexao.

Arquivos provaveis:

- novo servico `totem-setup`;
- perfis NetworkManager dedicados;
- scripts/wrappers de NetworkManager;
- status de setup em `/data/state/totem`;
- pagina local de setup.

Validacao minima:

- sem rede/config, hotspot sobe com nome previsivel e nao sensivel;
- celular acessa portal local via QR code;
- operador seleciona rede, informa senha e testa conexao;
- senha errada mostra erro recuperavel;
- reboot preserva conexao salva;
- Ethernet, se presente, nao e derrubada indevidamente.

Riscos:

- hotspot interferir em redes salvas;
- senha Wi-Fi aparecer em logs/status;
- captive portal falhar em celulares especificos;
- NetworkManager entrar em estado ambiguo entre AP e cliente.

Criterios de aceite:

- configuracao Wi-Fi completa sem terminal;
- nenhum segredo aparece em docs, logs compartilhaveis ou diagnostico
  sanitizado;
- queda e retorno de internet ficam legiveis para operador.

Criterio de rollback:

- remover/desabilitar perfis de hotspot/setup e voltar a conexoes
  NetworkManager provisionadas manualmente.

## Fase D - ativacao de ambiente

Objetivo:

- ativar por codigo;
- evitar digitacao manual de `api_key`;
- backend troca codigo por config;
- salvar config em `/data/config`.

Arquivos provaveis:

- endpoint/pagina de ativacao no `totem-setup`;
- writer atomico de `/data/config/config.json`;
- schema publico sem secrets;
- estado de ativacao em `/data/state/totem`;
- integracao backend para troca de codigo.

Validacao minima:

- sem config, tela mostra codigo/QR e estado claro;
- codigo valido baixa config e grava com permissao restrita;
- codigo invalido/expirado mostra erro recuperavel;
- player inicia depois da config valida;
- nenhum segredo e impresso.

Riscos:

- backend indisponivel bloquear ativacao;
- config parcial quebrar boot;
- permissao fraca em `/data/config/config.json`;
- operador digitar dados errados se houver fallback manual.

Criterios de aceite:

- operador nao manipula `api_key`;
- config e validada antes de substituir a anterior;
- rollback local preserva ultima config valida.

Criterio de rollback:

- restaurar ultima config valida de `/data/config` e desabilitar ativacao por
  codigo ate corrigir backend/setup.

## Fase E - rotacao/resolucao

Objetivo:

- suportar rotacao 0/90/180/270;
- oferecer teste visual;
- salvar preferencia;
- reiniciar player quando necessario.

Arquivos provaveis:

- pagina de manutencao/setup;
- config em `/data/config/config.json`;
- status/splash para teste visual;
- possivel config separada `/data/config/display.json`.

Validacao minima:

- operador escolhe 0, 90, 180 ou 270;
- teste visual confirma orientacao;
- valor persiste apos reboot;
- MPV aplica `--video-rotate` ou propriedade equivalente;
- erro de valor invalido cai para padrao seguro.

Riscos:

- rotacao quebrar layout do splash/status;
- resolucao/tela especifica exigir ajuste fora do MPV;
- reinicio do player durante reproducao confundir operador.

Criterios de aceite:

- rotacao muda sem terminal;
- estado final e claro para operador;
- player volta a `playing`.

Criterio de rollback:

- voltar `rotation_deg=0` ou ultima config valida e reiniciar player.

## Fase F - monitoramento/telemetria

Objetivo:

- reportar estado online;
- uptime;
- temperatura;
- disco;
- versao app;
- versao imagem;
- ultimo erro;
- `display_missing`.

Arquivos provaveis:

- agregador de status do appliance;
- contrato de payload de telemetria;
- spool opcional em `/data/spool/totem`;
- extensao do diagnostico sanitizado;
- config de telemetria sem token hardcoded.

Validacao minima:

- payload nao contem secrets, URLs privadas ou paths reais de midia;
- sem internet, telemetria falha sem afetar player;
- retorno da internet retoma envio;
- `display_missing`, disco cheio, temperatura alta e ultimo erro aparecem no
  estado agregado.

Riscos:

- vazamento de dados privados;
- telemetria gerar escrita excessiva;
- token de telemetria mal provisionado;
- backend interpretar estados de forma diferente do totem.

Criterios de aceite:

- dashboard/backend consegue distinguir online, offline, sem HDMI, sem config e
  erro de player;
- falha de telemetria nao reinicia player.

Criterio de rollback:

- desligar telemetria do appliance por config e manter status local/diagnostico.

## Fase G - update/rollback

Objetivo:

- armazenar releases em `/opt/totem/releases`;
- usar symlink ativo;
- permitir rollback.

Arquivos provaveis:

- `/opt/totem/releases/<versao>`;
- `/opt/totem/current`;
- unit apontando para symlink ativo;
- comando de update controlado;
- manifesto de release;
- estado de rollback em `/data/state/totem`.

Validacao minima:

- instalar nova release sem alterar `/data/config`;
- healthcheck pos-update passa antes de confirmar;
- rollback volta a release anterior;
- falha no boot retorna para release anterior ou entra em manutencao.

Riscos:

- symlink quebrado deixar player fora;
- update parcial em queda de energia;
- incompatibilidade entre config antiga e app novo;
- falta de espaco em `/opt` ou `/data`.

Criterios de aceite:

- update e rollback funcionam sem terminal;
- versao app/imagem aparecem no status;
- corte de energia durante update nao corrompe release ativa.

Criterio de rollback:

- apontar symlink ativo para release anterior validada e reiniciar servico.

## Fase H - root read-only/corte seco

Objetivo:

- ativar root read-only depois de logs, cache e config estabilizados;
- validar corte seco em condicoes controladas.

Arquivos provaveis:

- overlay/customizacao da imagem;
- ajustes de `/var/log`, `/tmp` e `/data`;
- units de montagem;
- documentacao de teste de corte seco;
- politicas de log/cache.

Validacao minima:

- boot normal com root protegido;
- player grava somente em `/data` e `/tmp`;
- diagnostico confirma ausencia de escrita inesperada em root;
- ciclos de desligamento abrupto nao causam erro EXT4, remount read-only ou
  perda de config;
- factory reset continua funcionando.

Riscos:

- caminho mutavel esquecido em root;
- diagnostico/logs insuficientes para suporte;
- reset/update incompatibilizar com root read-only;
- teste de corte seco antes da hora mascarar causa de falha.

Criterios de aceite:

- sistema volta a operar apos cortes repetidos;
- `/data` contem todo estado mutavel necessario;
- rollback/update/reset continuam testados.

Criterio de rollback:

- voltar imagem para root gravavel de bancada e corrigir paths mutaveis antes de
  repetir corte seco.
