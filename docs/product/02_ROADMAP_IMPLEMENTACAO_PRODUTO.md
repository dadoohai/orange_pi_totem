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
- C6.3-preflight - inspecao read-only da placa antes da escrita real;
- C6.3.0 - plano de execucao real com servico parado;
- C6.3 - execucao futura em placa de desenvolvimento;
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
  config seguem nao implementados ao final de C2.

## Fases C1-C8 - onboarding minimo refinado

Status: C1 documentada; C1.1 documental em preparacao; C2-C8 planejadas. Nao
implementadas operacionalmente.

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
- manter `api_url`, `environment_id` e `station_id` como mock/placeholders;
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
desenvolvimento em `/tmp` concluido; C6.3-preflight read-only na placa
concluido; C6.3.0 plano de execucao com servico parado concluido; C6.3
execucao real futura.

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
- rollback restauravel e documentado.

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
- placa de desenvolvimento prevista no preflight e autorizada antes de C6.3;
- evidencia esperada definida sem secrets;
- nenhuma config real lida, escrita ou alterada em C6.0.

#### C6.1-preflight - checklist e decisoes antes do writer real

Status: checklist documental criado em
`docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md`. Sem escrita real.

Objetivo:

- consolidar decisoes humanas obrigatorias antes de C6.2/C6.3;
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
- decisoes pendentes explicitadas antes de C6.2/C6.3.

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
- preparar C6.3 sem tocar `/data/config/config.json`.

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
- escrita real em `/data/config/config.json` continua bloqueada ate C6.3.

#### C6.2.1 - smoke do writer simulado na placa

Status: smoke test concluido na placa de desenvolvimento. Ainda sem escrita
real em `/data`.

Objetivo:

- provar que o writer C6.2 roda no ambiente real da Orange Pi;
- copiar scripts somente para `/tmp`;
- criar candidata sintetica nao-secret na placa;
- executar self-tests na placa;
- executar writer com destino, backup-dir e out-dir sob `/tmp`;
- manter C6.3 separada para a escrita real em `/data`.

Validacao:

- self-test do validador C5.1 passou na placa;
- self-test do writer C6.2 passou na placa;
- writer simulado passou na placa;
- config ativa simulada foi criada em `/tmp` com permissao restritiva;
- status e summary nao publicaram `api_key`/token;
- nada foi escrito em `/data`;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player`
  permaneceram fora do escopo.

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
- recomendacao para C6.3: executar com o servico parado ou bloqueio equivalente
  aprovado;
- C6.3 execucao real continua pendente.

#### C6.3.0 - plano de execucao com servico parado

Status: plano documental criado em
`docs/product/32_C6_3_EXECUCAO_CONFIG_REAL_SERVICO_PARADO.md`. Sem escrita real
em `/data` e sem tocar a placa.

Objetivo:

- transformar a recomendacao do preflight em plano de execucao real;
- exigir C6.3 com `kiosky-player.service` parado ou bloqueio equivalente;
- preservar backup e rollback antes da primeira escrita real;
- validar pos-escrita antes de qualquer decisao de iniciar player;
- manter decisao humana explicita para start do servico.

Validacao:

- C6.3-preflight read-only concluido e servico ativo/running detectado;
- escrita com servico ativo considerada bloqueada;
- sequencia futura documentada: preflight final, parada do servico, backup,
  candidata real privada, escrita atomica, pos-validacao, decisao de servico e
  evidencia sanitizada;
- C6.3 execucao real continua pendente.

#### C6.3 - execucao futura em placa de desenvolvimento

Status: futura. Nao executada.

Objetivo:

- executar writer real aprovado apenas na placa de desenvolvimento;
- executar com `/data/config/config.json` real somente em fase separada;
- executar com `kiosky-player.service` parado ou bloqueio operacional
  equivalente aprovado;
- validar escrita atomica, permissao e rollback;
- preservar ultima config valida quando existir;
- manter player bloqueado se a config falhar.

Validacao:

- execucao autorizada por humano apos C6.1-preflight, C6.2, C6.2.1,
  C6.3-preflight e C6.3.0;
- `/data/config/config.json` escrito somente pelo writer real aprovado;
- falha parcial nao vira config ativa;
- player inicia somente apos config real valida e decisao humana explicita;
- evidencia sanitizada sem `api_key`, URL privada, IDs reais ou payload.

### C7 - ativacao por codigo, login ou lista de ambientes

Status: planejada.

Objetivo:

- reavaliar alternativas mais completas depois do minimo funcionar;
- decidir entre codigo curto, login/lista de ambientes ou outro mecanismo;
- implementar, em fase futura, emissao de token de dispositivo/station pelo
  backend quando essa direcao for aprovada;
- integrar backend apenas com seguranca e expiracao definidas;
- remover necessidade de `environment_id` manual se a solucao escolhida
  substituir esse fluxo.

Validacao:

- operador continua sem manipular `api_key`;
- runtime do totem nao depende de token permanente de usuario humano;
- token de dispositivo/station e escopado, revogavel, rotacionavel e
  auditavel antes de producao/campo;
- erros de backend nao vazam URL, payload ou regra interna;
- fluxo nao regride C6.

### C8 - rotacao, troca de ambiente, manutencao e reset

Status: planejada.

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
