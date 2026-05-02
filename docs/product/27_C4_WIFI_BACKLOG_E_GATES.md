# C4 - backlog e gates Wi-Fi

Status: backlog documental. Nao executa acoes operacionais.

Data: 2026-05-02

## Objetivo

Este documento consolida o estado atual da frente Wi-Fi e explicita os gates
que ainda precisam ser retomados antes de tratar Wi-Fi como produto.

Objetivos:

- consolidar o que ja foi validado na frente Wi-Fi;
- listar pendencias futuras;
- impedir que C4 fique implicito no roadmap;
- permitir avancar C5/C6 sem esquecer gates Wi-Fi.

Este documento nao autoriza execucao operacional, nao conecta Wi-Fi, nao
altera NetworkManager, nao escreve config real, nao toca em launcher, renderer,
`systemd` ou `kiosky-player`, nao escreve em `/data` e nao substitui os planos
de execucao especificos de cada gate.

## Estado atual da frente Wi-Fi

Estado consolidado ate C4.5:

- C3 read-only foi validado como diagnostico sanitizado e sem alteracao de
  rede;
- C4.0 criou plano de bancada com Ethernet preservada, rollback e evidencia
  sanitizada;
- C4.1 remoto foi abortado corretamente antes de inserir senha;
- regra permanente: Codex nao recebe senha Wi-Fi;
- C4.2 hibrido/local foi validado com humano executando a etapa sensivel fora
  do Codex e Codex restrito a C3/evidencia sanitizada;
- C4.5 registrou que a configuracao Wi-Fi de teste foi removida por acao
  humana local;
- internet/backend ainda nao foram testados;
- Wi-Fi ainda nao e produto final.

Consequencias:

- o avanco por C5/C6 pode continuar, mas sem assumir Wi-Fi como producao;
- qualquer retomada C4 deve preservar a regra de credencial fora do Codex;
- qualquer evidencia de rede mutavel deve continuar sanitizada e sem output
  bruto.

## Gates futuros C4

### C4.6 - reboot/reconexao Wi-Fi

Objetivo:

- validar se Wi-Fi de teste reconecta apos reboot, sem perder a linha de vida
  Ethernet.

Escopo:

- usar rede de teste controlada;
- preservar Ethernet;
- usar C3 antes/depois/final;
- observar reconexao Wi-Fi apos reboot controlado, quando aprovado;
- manter internet/backend inicialmente fora do escopo.

Fora de escopo:

- testar backend;
- provar internet externa;
- alterar player, launcher, renderer ou `systemd`;
- usar rede real de cliente;
- publicar output bruto.

Criterios de aceite:

- C3 antes confirma Ethernet preservada;
- reboot e reconexao ocorrem somente com aprovacao humana e rollback definido;
- C3 depois/final mostra estado agregado coerente;
- Ethernet permanece preservada;
- nenhuma credencial ou identificador real e publicado.

Criterios de bloqueio:

- ausencia de acesso fisico;
- Ethernet ausente ou instavel;
- duvida sobre rollback;
- necessidade de senha pelo Codex;
- NetworkManager em estado ambiguo;
- qualquer output bruto com dado sensivel.

Evidencia esperada:

- README sanitizado com C3 antes/depois/final;
- resultado agregado de reconexao;
- confirmacao de Ethernet preservada;
- confirmacao de que internet/backend ficaram fora do escopo;
- estado final e rollback, se aplicado.

Dependencias:

- C3 operacional e sanitizado;
- politica de credencial C4.11 respeitada;
- perfil de teste controlado;
- aprovacao humana para reboot.

### C4.7 - falhas controladas

Objetivo:

- validar erros recuperaveis de Wi-Fi sem vazar senha, SSID ou output bruto.

Escopo:

- senha errada;
- rede ausente;
- timeout;
- erro recuperavel;
- estados publicos sanitizados;
- rollback do perfil de teste.

Fora de escopo:

- testar redes reais de cliente;
- publicar SSID, senha, IP, gateway, hostname, MAC, BSSID, DNS real ou nome de
  conexao;
- chamar backend;
- alterar config real;
- insistir em tentativas que possam travar a bancada.

Criterios de aceite:

- cada falha gera codigo publico recuperavel;
- Ethernet permanece preservada;
- perfil de teste pode ser removido;
- nenhuma senha ou identificador real aparece em evidencia;
- C3 final fica limpo ou com aviso publico esperado.

Criterios de bloqueio:

- senha precisaria passar pelo Codex;
- output bruto seria necessario para explicar a falha;
- falha afeta Ethernet ou conexao antiga;
- rollback incerto;
- erro deixa NetworkManager em estado desconhecido.

Evidencia esperada:

- matriz sanitizada de casos executados;
- C3 antes/depois/final;
- codigo publico observado;
- confirmacao de rollback ou estado final;
- privacidade revisada.

Dependencias:

- C4.11 politica de credenciais;
- C4.14 contrato de estados Wi-Fi;
- C4.16 padrao de evidencia.

### C4.8 - internet/backend com politica de privacidade

Objetivo:

- decidir e validar, com politica aprovada, quando `internet_state` e
  `backend_state` podem deixar de ser `not_checked`.

Escopo:

- decidir se havera teste externo;
- definir endpoint permitido ou backend permitido;
- definir timeout curto;
- publicar apenas estados agregados;
- manter URL privada, payload e headers fora de evidencia.

Fora de escopo:

- usar endpoint privado sem aprovacao;
- publicar URL, payload, token, header, resposta bruta ou erro bruto;
- transformar falha de internet em falha do player;
- fazer telemetria ampla.

Criterios de aceite:

- politica de privacidade aprovada antes do teste;
- endpoint permitido documentado sem segredo;
- timeout definido;
- `internet_state` e `backend_state` mudam de `not_checked` somente quando a
  politica permitir;
- evidencia contem apenas resultado sanitizado.

Criterios de bloqueio:

- endpoint nao aprovado;
- dependencia de URL privada;
- necessidade de publicar payload ou resposta bruta;
- risco de expor `api_key`, `environment_id` real ou identificadores de rede;
- teste externo sem criterio de timeout.

Evidencia esperada:

- decisao de politica;
- escopo do endpoint permitido;
- estados agregados antes/depois;
- timeout aplicado;
- ausencia de URL privada e payload em evidencia.

Dependencias:

- aprovacao de politica de privacidade;
- C3/C4 com campos de internet/backend revisados;
- C7 ou backend futuro, se o teste depender do produto real.

### C4.9 - adapter NetworkManager seguro

Objetivo:

- substituir comandos manuais por camada estreita e auditavel para operacoes
  Wi-Fi.

Escopo:

- listar redes de forma sanitizada;
- criar perfil dedicado;
- testar conexao;
- remover ou executar rollback;
- bloquear shell arbitrario;
- nunca logar senha.

Fora de escopo:

- expor shell;
- aceitar comando livre;
- alterar Ethernet;
- apagar conexoes antigas;
- registrar senha, SSID real ou output bruto;
- instalar pacotes.

Criterios de aceite:

- API estreita com operacoes nomeadas;
- validacao de argumentos e alvos;
- senha nunca aparece em log, status ou evidencia;
- rollback remove somente perfil criado pelo adapter;
- testes cobrem comandos proibidos e dados sensiveis.

Criterios de bloqueio:

- uso de shell arbitrario;
- comandos montados por string insegura;
- senha em argv, log ou arquivo;
- possibilidade de deletar conexao antiga;
- ausencia de rollback.

Evidencia esperada:

- especificacao da API;
- testes de guardrail;
- exemplo com placeholders;
- prova de que logs/status nao contem segredo;
- README sanitizado de rodada controlada.

Dependencias:

- C4.11 politica de credenciais;
- C4.12 ciclo de vida de perfis;
- C4.14 contrato de estados;
- revisao de seguranca antes de integrar com onboarding.

### C4.10 - integracao com fluxo de onboarding

Objetivo:

- ligar estados Wi-Fi ao setup sem misturar onboarding com player.

Escopo:

- conectar estados Wi-Fi ao fluxo de setup;
- respeitar renderer/player;
- preservar status publico;
- manter player fora de operacoes de configuracao;
- definir transicoes entre `config_missing`, setup e rede.

Fora de escopo:

- alterar reproducoes de midia sem necessidade;
- iniciar player antes de config valida;
- publicar dados privados no status;
- misturar comandos de rede com logica do player.

Criterios de aceite:

- setup usa estados Wi-Fi publicos;
- renderer e player continuam separados;
- status publico permanece allowlisted;
- erros de rede aparecem como mensagens publicas;
- nenhuma credencial passa pela UI/status de forma indevida.

Criterios de bloqueio:

- qualquer acoplamento que faca o player travar por rede;
- status publico com SSID, IP, URL ou segredo;
- renderer e player disputando tela;
- escrita real de config sem C6 aprovado.

Evidencia esperada:

- diagrama ou tabela de transicoes;
- mapping de estado interno para mensagem publica;
- validacao visual sanitizada;
- confirmacao de que player/renderer mantem regras existentes.

Dependencias:

- C4.9 adapter seguro;
- C4.14 contrato de estados;
- C5/C6 para config minima;
- regras ja validadas de renderer/player.

### C4.11 - politica de credenciais Wi-Fi

Objetivo:

- definir onde a senha Wi-Fi pode existir, onde nunca pode aparecer e como
  evidenciar sem segredo.

Escopo:

- local permitido para entrada de senha;
- locais proibidos para senha;
- quem insere a senha;
- apagamento/rotacao;
- evidencia sem segredo;
- regra permanente de Codex fora do canal de credencial.

Fora de escopo:

- armazenar senha em documentacao;
- enviar senha por chat, historico, script, README ou evidencia;
- usar senha real em exemplos;
- publicar SSID real ou nome real de perfil.

Criterios de aceite:

- politica documenta canal permitido e canais proibidos;
- Codex nao recebe senha;
- evidencias usam somente resultado sanitizado;
- rotacao/apagamento tem procedimento;
- revisao de privacidade e criterio bloqueante estao claros.

Criterios de bloqueio:

- senha em comando, argv, log, chat, transcript ou arquivo versionavel;
- necessidade de output bruto;
- ausencia de dono humano para inserir credencial;
- falta de procedimento de apagamento.

Evidencia esperada:

- documento de politica;
- checklist de execucao sem segredo;
- comprovacao sanitizada de que segredo nao foi registrado;
- resultado agregado de sucesso/falha.

Dependencias:

- postmortem C4.1;
- roteiro C4.2;
- padrao de evidencia C4.16.

### C4.12 - ciclo de vida dos perfis NetworkManager

Objetivo:

- definir criacao, uso, prioridade, remocao e convivencia de perfis Wi-Fi sem
  afetar Ethernet ou conexoes antigas.

Escopo:

- naming de perfil dedicado;
- `autoconnect`;
- prioridade;
- preservacao de Ethernet;
- remocao de teste;
- evitar duplicatas;
- nao apagar conexoes antigas.

Fora de escopo:

- deletar perfis historicos;
- modificar perfil Ethernet;
- publicar nomes reais de conexao;
- assumir que perfil de teste e perfil de producao.

Criterios de aceite:

- regra de naming usa placeholder/namespace controlado;
- adapter impede duplicatas indevidas;
- Ethernet nao e alvo de alteracao;
- perfil de teste tem remocao documentada;
- conexoes antigas ficam preservadas.

Criterios de bloqueio:

- alvo ambiguo para remocao;
- operacao que possa apagar conexao antiga;
- autoconnect/prioridade sem revisao;
- estado final com perfil de teste persistente sem decisao documentada.

Evidencia esperada:

- tabela de ciclo de vida;
- C3 antes/depois/final;
- confirmacao sanitizada de perfil removido ou mantido por decisao humana;
- ausencia de lista bruta de conexoes.

Dependencias:

- C4.9 adapter NetworkManager seguro;
- C4.11 politica de credenciais;
- C4.16 padrao de evidencia.

### C4.13 - esquecer Wi-Fi / reset de rede

Objetivo:

- permitir limpar perfil Wi-Fi e voltar a estado de setup sem perder Ethernet
  ou diagnostico.

Escopo:

- limpar perfil Wi-Fi dedicado;
- voltar para `config_missing` ou setup;
- preservar Ethernet;
- preservar diagnostico sanitizado;
- expor estado publico claro.

Fora de escopo:

- factory reset amplo;
- apagar config do player sem C6/C8;
- apagar conexoes antigas;
- apagar evidencias necessarias;
- reiniciar servicos sem plano.

Criterios de aceite:

- perfil Wi-Fi alvo e inequivoco;
- Ethernet permanece ativa;
- estado publico volta para configuracao pendente/setup;
- diagnostico final fica disponivel;
- dados sensiveis nao aparecem em logs ou evidencia.

Criterios de bloqueio:

- alvo de remocao ambiguo;
- risco de apagar Ethernet ou conexao antiga;
- ausencia de rollback;
- reset apaga evidencia necessaria;
- estado publico fica incoerente.

Evidencia esperada:

- C3 antes/depois/final;
- resultado sanitizado do reset;
- estado publico esperado;
- confirmacao de Ethernet preservada;
- confirmacao de diagnostico preservado.

Dependencias:

- C4.12 ciclo de vida de perfis;
- C4.14 contrato de estados;
- C8 reset/manutencao para escopo amplo.

### C4.14 - contrato de estados Wi-Fi

Objetivo:

- definir estados internos/publicos de Wi-Fi e suas mensagens ao operador.

Escopo:

- `wifi_not_configured`;
- `wifi_connecting`;
- `wifi_connected`;
- `wifi_connected_no_internet`;
- `wifi_error_bad_password`;
- `wifi_error_no_network`;
- `wifi_error_timeout`;
- `backend_unreachable`;
- mapeamento para mensagens publicas.

Fora de escopo:

- publicar SSID, IP, gateway, hostname, DNS, URL, payload ou segredo;
- usar erro bruto de ferramenta como mensagem publica;
- misturar estado de player com estado de rede sem contrato.

Criterios de aceite:

- cada estado tem significado claro;
- cada estado tem mensagem publica sanitizada;
- estados distinguem Wi-Fi local, internet e backend;
- timeouts e erros recuperaveis sao representados;
- status publico mantem allowlist.

Criterios de bloqueio:

- mensagem publica depende de dado sensivel;
- erro tecnico bruto aparece na tela/status;
- internet/backend confundidos com Wi-Fi local;
- ausencia de estado para falha recuperavel.

Evidencia esperada:

- tabela de estados;
- tabela de mensagens publicas;
- exemplos sanitizados;
- validacao contra C3/C4 e C5/C6.

Dependencias:

- C3 campos agregados;
- C4.7 falhas controladas;
- C4.8 politica de internet/backend;
- C4.10 integracao com onboarding.

### C4.15 - matriz de casos de campo

Objetivo:

- mapear casos reais de campo antes de liberar Wi-Fi como produto.

Escopo:

- DHCP falha;
- DNS falha;
- sinal fraco;
- 2.4 GHz vs 5 GHz;
- portal cativo;
- rede oculta;
- roteador reinicia;
- Wi-Fi cai/volta;
- Ethernet + Wi-Fi;
- sem Ethernet + Wi-Fi salvo.

Fora de escopo:

- resolver todos os casos em uma unica rodada;
- usar rede real de cliente como primeira evidencia;
- publicar identificadores reais;
- tratar portal cativo como suportado sem decisao propria.

Criterios de aceite:

- matriz lista comportamento esperado e bloqueios;
- casos essenciais tem estado publico definido;
- casos nao suportados sao marcados explicitamente;
- nenhum caso exige publicar dado sensivel;
- antes de campo, casos criticos tem evidencia ou decisao de nao suporte.

Criterios de bloqueio:

- campo sem plano para falhas comuns;
- portal cativo assumido como funcional;
- sem estado para DHCP/DNS ou queda/retorno;
- dependencia de output bruto para diagnostico.

Evidencia esperada:

- matriz de campo sanitizada;
- links para rodadas C3/C4 quando existirem;
- decisao de suporte/nao suporte por caso;
- lacunas remanescentes antes de campo.

Dependencias:

- C4.14 contrato de estados;
- C4.16 padrao de evidencia;
- C4.17 comportamento com player rodando.

### C4.16 - padrao de evidencia para rede mutavel

Objetivo:

- padronizar evidencia de qualquer rodada que altere rede.

Escopo:

- C3 antes;
- acao humana ou adapter;
- C3 depois;
- C3 final;
- resultado sanitizado;
- sem SSID, senha ou IP;
- rollback;
- estado final.

Fora de escopo:

- versionar output bruto;
- publicar lista de conexoes;
- publicar identificadores reais;
- aceitar evidencia sem rollback/estado final.

Criterios de aceite:

- toda rodada mutavel tem C3 antes/depois/final;
- acao sensivel e atribuida a humano ou adapter seguro;
- README registra resultado sem segredo;
- rollback ou decisao de manter perfil e documentada;
- estado final fica explicito.

Criterios de bloqueio:

- ausencia de C3 antes ou final;
- evidencia com SSID, senha, IP, gateway, hostname, MAC, BSSID, DNS real, URL,
  payload ou nome real de conexao;
- output bruto versionado;
- rollback nao documentado;
- estado final ambiguo.

Evidencia esperada:

- template de README;
- checklist de privacidade;
- resumo agregado;
- confirmacao de rollback/estado final;
- confirmacao de que nada fora do escopo foi alterado.

Dependencias:

- C3 diagnostico read-only;
- C4.11 politica de credenciais;
- C4.12 ciclo de vida de perfis.

### C4.17 - comportamento com player rodando

Objetivo:

- validar que perda/retorno de Wi-Fi nao trava o player nem viola o fluxo de
  status.

Escopo:

- perda de Wi-Fi durante reproducao;
- retorno de Wi-Fi;
- polling/API durante queda;
- cache offline;
- player nao deve travar por rede;
- estados publicos coerentes.

Fora de escopo:

- alterar player sem plano proprio;
- exigir backend online para reproducao local;
- publicar URLs, payloads ou paths privados;
- misturar reset de rede com controle de player.

Criterios de aceite:

- player continua operando conforme cache/config disponivel;
- falha de rede aparece como estado publico apropriado;
- retorno de Wi-Fi recupera polling/API sem travar player;
- ausencia de internet/backend nao derruba renderer/player;
- logs/evidencias seguem sanitizados.

Criterios de bloqueio:

- player trava ou reinicia em loop por queda de rede;
- status publico vaza URL, payload ou path privado;
- perda de Wi-Fi corrompe config/cache;
- recuperacao depende de comando manual sem contrato.

Evidencia esperada:

- roteiro de teste com player rodando;
- estado antes/durante/depois;
- comportamento de cache/polling;
- confirmacao de ausencia de vazamento;
- criterios de rollback.

Dependencias:

- C4.14 contrato de estados Wi-Fi;
- C4.15 matriz de campo;
- C6 config real, quando o teste depender de player com config ativa;
- politica de backend/internet C4.8.

## Priorizacao

Essencial antes de Wi-Fi virar produto:

- C4.6;
- C4.7;
- C4.9;
- C4.11;
- C4.12;
- C4.14.

Importante antes de campo:

- C4.8;
- C4.13;
- C4.15;
- C4.16;
- C4.17.

## Relacao com C5/C6

C5/C6 podem avancar sem fechar todos os gates C4, porque C5 valida writer mock
em `/tmp` e C6 trata escrita real de config. Esses fluxos nao precisam provar
Wi-Fi completo para continuar, desde que nao assumam Wi-Fi como producao.

Regras para manter essa separacao:

- C5/C6 nao devem assumir Wi-Fi como producao;
- C5/C6 nao devem depender de SSID, senha, IP, URL privada ou backend real em
  evidencia;
- C5 continua mock em `/tmp` e sem config real;
- C6, quando retomado, deve validar config real sem misturar credencial Wi-Fi;
- antes de campo, Wi-Fi precisa voltar a estes gates;
- onboarding final depende especialmente de C4.9, C4.10 e C4.14.

Assim, o avanco atual pode seguir por C5/C6, mas a liberacao de produto/campo
deve reabrir C4 nos gates acima.
