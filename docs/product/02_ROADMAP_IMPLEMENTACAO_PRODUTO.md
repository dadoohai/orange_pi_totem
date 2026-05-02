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

## Fase C0/C1 - planejamento e refinamento minimo de onboarding

Status: C0 documentado e C1 em refinamento documental. Nao implementa
mudancas operacionais.

Documentos:

- `docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md`;
- `docs/product/13_RISCOS_ONBOARDING_WIFI_CONFIG.md`;
- `docs/DECISIONS/ADR-0008-onboarding-wifi-config.md`;
- `docs/product/14_C1_CONFIG_MISSING_MINIMAL_ONBOARDING.md`;
- `docs/product/15_C1_MINIMAL_USER_FLOW.md`;
- `docs/product/16_C1_MINIMAL_STATE_MACHINE.md`;
- `docs/DECISIONS/ADR-0009-minimal-config-environment-id.md`.

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

Fora de escopo em C0/C1:

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
- `api_key` fica fora da UI e deve vir de env, mock ou provisionamento separado;
- ativacao por codigo, login e lista de ambientes ficam como alternativas
  futuras;
- primeira inicializacao completa de cartao Armbian virgem fica para fase
  posterior.

Sequencia incremental refinada:

- C1 - escopo e fluxo minimo Wi-Fi + `environment_id` documentado;
- C2 - mock visual/formulario sem alterar rede;
- C3 - diagnostico Wi-Fi read-only;
- C4 - Wi-Fi controlado em bancada com Ethernet preservada;
- C5 - config writer minimo/mock;
- C6 - salvar config minima real com validacao e rollback;
- C7 - ativacao por codigo, login ou lista de ambientes;
- C8 - rotacao, troca de ambiente, manutencao e reset.

Criterios de aceite:

- documento de arquitetura do onboarding aprovado;
- ameacas principais de privacidade e credenciais listadas;
- estados publicos e mensagens definidos;
- plano de teste inclui senha incorreta, rede ausente, reboot, Ethernet
  presente e ausencia de internet;
- plano preserva a separacao entre homologacao `v0.1-rc1`, desenvolvimento
  pos-RC1 e producao futura.
- Wi-Fi setup real, hotspot, portal local, ativacao backend e escrita real de
  config seguem nao implementados ao final de C1.

## Fases C1-C8 - onboarding minimo refinado

Status: C1 documental; C2-C8 planejadas. Nao implementadas.

Estas fases substituem a sequencia anterior mais ampla para evitar que hotspot,
ativacao backend, writer real, rotacao e manutencao avancem juntos.

### C1 - escopo e fluxo minimo documentado

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

### C2 - mock visual/formulario sem alterar rede

Objetivo:

- criar mock de tela/formulario para Wi-Fi e `environment_id`;
- nao listar redes reais;
- nao pedir senha real persistida;
- nao alterar NetworkManager;
- nao escrever config real.

Validacao:

- previews e/ou mock local sem secrets;
- textos publicos claros para operador nao tecnico;
- renderer/setup continua separado do player.

### C3 - diagnostico Wi-Fi read-only

Objetivo:

- mostrar estado de rede de forma apenas leitura;
- diferenciar Wi-Fi associado, IP obtido, internet basica e backend futuro;
- nao derrubar Ethernet, Wi-Fi ou SSH de bancada;
- nao publicar SSID real, senha, IP publico ou hostname.

Validacao:

- prova de que nenhum comando altera conexoes;
- diagnostico sanitizado;
- falhas aparecem como codigos publicos.

### C4 - Wi-Fi controlado em bancada com Ethernet preservada

Objetivo:

- testar alteracao real de Wi-Fi apenas em bancada;
- preservar Ethernet como recuperacao;
- usar snapshots antes/depois;
- documentar rollback de conexoes.

Validacao:

- senha errada recupera sem vazar credencial;
- conexao sem internet mostra erro claro;
- Ethernet nao e derrubada indevidamente;
- reboot nao deixa NetworkManager em estado ambiguo.

### C5 - config writer minimo/mock

Objetivo:

- criar caminho de validacao de config minima sem substituir config ativa real;
- simular injecao de `api_key` por env, mock ou provisionamento separado;
- validar `environment_id` por formato minimo;
- exercitar erro de `api_key` ausente.

Validacao:

- nenhuma config parcial vira ativa;
- erros sao publicos e sanitizados;
- writer mock nao imprime secrets.

### C6 - salvar config minima real com validacao e rollback

Objetivo:

- gravar config minima real somente depois de C5;
- validar todos os campos obrigatorios antes de substituir;
- usar escrita atomica;
- preservar ultima config valida quando existir;
- iniciar player apenas depois de config valida.

Validacao:

- queda no meio nao deixa config parcial ativa;
- `api_key` externa ausente bloqueia salvamento ou inicio do player;
- renderer/setup para antes do player;
- rollback restauravel e documentado.

### C7 - ativacao por codigo, login ou lista de ambientes

Objetivo:

- reavaliar alternativas mais completas depois do minimo funcionar;
- decidir entre codigo curto, login/lista de ambientes ou outro mecanismo;
- integrar backend apenas com seguranca e expiracao definidas;
- remover necessidade de `environment_id` manual se a solucao escolhida
  substituir esse fluxo.

Validacao:

- operador continua sem manipular `api_key`;
- erros de backend nao vazam URL, payload ou regra interna;
- fluxo nao regride C6.

### C8 - rotacao, troca de ambiente, manutencao e reset

Objetivo:

- tratar funcoes fora do minimo C1;
- planejar rotacao de tela;
- planejar troca de ambiente apos player rodando;
- planejar manutencao limitada;
- planejar reset leve e factory reset com confirmacao forte.

Validacao:

- nenhuma acao executa shell arbitrario;
- player nao e interrompido sem estado publico claro;
- diagnostico segue sanitizado;
- reset preserva ou apaga dados conforme escopo aprovado.

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
