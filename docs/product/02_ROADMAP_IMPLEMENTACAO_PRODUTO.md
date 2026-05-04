# Roadmap de implementacao produto/UX

Status: proposta incremental. Nao implementa mudancas.

Data: 2026-05-01

Atualizacao C6.5: 2026-05-02. C6.3A e C6.4 estao concluidos como
desenvolvimento; C6.5 consolida o marco config real + `player_running`; testes
longos foram movidos para fila de homologacao separada.

Atualizacao C7.0: 2026-05-02. C7 passa a iniciar por diagnostico/status
sanitizado do appliance, com contrato e snapshot local/offline. C7.0 nao toca
placa, nao le config real, nao executa comandos operacionais e nao substitui
homologacao longa.

Atualizacao C8 produto V1: 2026-05-03. C8 passa a organizar a visao Produto V1
de operacao, onboarding e recuperacao para operador nao tecnico. Esta
atualizacao e documental: nao implementa operacao real, nao toca placa, nao
altera rede/config/player e nao substitui homologacao.

Atualizacao C8.1: 2026-05-03. C8.1 entrega setup minimo funcional/mock local
sem Wi-Fi real, com servidor HTTP local, prototipo estatico, candidata em
`/tmp`, status/summary sanitizados e smoke seguro opcional na placa usando
somente `/tmp`. Nao escreve config real, nao altera rede, nao chama backend,
nao inicia player e nao substitui homologacao.

Atualizacao C8.1.1: 2026-05-03. C8.1.1 consolida o handoff entre setup minimo
e contrato C5.1: candidata passa em `allow-mock`, falha em `real-dry-run`
enquanto usa placeholders e grava rotacao em `rotation_deg`. Continua somente
em `/tmp`, sem writer real, sem rede e sem player.

Atualizacao C8.2: 2026-05-03. C8.2 troca o caminho principal de ambiente para
uma lista mock/local com nomes publicos e mantem o campo manual como modo
avancado/de bancada. A candidata continua validada por C5.1, somente em `/tmp`,
sem backend, sem rede real, sem writer real e sem player.

Atualizacao C8.3: 2026-05-03. C8.3 troca a escolha principal de rotacao de
graus tecnicos para opcoes amigaveis de orientacao, com preview simples. A
candidata continua gravando `rotation_deg`, somente em `/tmp`, sem aplicar
rotacao real e sem tocar MPV, player, rede, servicos, `/data` ou `/opt`.

Atualizacao C8.4.0: 2026-05-03. C8.4.0 cria a manutencao minima mock/local
como area secundaria do setup, com `restart_player_mock`,
`reset_config_mock`, confirmacao forte para reset e artefatos sanitizados em
`/tmp`. Ainda nao executa reset real, nao chama `systemctl`, nao reinicia
player/MPV, nao altera rede e nao toca `/data` ou `/opt`.

Atualizacao C8.5.0: 2026-05-03. C8.5.0 cria o preflight local/offline de
integracao setup -> writer/config: le a candidata C8 em `/tmp`, confirma
C5.1 `allow-mock`, confirma `real-dry-run` falhando por placeholders e gera
relatorio sanitizado de lacunas para futura config real. Nao chama writer em
modo real, nao usa secrets, nao toca `/data` ou `/opt` e nao altera servico,
player, MPV, rede ou backend.

Atualizacao C8.5.1: 2026-05-03. C8.5.1 define a origem futura aprovada de
valores privados e gera uma candidata real-sintetica somente em `/tmp`, com
valores nao reais gerados localmente. A candidata real-sintetica passa C5.1
`real-dry-run`, mas writer real continua bloqueado; nao usa secrets reais, nao
toca `/data` ou `/opt` e nao altera servico, player, MPV, rede ou backend.

Atualizacao C8.5.2: 2026-05-03. C8.5.2 revisa o contrato minimo e reclassifica
`station_id` como opcional, nao operacional e futuro. `api_url` e `api_key`
continuam valores privados importantes, `environment_id` continua necessario,
e `station_id` deixa de bloquear C5.1 `real-dry-run`. A alteracao permanece em
`/tmp`, sem writer real, sem config real, sem `/data`, sem `/opt`, sem player e
sem rede.

Atualizacao C8.6-preflight: 2026-05-03. C8.6 define o handoff real controlado
sem escrita real: le valores privados aprovados somente de arquivo restrito sob
`/tmp`, gera candidata privada temporaria, valida C5.1 `real-dry-run`, observa
pre-condicoes de servico/player sem alterar estado e registra pontos de aborto.
Writer real continua bloqueado, `--enable-real-write` nao e usado, `/data` e
`/opt` nao sao tocados e nenhum valor privado e publicado.

Atualizacao C8.6.1: 2026-05-03. C8.6.1 adiciona limpeza explicita dos arquivos
privados temporarios do preflight: remove `candidate-private.json` e
`private-values.json`, preserva apenas status/summary sanitizados, registra
cleanup executado e mantem writer real bloqueado. Continua somente em `/tmp`,
sem `/data`, `/opt`, servico, player, MPV, rede ou backend.

Atualizacao C8.7: 2026-05-03. C8.7 cria o gate operacional final antes da
primeira escrita real integrada: inspeciona a placa em modo read-only, confirma
guardrails do writer C6, verifica o fluxo C8.6/C8.6.1, gera checklist go/no-go
e documenta o roteiro exato da rodada real futura. Ainda nao usa
`--enable-real-write`, nao escreve em `/data` ou `/opt`, nao para/inicia
servico, nao inicia player e nao publica valores privados.

Atualizacao C8.8: 2026-05-03. C8.8 executa a primeira escrita real integrada
setup -> writer/config em desenvolvimento: gera candidata C8 em `/tmp`, aplica
valores privados aprovados por arquivo restrito, valida C5.1 `real-dry-run`,
para `kiosky-player.service`, escreve `/data/config/config.json` via writer C6
com flags reais explicitas, cria backup, limpa temporarios privados e roda gate
read-only final. O servico permanece parado ao final; player/MPV/rede/backend
nao sao iniciados e producao continua bloqueada.

Atualizacao C8.9: 2026-05-03. C8.9 executa o start controlado pos-escrita real:
inicia `kiosky-player.service` sem alterar config e sem rodar writer, observa
status publico e processos por categorias, confirma `player_running`, playback
`playing`, `kiosk.py` e MPV ativos, renderer ausente junto do player e
`NRestarts=0` em smoke curto de 120 segundos. Evidencia permanece sanitizada em
`/tmp`; producao continua bloqueada.

Atualizacao C8.10: 2026-05-03. C8.10 executa reboot/autoboot controlado com a
config real escrita pelo fluxo C8: confirma pre-check `player_running`, pede
autorizacao humana explicita, reinicia a placa por reboot controlado, aguarda
SSH voltar, observa servico/status/player/MPV/renderer e confirma retorno para
`player_running` com playback `playing`, MPV ativo, renderer inativo e
`NRestarts=0`. Validacao visual humana confirmou midia visivel apos boot.
Config, backups, writer, rede/Wi-Fi e repo do player nao foram alterados;
producao continua bloqueada.

Correcao pos-C8.10: observacao de 30-60 minutos com config real pertence a fila
de homologacao paralela, nao a uma etapa C8.11 de desenvolvimento. A proxima
frente de desenvolvimento passa a ser C9.0: acesso temporario ao setup pela
rede local existente, sem Wi-Fi real, hotspot, portal definitivo, writer ou
alteracao da config real.

Atualizacao C9.0: 2026-05-03. C9.0 executa o acesso temporario ao setup C8 pela
rede local de bancada existente: sobe o servidor em `/tmp`, expoe porta
temporaria para navegador, gera candidata de teste apenas em `/tmp`, coleta
evidencia sanitizada e encerra o servidor ao final. Nao implementa Wi-Fi real,
hotspot, portal definitivo, NetworkManager, `nmcli`, writer, config real ou
alteracao do player; `kiosky-player.service` permanece ativo e producao
continua bloqueada.

Atualizacao C9.1: 2026-05-03. C9.1 corrige a premissa de produto: setup pela
propria tela HDMI do totem e obrigatorio, enquanto rede local/QR/navegador sao
caminhos auxiliares. A etapa cria um wizard local controlado por teclado USB,
sem Chromium, desktop, compositor ou shell livre, que seleciona ambiente
mock/local, orientacao, revisao e gera candidata apenas em `/tmp` validada por
C5.1. Nao escreve config real, nao roda writer, nao toca `/data`, `/opt`,
servico, player, MPV, rede ou Wi-Fi.

Atualizacao C9.1.1: 2026-05-04. C9.1.1 executa a validacao humana do wizard
local na propria placa, com HDMI e teclado USB. O runner remoto copia scripts
para `/tmp`, roda self-tests, observa console/servico/processos por categorias,
abre o wizard em TTY local com parada temporaria do player somente apos
autorizacao humana explicita e restaura o estado ao final. Resultado: passou
tecnicamente, gerou candidata em `/tmp`, C5.1 `allow-mock` passou,
`real-dry-run` falhou como esperado e o servico voltou `active/enabled` com
`NRestarts=0`, player=1, MPV=1 e renderer=0. Ressalvas: UX ainda parece
terminal Linux/Python interativo, nao esta aprovada para operador final, e foi
registrado warning visual de midia aparentemente mais esticada apos
restauracao. Nao integra launcher, nao chama automaticamente em
`config_missing`, nao roda writer e nao altera config real, `/data`, `/opt`,
rede ou Wi-Fi.

Atualizacao C9.1.2: 2026-05-04. C9.1.2 diagnostica a proporcao visual
pos-restauracao observada em C9.1.1. A Fase A read-only confirmou que a midia
ja parecia esticada antes de qualquer stop/start da etapa; a Fase B, autorizada
explicitamente, executou stop/start controlado e a imagem continuou exatamente
igual. O servico terminou `active/enabled`, `NRestarts=0`, player=1, MPV=1 e
renderer=0. A placa observou HDMI `connected/enabled`, framebuffer `1360x768`,
MPV OSD `1024x768` e modos HDMI anunciados sem `1920x1080`; por isso, a
hipotese mais forte passa a ser adequacao de modo/resolucao por tela
fisica/EDID/framebuffer/MPV, nao regressao direta do wizard. Proxima frente
deve considerar contrato visual/seletor por tipo de tela antes de UX final.

Atualizacao C9.1.3: 2026-05-04. C9.1.3 cria e executa o contrato visual curto
de display/orientacao: gera um SVG local em `/tmp` com borda, grid, circulo,
quadrado, cruz central e setas de topo; coleta snapshots sanitizados de
servico/processos/TTY/framebuffer/DRM/MPV; e fornece runner remoto com
`--prepare-only` seguro e `--display` bloqueado por confirmacao humana textual
explicita. Na execucao autorizada, o player foi parado temporariamente, o
padrao apareceu via MPV/DRM por 90s, e o player foi restaurado para
`active/enabled`, `NRestarts=0`, player=1, MPV=1 e renderer=0. O humano
corrigiu a validacao: circulo parece oval, quadrado parece retangulo, a margem
amarela nao esta cortada, mas o padrao nao ocupa/alinha igualmente os dois
eixos da tela; a midia restaurada continua esticada. A etapa nao altera config
real, writer, flags MPV, launcher, rede, NetworkManager, `/data`, `/opt` ou
repo do player. Producao continua bloqueada; a frente futura de
seletor/resolucao/tipo de tela deve ser aberta sem travar C9 indefinidamente.

Atualizacao C9.2: 2026-05-04. C9.2 documenta o contrato futuro de chamada do
setup local pelo launcher no estado `config_missing`, sem alterar o launcher
operacional. O contrato define que o setup local continua obrigatorio no proprio
totem e QR/navegador seguem auxiliares; o wizard deve entrar somente com display
conectado, config invalida/ausente, gatilho local controlado, renderer parado e
player ausente. A TTY futura deve ser reservada, preferencialmente `tty2`, com
exec direto do wizard e sem shell livre. O handoff permanece em `/tmp`, com
candidata/status/summary `0700`/`0600`, e writer/config real ficam para etapa
futura. O problema de display/EDID fica registrado como risco e frente separada,
sem bloquear C9.2. Producao continua bloqueada.

Atualizacao C9.2.1: 2026-05-04. C9.2.1 cria uma simulacao source-only da
decisao launcher/setup local, sem executar o launcher real, renderer, MPV,
wizard HDMI, writer, servico ou acoes operacionais. A matriz cobre display
ausente, config valida, config ausente sem setup, config ausente com setup,
cancelamento do wizard, candidata pronta e config valida apos escrita futura.
A regra `renderer xor wizard xor player` e validada em fixtures, com TTY futura
`tty2`, handoff de candidata em `/tmp` e writer/config real reservados para
etapa futura. Nao altera launcher, `/data`, `/opt`, rede, display ou
`kiosky-player`; producao continua bloqueada.

Atualizacao C9.3: 2026-05-04. C9.3 implementa uma integracao experimental do
launcher com o wizard local em `config_missing`, desligada por padrao e atras
de `TOTEM_SETUP_LOCAL_ENABLED=1` mais autorun/gatilho explicito em `/tmp`. O
launcher passa a conseguir parar renderer, chamar o wizard via `openvt` em TTY
reservada, registrar cancelamento/falha/candidata pronta e voltar para status
sem chamar writer nem iniciar player enquanto a config segue invalida. O
agregador de status passa a mapear estados experimentais `setup_local_*` para
estado publico seguro `config_missing`. Foi criado runner remoto controlado que
usa copia em `/tmp`, config override inexistente, renderer fake sem MPV e
restauracao do servico real ao final. A execucao autorizada provou o caminho de
cancelamento do wizard e depois o caminho de `candidate_ready` com candidata em
`/tmp`; em ambos os casos restaurou `active/enabled`, `NRestarts=0`, player=1,
MPV=1 e renderer=0, com status publico final `player_running`. Nao altera
config real, `/data/config`, writer, rede, display/EDID, flags MPV ou
`kiosky-player`; producao continua bloqueada.

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

Status: B1 concluida em desenvolvimento. O restante da manutencao minima segue
planejado. Ver `docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md` e
`docs/product/10_FASE_B1_VISUAL_CONFIG_MISSING.md`.

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

B1 concluida em desenvolvimento:

- tela publica Dadooh "Configuracao pendente" validada por observacao humana;
- codigo publico `CONFIG_MISSING` visivel;
- area de configuracao assistida marcada como futura, sem QR funcional;
- renderer ativo apenas em `config_missing`;
- `kiosk.py=0` e MPV principal `0` enquanto renderer esta ativo;
- restauracao para `player_running` com renderer parado e observer curto limpo;
- sem Wi-Fi setup, hotspot, portal, ativacao backend, reset real, telemetria ou
  mudanca no `kiosky-player`.

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

## Fase C0-C2 - planejamento e refinamento minimo de onboarding

Status: C0 e C1 documentados; C1.1/C2 em preparacao documental. Nao implementa
mudancas operacionais.

Documentos:

- `docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md`;
- `docs/product/13_RISCOS_ONBOARDING_WIFI_CONFIG.md`;
- `docs/DECISIONS/ADR-0008-onboarding-wifi-config.md`;
- `docs/product/14_C1_CONFIG_MISSING_MINIMAL_ONBOARDING.md`;
- `docs/product/15_C1_MINIMAL_USER_FLOW.md`;
- `docs/product/16_C1_MINIMAL_STATE_MACHINE.md`;
- `docs/product/17_C2_MOCK_VISUAL_FORMULARIO.md`;
- `docs/product/18_C2_PREVIEW_VISUAL_EVIDENCE.md`;
- `docs/product/25_C5_CONFIG_WRITER_MOCK.md`;
- `docs/product/26_C5_1_CONFIG_CONTRACT_VALIDATOR.md`;
- `docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md`;
- `docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md`;
- `docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md`;
- `docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md`;
- `docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md`;
- `docs/product/36_C7_DIAGNOSTICO_STATUS_APPLIANCE.md`;
- `docs/product/37_PRODUTO_V1_OPERACAO_ONBOARDING_RECUPERACAO.md`;
- `docs/product/38_FLUXO_PRODUTO_V1_ONBOARDING_MANUTENCAO_RECUPERACAO.md`;
- `docs/product/39_INVENTARIO_TELAS_ACOES_PRODUTO_V1.md`;
- `docs/product/40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md`;
- `docs/product/prototypes/v1-operacao-recuperacao/index.html`;
- `docs/DECISIONS/ADR-0009-minimal-config-environment-id.md`;
- `docs/DECISIONS/ADR-0010-api-token-provisioning.md`.

Objetivo:

- especificar o fluxo de onboarding antes de qualquer implementacao de rede;
- separar primeiro boot, Wi-Fi, ativacao e manutencao minima;
- definir estados publicos e mensagens sem dados privados;
- definir limites de seguranca para credenciais, config e diagnostico;
- desenhar rollback antes de alterar NetworkManager ou `/data/config`.

Escopo de planejamento:

- jornadas de operador e suporte;
- contrato publico de estados para setup;
- decisao entre hotspot, rede existente e fallback de bancada;
- politica para credenciais Wi-Fi sem logs sensiveis;
- fluxo de ativacao backend por codigo, ainda sem endpoint implementado;
- escrita atomica futura de config em `/data/config`;
- criterios de teste e bloqueio para placa de desenvolvimento e homologacao;
- criterios de rollback para voltar ao player/status atual.

Fora de escopo em C0-C2:

- implementar Wi-Fi setup;
- criar hotspot;
- criar portal local;
- integrar ativacao backend;
- escrever config real por operador;
- implementar reset real;
- implementar telemetria;
- instalar pacotes.

Refinamento C1:

- foco no caso `config_missing` com sistema/servico/launcher funcionando e HDMI
  conectado;
- operador informa apenas `environment_id`;
- `api_key`/token fica fora da UI e, conforme ADR-0010, pode vir de
  provisionamento local privado em C6;
- ativacao por codigo, login e lista de ambientes ficam como alternativas
  futuras;
- primeira inicializacao completa de cartao Armbian virgem fica para fase
  posterior.

Sequencia incremental refinada:

- C1 - escopo e fluxo minimo Wi-Fi + `environment_id` documentado;
- C1.1 - coerencia documental C0/C1 e preparacao de C2;
- C2 - mock visual/formulario sem alterar rede;
- C3 - diagnostico Wi-Fi read-only;
- C4 - Wi-Fi real controlado em bancada com Ethernet preservada;
- C5 - config writer mock em `/tmp`, sem secrets, sem config real e preparando
  C6;
- C5.1 - contrato de config minima e validador dry-run em `/tmp`;
- C6.0 - plano de writer real concluido;
- C6.1-preflight - checklist e decisoes antes de implementacao real;
- C6.2 - writer real simulado em `/tmp`, sem tocar `/data`;
- C6.2.1 - smoke na placa de desenvolvimento, ainda somente em `/tmp`;
- C6.2.2 - guardrails para modo real do writer;
- C6.3-preflight - inspecao read-only da placa antes da escrita real;
- C6.3.0 - plano de execucao real com servico parado;
- C6.3A - primeira escrita real com servico parado;
- C6.4 - start controlado com config real e smoke curto;
- C6.5 - consolidacao documental do marco config real + `player_running`;
- C7.0 - contrato + snapshot local/offline de diagnostico/status sanitizado;
- C7.1 - futura validacao em placa read-only, se aprovada;
- C8 - Produto V1: operacao, onboarding e recuperacao;
- C8.1 - setup minimo funcional sem Wi-Fi real;
- C8.1.1 - handoff setup minimo -> contrato C5.1;
- C8.2 - selecao de ambiente mock/local, funcional/mock local;
- C8.3 - rotacao mock/local, funcional/mock local;
- C8.4.0 - manutencao minima mock/local e contrato de acoes;
- C8.4 - reset leve e reiniciar player, ainda pendente de acao real aprovada;
- C8.5.0 - preflight setup -> writer/config, local/offline em `/tmp`;
- C8.5.1 - origem de valores privados e candidata real-sintetica em `/tmp`;
- C8.5 - integracao com writer/config;
- C8.6 - handoff real controlado, ainda sem escrita real;
- C8.6.1 - limpeza segura da candidata privada temporaria;
- C8.7 - gate operacional final antes da escrita real;
- C8.8 - primeira escrita real integrada, sem start do player;
- C8.9 - start controlado pos-escrita real, smoke curto;
- C8.10 - reboot/autoboot controlado com config real;
- C9.0 - acesso temporario ao setup pela rede local existente;
- C9.1 - setup local na propria plaquinha;
- C9.1.1 - validacao humana do wizard local HDMI;
- C9.1.2 - diagnostico de proporcao visual pos-restauracao;
- C9 - Wi-Fi/portal/hotspot;
- C10 - manutencao/reset avancado.

Criterios de aceite:

- documento de arquitetura do onboarding aprovado;
- ameacas principais de privacidade e credenciais listadas;
- estados publicos e mensagens definidos;
- plano de teste inclui senha incorreta, rede ausente, reboot, Ethernet
  presente e ausencia de internet;
- plano preserva a separacao entre homologacao `v0.1-rc1`, desenvolvimento
  pos-RC1 e producao futura;
- Wi-Fi setup real, hotspot, portal local, ativacao backend e escrita real de
  config seguem nao implementados ao final de C2.

## Fases C1-C8 - onboarding minimo refinado

Status: C1-C6 avancaram como desenvolvimento incremental; C6.5 consolida config
real + `player_running`; C7.0 inicia diagnostico/status sanitizado
local/offline; C7.1 e C8 continuam planejadas. Homologacao e producao seguem
separadas.

Estas fases substituem a sequencia anterior mais ampla para evitar que hotspot,
ativacao backend, writer real, rotacao e manutencao avancem juntos.

### C1 - escopo e fluxo minimo documentado

Status: concluida/documentada.

Objetivo:

- documentar o caso `config_missing` com HDMI conectado;
- definir fluxo minimo Wi-Fi + `environment_id`;
- manter `api_key` fora da UI;
- registrar a maquina de estados minima;
- preservar C0/ADR-0008 como visao futura.

Aceite:

- documentos C1 e ADR-0009 criados;
- nenhum script, systemd, NetworkManager ou `kiosky-player` alterado;
- C1 marcada como desenvolvimento/proposta, sem liberar producao.

### C1.1 - coerencia documental C0/C1

Status: documental.

Objetivo:

- consolidar que C0/ADR-0008 sao visao original e futura;
- deixar C1/ADR-0009 como recorte vigente atual;
- preparar C2 sem apagar historico;
- explicitar que codigo curto, login, lista de ambientes e ativacao backend
  ficam para C7 ou fase posterior.

Aceite:

- C0 tem nota de leitura para trechos historicos;
- roadmap aponta para C2 como mock visual sem rede real;
- riscos cobrem o mock parecer funcional ou capturar dados reais.

### C2 - mock visual/formulario sem alterar rede

Status: preview visual/mock local em implementacao. Sem integracao
operacional.

Objetivo:

- criar preview visual/mock local para Wi-Fi e `environment_id`;
- nao listar redes reais;
- nao pedir senha real;
- nao persistir senha mock;
- nao alterar NetworkManager;
- nao escrever config real;
- nao criar portal funcional, servidor HTTP, hotspot ou QR funcional.

Validacao:

- previews e/ou mock local sem secrets;
- textos publicos claros para operador nao tecnico;
- renderer/setup continua separado do player;
- SVGs estaticos gerados localmente em `/tmp`;
- nenhuma integracao com rede real, config real, launcher operacional,
  renderer operacional ou `kiosky-player`.

### C3 - diagnostico Wi-Fi read-only

Status: diagnostico Wi-Fi read-only em implementacao/preparado. Sem alteracao
de rede.

Objetivo:

- criar base local sanitizada para observar estado de rede de forma apenas
  leitura;
- diferenciar Wi-Fi device presente, Wi-Fi conectado, IP local, rota default,
  DNS planejado, internet basica futura e backend futuro;
- nao derrubar Ethernet, Wi-Fi ou SSH de bancada;
- nao publicar SSID real, senha, IP local/publico, gateway, hostname, MAC,
  BSSID ou nome de conexao NetworkManager;
- nao executar teste externo de internet/backend por enquanto, salvo decisao
  posterior.

Validacao:

- prova de que nenhum comando altera conexoes;
- diagnostico sanitizado em `/tmp`, com permissoes restritas;
- comandos allowlisted e comandos proibidos testados por self-test;
- falhas aparecem como codigos publicos;
- Ethernet nao e desconectada ou modificada;
- nenhum artefato publica SSID, IP, senha, hostname, gateway ou nome de
  conexao.

### C4 - Wi-Fi real controlado em bancada

Status: C4.0 aprovado/documentado como plano de bancada; C4.1-preflight
documentado; primeira rodada C4.1 abortada com seguranca antes de inserir
senha; C4.1-postmortem concluido; C4.2 hibrido/local consolidou o modelo
humano fora do Codex, com C3 antes/depois/final e retorno humano sanitizado;
C4.3 define canal seguro de credencial como proximo passo de processo; canal
humano/local escolhido como SSH proprio fora do Codex; C4 hibrido validou
conexao Wi-Fi de teste por humano fora do Codex; C4.5 registrou remocao local
da configuracao de teste. C4 esta pausado/fechado temporariamente apos C4.5,
com backlog explicito em `docs/product/27_C4_WIFI_BACKLOG_E_GATES.md`.

Objetivo:

- planejar e depois testar alteracao real de Wi-Fi apenas em bancada;
- preservar Ethernet como recuperacao;
- usar C3 sanitizado antes/depois;
- documentar rollback de NetworkManager antes de executar;
- manter C4 fora de hotspot, portal local, config writer e producao.

Validacao:

- C4.0 documenta pre-condicoes, comandos candidatos, rollback, criterios de
  sucesso/aborto e evidencia esperada;
- C4.1-preflight documenta decisoes humanas finais, regra de senha sem registro
  e roteiro comando a comando sem execucao;
- C4.1 teve tentativa abortada com seguranca antes de inserir senha;
- C4.1-postmortem registrou que Codex/SSH/chat nao devem receber credencial;
- C4.1 nao deve passar senha por Codex, SSH remoto gerenciado pelo agente, chat,
  historico, script ou evidencia;
- C4.2 define o roteiro hibrido/local com Codex rodando C3 antes/depois/final e
  humano executando a etapa sensivel fora do agente;
- C4.2 consolidou o modelo hibrido/local, mantendo Codex fora da credencial e
  restrito a C3/evidencia sanitizada;
- C4.3 definiu canal humano/local seguro para inserir credencial: SSH proprio
  do humano fora do Codex;
- C4 hibrido validou conexao Wi-Fi de teste usando esse canal, mantendo Codex
  restrito a C3/evidencia sanitizada;
- C4.5 removeu o perfil/configuracao de teste por acao humana local e C3 final
  permaneceu saudavel;
- internet/backend continuam nao testados;
- Wi-Fi ainda nao e produto final;
- backlog futuro de Wi-Fi esta documentado em
  `docs/product/27_C4_WIFI_BACKLOG_E_GATES.md`;
- o avanco atual pode seguir por C5/C5.1/C6 sem assumir Wi-Fi como producao;
- antes de produto/campo, voltar aos gates C4 de reboot/reconexao, falhas
  controladas, adapter seguro, politica de credenciais, ciclo de vida de
  perfis e contrato de estados;
- senha errada ou falha de conexao recupera sem vazar credencial;
- Ethernet nao e derrubada indevidamente;
- rollback remove somente perfil de teste;
- reboot nao e criterio obrigatorio e NetworkManager nao pode ficar em estado
  ambiguo;
- nenhum hotspot, portal, config writer, `/data/config/config.json` ou player
  e alterado em C4.

### C5 - config writer mock

Status: base mock local concluida. Sem escrita real de config.

Objetivo:

- criar caminho de validacao de config minima sem substituir config ativa real;
- montar config candidata mock somente em `/tmp`;
- simular `api_key` fora da UI usando placeholder;
- manter `api_url` e `environment_id` como mock/placeholders;
- manter `station_id` apenas como mock opcional/futuro, sem bloquear a config
  minima;
- validar `environment_id` por formato minimo;
- preparar C6, mas sem executar C6.

Validacao:

- `--self-test` cobre `environment_id` valido/invalido, URL, path,
  token/secret, `--out-dir` fora de `/tmp` e escrita atomica;
- artefatos mock gerados em `/tmp/dadooh-c5-config-writer-mock`;
- diretorio com permissao `700` e arquivos com permissao `600`;
- nenhuma config parcial vira ativa;
- nenhuma escrita em `/data` ou `/data/config/config.json`;
- nenhum secret real, `api_url` privada, `environment_id` real ou payload de
  backend;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` permanecem
  fora do escopo;
- writer mock nao imprime secrets.

### C5.1 - contrato de config minima e validador dry-run

Status: contrato e validador dry-run local concluido. Sem escrita real de
config.

Objetivo:

- definir contrato minimo da config candidata;
- validar config candidata em dry-run;
- preparar C6 com bloqueio explicito de placeholders;
- impedir que config mock C5 vire config real;
- escrever apenas relatorio/status em `/tmp`;
- nao escrever, ler ou alterar `/data/config/config.json`.

Validacao:

- config mock C5 passa em `--allow-mock`;
- config mock C5 falha em `--real-dry-run` por placeholders;
- `--out-dir` fora de `/tmp` falha;
- campo obrigatorio ausente falha;
- path fora do contrato falha;
- `api_key` placeholder falha em `--real-dry-run`;
- status e summary nao imprimem valor de `api_key`;
- nada e escrito em `/data`;
- config real nao e lida;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` permanecem
  fora do escopo.

### C6 - config real com validacao e rollback

Status: C6.0 plano concluido; C6.1-preflight documental concluido; C6.2
writer real simulado em `/tmp` concluido localmente; C6.2.1 smoke na placa de
desenvolvimento em `/tmp` concluido; C6.2.2 guardrails de modo real concluidos;
C6.3A tentativa abortada por self-test do writer na placa; C6.2.3 correcao de
compatibilidade do self-test concluida; C6.3-preflight read-only na placa
concluido; C6.3.0 plano de execucao com servico parado concluido; C6.3A
execucao real concluida na placa de desenvolvimento com servico parado, backup
restrito e player mantido parado; C6.4 start controlado com config real
concluido como smoke curto de desenvolvimento; C6.5 consolidacao documental
criada.

Objetivo:

- gravar config minima real somente depois de C5;
- usar provisionamento local privado de `api_key`/token como caminho de
  desenvolvimento conforme ADR-0010;
- validar todos os campos obrigatorios antes de substituir;
- usar escrita atomica;
- preservar ultima config valida quando existir;
- iniciar player apenas depois de config valida.

Validacao:

- queda no meio nao deixa config parcial ativa;
- `api_key` externa ausente bloqueia salvamento ou inicio do player;
- renderer/setup para antes do player;
- rollback restauravel e documentado;
- C6.3A e C6.4 estao concluidos em desenvolvimento, nao homologacao.
- Observer prolongado, reboot/autoboot, segunda placa/cartao, root read-only,
  corte seco e rollback real acionado por falha foram movidos para fila de
  homologacao separada.

#### C6.0 - plano de writer real

Status: plano documental criado em
`docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md`. Sem escrita real.

Objetivo:

- planejar escrita real de `/data/config/config.json`;
- definir origem real da `api_key`/token por provisionamento local privado em
  desenvolvimento;
- definir ownership, permissoes, backup, rollback e criterio de falha;
- definir como queda de energia sera testada;
- definir criterio para launcher iniciar player somente com config valida;
- manter implementacao e execucao bloqueadas ate decisao humana sobre secrets,
  permissoes, rollback, queda de energia e evidencia.

Validacao:

- plano revisado antes de qualquer escrita em `/data`;
- rollback documentado;
- placa de desenvolvimento prevista no preflight e autorizada antes de C6.3A;
- evidencia esperada definida sem secrets;
- nenhuma config real lida, escrita ou alterada em C6.0.

#### C6.1-preflight - checklist e decisoes antes do writer real

Status: checklist documental criado em
`docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md`. Sem escrita real.

Objetivo:

- consolidar decisoes humanas obrigatorias antes de C6.2/C6.3A;
- definir politica de secrets para `api_key`/token, `api_url`, IDs reais,
  backup e evidencia;
- definir checklist tecnico antes de escrita real;
- separar implementacao futura do writer real de execucao futura em placa;
- definir pontos de abortar e estrategia para evitar inicio prematuro do
  player.

Validacao:

- nenhuma config real lida, escrita ou alterada;
- nenhum writer real implementado;
- nenhuma placa acessada;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` fora do
  escopo;
- decisoes pendentes explicitadas antes de C6.2/C6.3A.

#### C6.2 - writer real simulado em /tmp

Status: implementado localmente em
`docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md` e
`scripts/board/totem_config_writer_real.py`. Sem escrita real em `/data`.

Objetivo:

- implementar writer real reutilizavel em modo simulado;
- manter testes e escrita somente em `/tmp` antes de qualquer placa;
- consumir candidata local de teste sem Codex ver token real;
- usar validador C5.1 em `--real-dry-run`;
- bloquear placeholders e ausencia de `api_key`;
- implementar escrita atomica, permissoes restritivas, backup e rollback
  simulados;
- preparar C6.3A sem tocar `/data/config/config.json`.

Validacao:

- self-test local sem tocar `/data`;
- candidata mock C5 falha em modo real;
- candidata sintetica nao-secret passa;
- destino fora de `/tmp` falha;
- backup-dir fora de `/tmp` falha;
- candidata sob `/data` ou `/opt` falha;
- escrita atomica gera config ativa simulada em `/tmp`;
- backup e rollback simulados cobertos pelo self-test;
- nenhum secret em stdout, log, summary, status ou evidencia;
- candidata sintetica, config ativa simulada, backup e status JSON de `/tmp`
  nao versionados;
- escrita real em `/data/config/config.json` continua bloqueada ate C6.3A.

#### C6.2.1 - smoke do writer simulado na placa

Status: smoke test concluido na placa de desenvolvimento. Ainda sem escrita
real em `/data`.

Objetivo:

- provar que o writer C6.2 roda no ambiente real da Orange Pi;
- copiar scripts somente para `/tmp`;
- criar candidata sintetica nao-secret na placa;
- executar self-tests na placa;
- executar writer com destino, backup-dir e out-dir sob `/tmp`;
- manter C6.3A separada para a escrita real em `/data`.

Validacao:

- self-test do validador C5.1 passou na placa;
- self-test do writer C6.2 passou na placa;
- writer simulado passou na placa;
- config ativa simulada foi criada em `/tmp` com permissao restritiva;
- status e summary nao publicaram `api_key`/token;
- nada foi escrito em `/data`;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player`
  permaneceram fora do escopo.

#### C6.2.2 - guardrails para modo real

Status: implementado localmente em
`docs/product/33_C6_2_2_WRITER_REAL_MODE_GUARDRAILS.md` e
`scripts/board/totem_config_writer_real.py`. Sem escrita real em `/data`.

Objetivo:

- manter modo padrao restrito a `/tmp`;
- adicionar flags explicitas para modo real futuro;
- permitir somente `/data/config/config.json` como destino real;
- restringir backup real a `/data/config/backups`;
- exigir candidata privada sob `/tmp` e fora do Git;
- testar guardrails sem executar escrita real.

Validacao:

- sem flags reais, destino `/data/config/config.json` falha;
- flags incompletas falham;
- com flags completas, path real aprovado passa apenas na validacao interna de
  guardrail durante self-test;
- destino real diferente falha;
- backup-dir real diferente falha;
- candidata em repositorio, `/data` ou `/opt` falha;
- modo simulado em `/tmp` continua passando;
- C6.3A continua sendo a primeira escrita real autorizada.

#### C6.2.3 - compatibilidade do self-test na placa

Status: concluido. Sem escrita real em `/data`.

Objetivo:

- diagnosticar falha do self-test do writer copiado para `/tmp` na placa;
- corrigir compatibilidade sem relaxar guardrails;
- revalidar localmente e na placa;
- manter C6.3A bloqueada ate nova revisao humana.

Validacao:

- causa identificada: teste de candidata em repo dependia do script estar
  dentro do checkout Git;
- correcao: detectar repo pelos pais da candidata e criar repo fake temporario
  em `/tmp` no self-test;
- self-test local do writer passou;
- self-test do writer na placa passou;
- escrita simulada em `/tmp` passou localmente e na placa;
- nada foi escrito em `/data`;
- servico nao foi parado, iniciado ou reiniciado;
- C6.2.3 permitiu repetir C6.3A desde a Fase 0 apos revisao humana.

#### C6.3-preflight - inspecao read-only da placa

Status: preflight read-only concluido na placa de desenvolvimento. Sem escrita
real em `/data`.

Objetivo:

- inspecionar usuario/grupo `totem` sem publicar arquivos completos do sistema;
- inspecionar existencia, tipo, mode e owner/group agregado de `/data`,
  `/data/config` e `/data/config/config.json`;
- confirmar legibilidade/escrita da config para `totem` sem ler conteudo;
- consultar estado do servico com comandos read-only;
- revisar a logica versionada do launcher;
- definir controle necessario antes da escrita real.

Validacao:

- `/data/config/config.json` existe e nao teve conteudo lido;
- config real nao foi escrita nem copiada;
- servico esta `enabled` e `active/running`;
- launcher usa `/data/config/config.json` por padrao e chama `run_app_once`
  quando a config e valida;
- recomendacao para C6.3A: executar com o servico parado ou bloqueio equivalente
  aprovado;
- C6.3A foi executada posteriormente com o servico parado.

#### C6.3.0 - plano de execucao com servico parado

Status: plano documental criado em
`docs/product/32_C6_3_EXECUCAO_CONFIG_REAL_SERVICO_PARADO.md`. Sem escrita real
em `/data` e sem tocar a placa.

Objetivo:

- transformar a recomendacao do preflight em plano de execucao real;
- exigir C6.3A com `kiosky-player.service` parado ou bloqueio equivalente;
- preservar backup e rollback antes da primeira escrita real;
- validar pos-escrita antes de qualquer decisao de iniciar player;
- manter decisao humana explicita para start do servico.

Validacao:

- C6.3-preflight read-only concluido e servico ativo/running detectado;
- escrita com servico ativo considerada bloqueada;
- sequencia futura documentada: preflight final, parada do servico, backup,
  candidata real privada, escrita atomica, pos-validacao, decisao de servico e
  evidencia sanitizada;
- C6.3A foi executada posteriormente com o servico parado.

#### C6.3A - primeira escrita real em placa de desenvolvimento

Status: concluida na placa de desenvolvimento. Player mantido parado ao final.

Objetivo:

- executar writer real aprovado apenas na placa de desenvolvimento;
- executar com `/data/config/config.json` real somente em fase separada;
- executar com `kiosky-player.service` parado ou bloqueio operacional
  equivalente aprovado;
- usar as flags reais de C6.2.2;
- validar escrita atomica, permissao e rollback;
- preservar ultima config valida quando existir;
- manter player bloqueado se a config falhar.

Validacao:

- execucao autorizada por humano apos C6.1-preflight, C6.2, C6.2.1, C6.2.2,
  C6.3-preflight e C6.3.0;
- `/data/config/config.json` escrito somente pelo writer real aprovado;
- `real-dry-run` e pos-validacao passaram;
- backup restrito foi criado em `/data/config/backups`;
- config ativa observada com owner/group `root:totem` e mode `0640`;
- usuario `totem` consegue ler e nao consegue gravar a config;
- rollback nao foi necessario;
- servico permaneceu parado ao final;
- player nao foi iniciado;
- evidencia sanitizada sem `api_key`, URL privada, IDs reais ou payload.

#### C6.4 - start controlado com config real

Status: concluido como smoke curto de desenvolvimento. Nao e homologacao e nao
libera producao.

Objetivo:

- iniciar `kiosky-player.service` controladamente com a config real escrita em
  C6.3A;
- observar launcher/player por 120s;
- confirmar `player_running` sem ler a config real;
- manter evidencia sanitizada.

Validacao:

- servico iniciou e permaneceu `active/running`;
- status publico chegou a `player_running`;
- playback ficou `playing`;
- MPV e `kiosk.py` ficaram ativos;
- `NRestarts=0` no observer curto;
- renderer junto com player nao foi observado na checagem final;
- servico foi mantido rodando ao final da rodada;
- nenhum secret, `api_url` real, ID real, payload, log bruto ou conteudo de
  config foi publicado.

Limite:

- C6.4 nao provou estabilidade 30-60 min, varias horas, reboot/autoboot,
  segunda placa/cartao, API indisponivel, rede oscilando, cache/offline longo,
  root read-only, corte seco, rollback real acionado por falha ou producao.

#### C6.5 - consolidacao do marco

Status: documentado em
`docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md`.

Objetivo:

- consolidar C6 como marco de desenvolvimento;
- registrar o que C6.3A/C6.4 provaram e o que nao provaram;
- separar desenvolvimento, homologacao e producao;
- mover testes longos para
  `docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md`.

Proximos caminhos possiveis, sem decisao automatica:

- C7 status/diagnostico de config real e appliance;
- C8 rollback/parada controlada;
- UX/setup/onboarding;
- `player_error`;
- integracao writer/onboarding;
- update/rollback;
- fila de homologacao.

### C7 - diagnostico/status sanitizado do appliance

Status: C7.0 contrato + snapshot local/offline criado em
`docs/product/36_C7_DIAGNOSTICO_STATUS_APPLIANCE.md`. C7.1 permanece futura.

Objetivo:

- criar contrato de diagnostico/status sanitizado do appliance;
- permitir entender estado publico de config, servico, launcher, player, MPV,
  renderer e privacidade sem ler conteudo de config real;
- tratar `/tmp/kiosky-status.json` como status bruto do player, lendo apenas
  campos allowlisted;
- observar `/data/config/config.json` somente por metadados, sem abrir o
  arquivo;
- gerar snapshot e resumo restritos em `/tmp`;
- preparar futura validacao read-only em placa.

Subfases:

- C7.0 - contrato + script local/offline
  `scripts/board/totem_appliance_status_snapshot.py`, com self-test por
  fixtures sinteticas em `/tmp`;
- C7.1 - futura validacao em placa read-only, se aprovada por roteiro proprio,
  sem journal bruto e sem publicar dados privados.

Validacao C7.0:

- self-test com fixtures contendo dados privados em campos desconhecidos;
- campo allowlisted suspeito redigido ou marcado com `privacy_scan=failed`;
- conteudo de config nao lido e `config_file_content_read=false`;
- out-dir fora de `/tmp` recusado;
- fontes ausentes viram `unavailable`/`unknown`;
- nenhum JSON bruto, log bruto, URL privada, payload, path privado, ID real,
  SSID, IP, hostname ou credencial e publicado.

Limite:

- C7 nao substitui observer prolongado, reboot/autoboot, segunda placa/cartao,
  root read-only, corte seco, rollback real ou homologacao;
- processos e `systemd` continuam fora de C7.0;
- a antiga frente de ativacao por codigo, login ou lista de ambientes fica para
  fase futura de UX/setup/onboarding, nao para este C7.

### C8 - Produto V1: operacao, onboarding e recuperacao

Status: visao documental criada; C8.1/C8.1.1/C8.2/C8.3/C8.4.0/C8.5.0/C8.5.1
funcional/mock local, preflight local ou sintetico local concluidos sem Wi-Fi
real, sem config real e sem acao real de manutencao.

Documentos:

- `docs/product/37_PRODUTO_V1_OPERACAO_ONBOARDING_RECUPERACAO.md`;
- `docs/product/38_FLUXO_PRODUTO_V1_ONBOARDING_MANUTENCAO_RECUPERACAO.md`;
- `docs/product/39_INVENTARIO_TELAS_ACOES_PRODUTO_V1.md`;
- `docs/product/40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md`;
- `docs/product/41_C8_1_SETUP_MINIMO_FUNCIONAL_SEM_WIFI_REAL.md`;
- `docs/product/42_C8_1_1_HANDOFF_SETUP_CONTRATO_CONFIG.md`;
- `docs/product/43_C8_2_SELECAO_AMBIENTE_MOCK_LOCAL.md`;
- `docs/product/44_C8_3_ROTACAO_MOCK_LOCAL.md`;
- `docs/product/45_C8_4_0_MANUTENCAO_MINIMA_MOCK_LOCAL.md`;
- `docs/product/46_C8_5_0_PREFLIGHT_SETUP_WRITER_CONFIG.md`;
- `docs/product/47_C8_5_1_ORIGEM_VALORES_PRIVADOS_CANDIDATA_REAL_SINTETICA.md`;
- `docs/product/48_C8_5_2_STATION_ID_OPCIONAL_CONTRATO_MINIMO.md`;
- `docs/product/49_C8_6_PREFLIGHT_HANDOFF_REAL_CONTROLADO.md`;
- `docs/product/50_C8_6_1_LIMPEZA_CANDIDATA_PRIVADA_TEMPORARIA.md`;
- `docs/product/51_C8_7_GATE_OPERACIONAL_FINAL_PRE_ESCRITA_REAL.md`;
- `docs/product/52_C8_8_PRIMEIRA_ESCRITA_REAL_INTEGRADA.md`;
- `docs/product/53_C8_9_START_CONTROLADO_POS_ESCRITA_REAL.md`;
- `docs/product/54_C8_10_REBOOT_AUTOBOOT_CONFIG_REAL.md`;
- `docs/product/55_C9_0_ACESSO_TEMPORARIO_SETUP_REDE_LOCAL.md`;
- `docs/product/56_C9_1_SETUP_LOCAL_PROPRIA_PLAQUINHA.md`;
- `docs/product/57_C9_1_1_VALIDACAO_HUMANA_WIZARD_LOCAL_HDMI.md`;
- `docs/product/58_C9_1_2_DIAGNOSTICO_PROPORCAO_VISUAL_POS_RESTAURACAO.md`;
- `docs/product/prototypes/v1-operacao-recuperacao/index.html`;
- `docs/product/prototypes/c8-1-setup-minimo/index.html`;
- `docs/product/prototypes/c8-2-selecao-ambiente/index.html`;
- `docs/product/prototypes/c8-3-rotacao/index.html`;
- `docs/product/prototypes/c8-4-manutencao-minima/index.html`.

Objetivo:

- consolidar a visao holistica de produto para operador nao tecnico;
- cobrir onboarding, operacao, manutencao, reset e recuperacao em campo;
- tratar rotacao, troca de ambiente e setup como jornada de produto, nao como
  comandos de bancada;
- separar camadas de recuperacao: automatica, operador, reset local fisico e
  restauracao de sistema;
- orientar MVP funcional e V1 final sem substituir homologacao.

Subfases propostas:

- C8.1 - setup minimo funcional sem Wi-Fi real, mock/local em `/tmp`;
- C8.1.1 - handoff setup minimo -> contrato C5.1;
- C8.2 - selecao de ambiente mock/local;
- C8.3 - rotacao mock/local, funcional/mock local;
- C8.4.0 - manutencao minima mock/local e contrato de acoes;
- C8.4 - reset leve e reiniciar player, ainda pendente de acao real aprovada;
- C8.5.0 - preflight setup -> writer/config, local/offline em `/tmp`;
- C8.5.1 - origem de valores privados e candidata real-sintetica em `/tmp`;
- C8.5.2 - `station_id` opcional e fora do caminho critico;
- C8.5 - integracao com writer/config;
- C8.6 - handoff real controlado, ainda sem escrita real;
- C8.6.1 - limpeza segura da candidata privada temporaria;
- C8.7 - gate operacional final antes da escrita real;
- C8.8 - primeira escrita real integrada, sem start do player;
- C8.9 - start controlado pos-escrita real, smoke curto;
- C8.10 - reboot/autoboot controlado com config real;
- C9.0 - acesso temporario ao setup pela rede local existente.
- C9.1 - setup local na propria plaquinha, tela HDMI + teclado USB.
- C9.1.1 - validacao humana do wizard local HDMI com teclado USB.
- C9.1.2 - diagnostico de proporcao visual pos-restauracao.

Validacao:

- nenhuma acao executa shell arbitrario;
- player nao e interrompido sem estado publico claro;
- diagnostico segue sanitizado;
- reset preserva ou apaga dados conforme escopo aprovado.

Limites:

- C8 documental nao altera NetworkManager, hotspot, portal, launcher,
  renderer, `systemd` ou `kiosky-player`;
- C8 documental nao escreve config real;
- C8 documental nao executa reset real;
- C8.1 pode ser validada na placa somente por smoke seguro em `/tmp`, sem
  servicos, sem rede operacional e sem player.

### C9.0 - acesso temporario ao setup pela rede local existente

Status: executado em desenvolvimento. Nao e servico permanente.

Objetivos:

- rodar o setup C8 temporariamente na placa;
- expor o setup em uma porta definida na rede local de bancada existente;
- permitir validacao humana da UX pelo navegador, fora do terminal;
- gerar candidata apenas em `/tmp`;
- encerrar o servidor ao final;
- preservar evidencia sanitizada.

Fora de escopo:

- Wi-Fi real;
- hotspot;
- portal definitivo;
- NetworkManager ou `nmcli`;
- writer/config real;
- `/data/config/config.json`;
- backups;
- parada/start de `kiosky-player.service`;
- alteracao do repo `kiosky-player`;
- producao.

### C9.1 - setup local na propria plaquinha

Status: implementado em desenvolvimento. Nao e producao.

Objetivos:

- provar o caminho obrigatorio de setup pela propria tela HDMI do totem;
- operar com teclado USB, sem Chromium, desktop, compositor ou shell livre;
- selecionar ambiente mock/local;
- selecionar orientacao da tela;
- revisar antes de gerar candidata;
- gerar candidata apenas em `/tmp`;
- validar C5.1 `allow-mock`;
- confirmar falha esperada de C5.1 `real-dry-run` por placeholders;
- preservar status/summary sanitizados.

Fora de escopo:

- writer/config real;
- `/data/config/config.json`;
- backups;
- parada/start de `kiosky-player.service`;
- player/MPV;
- NetworkManager, `nmcli`, Wi-Fi real, hotspot ou QR;
- backend;
- producao.

### C9.1.1 - validacao humana do wizard local HDMI

Status: passou tecnicamente com ressalvas de UX e warning visual
pos-restauracao. Nao e producao.

Objetivos:

- rodar o wizard local na placa com HDMI e teclado USB;
- validar legibilidade, navegacao e entendimento do fluxo por humano;
- gerar candidata somente em `/tmp`;
- preservar evidencia sanitizada;
- restaurar estado combinado se houver parada temporaria autorizada do player.

Fora de escopo:

- integracao com launcher;
- chamada automatica em `config_missing`;
- writer/config real;
- `/data/config/config.json`;
- backups;
- mudanca permanente de servico/player;
- NetworkManager, `nmcli`, Wi-Fi real, hotspot ou QR;
- backend;
- producao.

### C9.1.2 - diagnostico de proporcao visual pos-restauracao

Status: concluido como diagnostico controlado. Nao e producao.

Objetivos:

- separar stop/start do servico, wizard/openvt e modo de video como causas
  possiveis da percepcao de midia esticada;
- coletar snapshots sanitizados de servico, processos, TTY, framebuffer, DRM e
  propriedades MPV allowlisted;
- manter config real, writer, player repo, rede e Wi-Fi intocados.

Resultado:

- Fase A read-only mostrou que a midia ja parecia esticada;
- Fase B stop/start controlado nao mudou a percepcao;
- servico terminou `active/enabled`, `NRestarts=0`, player=1, MPV=1,
  renderer=0;
- modos HDMI observados nao incluiam Full HD;
- permanece recomendada uma frente futura de contrato visual/seletor por tipo
  de tela.

Fora de escopo:

- mudar resolucao;
- alterar flags MPV;
- alterar config real;
- rodar writer;
- repetir wizard/openvt sem nova autorizacao;
- liberar producao.

### C9 - Wi-Fi/portal/hotspot

Status: planejada.

Objetivo:

- retomar os gates C4 de Wi-Fi antes de transformar conectividade em produto;
- implementar Wi-Fi setup, portal local e/ou hotspot somente depois de adapter
  seguro, politica de credenciais, rollback e evidencia sanitizada;
- manter credenciais fora do Codex, logs, status publico e diagnostico;
- separar Wi-Fi local, internet e backend nas mensagens ao operador.

Validacao:

- falhas controladas de senha, rede ausente, timeout e conexao limitada;
- rede anterior preservada ate nova conexao passar, quando aplicavel;
- Ethernet preservada em bancada;
- nenhum SSID, senha, IP, hostname, MAC, BSSID, gateway ou DNS real em
  evidencia.

### C10 - manutencao/reset avancado

Status: planejada.

Objetivo:

- implementar manutencao protegida, factory reset, hard reset local, rollback
  de app e restauracao avancada;
- escolher metodo fisico de hard reset;
- impedir que reset vire shell;
- preservar ou exportar diagnostico sanitizado antes de apagamentos
  destrutivos, conforme politica;
- integrar com update/rollback e recovery image quando essas fases estiverem
  prontas.

Validacao:

- matriz de reset aprovada antes de implementacao;
- confirmacao forte em reset destrutivo;
- factory reset retorna para setup sem expor segredo;
- hard reset local e acionavel em campo e dificil de disparar por acidente;
- rollback/restauracao tem healthcheck publico e caminho de retorno.

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
