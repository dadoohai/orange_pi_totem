# C18 Macro Steering

Estado inicial: 2026-07-05. Atualizado em 2026-07-17.

Este documento e o cerne direcionador da fase atual. Ele existe para impedir que
rodadas longas, auditorias e tarefas tecnicas desviem o trabalho do objetivo de
produto.

## Objetivo Macro

Colocar a C18 em producao escalavel com atualizacao remota automatica, mantendo
a placa funcional, recuperavel e sem regressao no player.

O cliente quer escala rapida e aceita risco de negocio. Nossa responsabilidade e
avancar rapido sem transformar pressa em caminho tecnico perigoso.

## Norte De Decisao

Quando houver duvida, priorizar nesta ordem:

1. Nao quebrar placa em cliente.
2. Manter rollback ou recuperacao clara.
3. Entregar capacidade real de atualizacao remota.
4. Separar o que e entrega imediata do que e roadmap.
5. Evitar perfeccionismo que nao muda risco real nem valor para o cliente.

## Regras De Foco

- Uma tarefa so importa se aproxima um marco macro.
- Auditoria deve responder risco real do marco atual, nao abrir melhorias
  aleatorias.
- Detalhe tecnico nao pode virar objetivo por si so.
- Se uma frente travar, outra vertical pode avancar desde que nao gere regressao.
- Producao inicial pode ter risco aceito; regressao silenciosa nao pode.
- Homologacao, publicacao e producao sao coisas diferentes.

## Marcos Macro

### M0 - Direcao Registrada

Status: feito.

O modelo de entrega C18 esta registrado:

- `orange_pi_totem` e o repo de entrega;
- `totem-core` atualiza produto/wizard/sistema Dadooh;
- `player-runtime` atualiza comportamento do player;
- `media-system` exige imagem;
- `field-data` nao e release de software;
- `kiosky-player` legado nao publica para C18.

### M1 - Decisao De Producao Com Risco Aceito

Status: feito.

A decisao atual e seguir para producao escalavel com auto-pull como padrao,
mesmo antes de dashboard, grupos e telemetria de frota.

Essa decisao nao libera caminho inseguro. Ela muda a ordem de entrega:

- primeiro linha produtiva simples;
- depois robustez de frota.

### M2 - Auto-Pull Real De `totem-core`

Status: feito em 2026-07-05.

Valor: permitir atualizar wizard, UX operacional, status e scripts Dadooh sem
operador.

Este marco fecha quando uma placa:

- recebe update remoto automaticamente pelo timer;
- valida pacote;
- aplica;
- continua com player saudavel;
- consegue rollback;
- preserva contrato de no-op para release repetida. A prova fisica especifica
  de timer repetido com a mesma release fica como hardening, nao como blocker
  deste marco.

### M3 - Imagem C18 De Producao

Status: feito em 2026-07-05.

Valor: novas placas saem prontas para cliente, com o player aprovado como
baseline inicial da imagem.

Este marco fecha quando existe imagem C18 de producao:

- sem marcador `not_for_production`;
- com player-runtime C25B exato aprovado;
- com auto-pull `totem-core` configurado;
- validada em placa gravada do zero;
- com runbook de gravacao/validacao de bancada. Checklist completo de
  fabrica/lote fica em M4.

### M4 - Operacao Inicial De Lote

Status: em andamento, leve e paralelo.

Valor: permitir entrega para cliente com risco conhecido e controle minimo.

Este marco fecha quando temos:

- inventario manual de placas;
- versao de imagem/core/runtime por placa;
- responsavel por rollback;
- procedimento de emergencia;
- criterio para pausar update;
- registro de risco aceito.

### M5 - Auto-Pull Publico De `player-runtime`

Status: fechado para o alvo exato C25B na prod15 em 2026-07-17. C23/prod8
permanece prova historica anterior.

Valor: permitir atualizar comportamento do player remotamente sem voltar ao
caminho legado.

Decisao de negocio em 2026-07-05: o cliente exige auto-pull tambem para
`player-runtime` e aceita o risco de uma primeira producao sem grupos,
dashboard ou telemetria de frota. Isso muda a prioridade: M5 deixa de ser
roadmap opcional e vira o proximo ponteiro de valor. A decisao nao autoriza
`latest` amplo, pacote futuro sem nova aprovacao, nem retorno ao caminho legado
`kiosky-player`.

Este marco nao fecha removendo o freeze de forma ampla. Fecha apenas quando
existir caminho publico por alvo exato, com:

- versao/hash autorizados;
- health real;
- rollback;
- quarentena de candidato ruim;
- no-op seguro;
- timer ou execucao automatica sem harness lab.

Estado atual em 2026-07-10: a autorizacao canonica no repo esta presa por hashes
ao C23 `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`. A placa prod7
ainda carrega no timer a autorizacao C22 embutida na imagem; ela so passa a
buscar C23 depois da reancoragem prod8. O caminho generico
`apply-github-latest --component player-runtime` continua congelado e a imagem
`homologation` nao carrega autorizacao production.

Na placa prod7, o timer real buscou a tag remota exata, aplicou C22 a partir do
bridge rollback-safe, fez no-op sem mutacao, voltou ao bridge por rollback
autorizado e restaurou C22. As cinco janelas curtas passaram health e mantiveram
o freeze publico `rc=44`. O marco nao abre `latest` nem autoriza pacote futuro.

Uma auditoria posterior encontrou reinicios internos do MPV entre e depois
dessas janelas. A RCA ao vivo confirmou backpressure no socket IPC persistente:
a fila de saida do MPV cresceu de `89088` para `213504` bytes, o MPV deixou de
responder e o novo processo voltou com fila zero. Portanto, M5 continua provando
a mecanica de entrega/retorno, mas nao prova limpeza continua de playback. A
evidencia esta em
`docs/evidence/c22-playback-ipc-backpressure/20260710T193847Z-verified-rca/`.

O fechamento de produto C23 removeu a conexao persistente nao lida no modo
fresh IPC. O pacote passou apply governado, rollback para C22, reapply e duas
janelas continuas de 10 minutos na placa. A janela decisiva percorreu nove
midias com zero `media_load_failed`, restart interno, acao de watchdog ou erro
de IPC; uma coleta paralela manteve o mesmo PID e `max_send_q=0` em 120
amostras. A evidencia, incluindo dois falsos vermelhos preservados e explicados,
esta em
`docs/evidence/c23-player-runtime-ipc-backpressure/20260710T195427Z-board-roundtrip/`.
O gate M5 preserva a claim mecanica historica e separa explicitamente a claim de
limpeza para distribuicao.

O alvo C23 foi publicado por tag exata com tres assets rebaixados e verificados;
`latest` permaneceu no `totem-core`. Evidencia:
`docs/evidence/c18-update-validation/20260710T211259Z-c23-exact-publication/`.
Esse ponteiro foi fechado na prod8 em 2026-07-11; a prova local anterior nao
foi usada como substituta da execucao production.

Preparacao prod8 em 2026-07-10: o pacote `totem-core`
`c21.9-prod8-pairing-restore-20260710T225825Z-665fc01` foi gerado do commit
`665fc01` e preso ao payload SHA256
`2c4123aed190c243e2e65bd1a477237717e93db14e69716dfb14f8c280fdd01b`.
Ele remove a expiracao local prematura do QR, mantem o servidor como fonte do
estado e limita o retorno ao player sem esconder o resultado. O builder da
prod8 esta preso a esse core e a autorizacao exata C23. A imagem foi construida
no commit `314ddd1`, SHA256
`6c3801d970d7bc5248f4c8fc5838b4233ea2e9e1f2120de4bffd7bea07f063ee`,
passou o gate `78/78` e duas auditorias do artefato real sem blocker para flash
de bancada. Evidencia em
`docs/evidence/c18-update-validation/20260710T232544Z-prod8-build-314ddd1/`.
Resultado em placa em 2026-07-11: a prod8 foi gravada do zero; wizard, QR,
writer privado e playback real passaram. O timer production original buscou e
adotou o C23 exato a partir do bridge rollback-safe. No-op, rollback autorizado
e restauracao passaram, e a janela final canonica de 600 segundos terminou sem
falha de midia, restart, watchdog, erro de IPC, GPU, MMC ou ext4. O gate M5
passou com `mechanics_passed=true`,
`product_distribution_cleanliness_passed=true` e zero blockers. Evidencia:
`docs/evidence/c18-update-validation/20260711T175205Z-prod8-m5-production-autopull-c23/`.

Achado paralelo, sem invalidar M5/C23: o timer independente de `totem-core`
selecionou a release stable remota antiga e o updater bloqueou corretamente o
downgrade sobre o C21.9 embutido (`rc=45`). A frente de publicacao/promotion de
`totem-core` deve alinhar o remoto ao core atual para remover a unit failed
recorrente; nao reabrir a prova de `player-runtime` por esse motivo.

Atualizacao de implementacao em 2026-07-10: a preparacao off-board de M5 foi
consolidada para o alvo C22. O repo agora possui:

- autorizacao canonica production exact-target gerada e validada contra
  manifest, payload e release gate;
- publisher estreito de tres assets que exige a autorizacao real, tag remota e
  `--latest=false`;
- perfil de imagem production apontando para a autorizacao C22 e incorporando o
  updater atual;
- coletor e gate de cinco fases: pre, auto-apply, no-op, rollback e restauracao;
- rollback publico autorizado que reinicia e verifica o player antes de
  reportar sucesso.
- imagem production que limpa identidade/tokens do seed, remove o firstboot e
  marcadores de laboratorio e gera chaves SSH unicas no device.

Auditoria do artefato `prod-5` encontrou firstboot privado, Wi-Fi/senhas de lab,
marcadores contraditorios e chaves SSH clonadas herdados da base. `prod-6`
removeu esses itens, mas a auditoria encontrou o servico do wizard ainda
chamando uma politica de homologacao; ambos estao bloqueados e preservados como
evidencia negativa. A referencia seguinte e `prod-7`, com politica de producao
para placa nova ou ja configurada e bloqueio executavel contra o helper lab. A
imagem tambem passa a embutir o pacote `totem-core`
`c21.8-production-settings-policy-20260710T161120Z-d79e4bd`, preso ao payload e
ao commit de origem, em vez de rotular o wizard atual como a antiga `c17.6`.
`prod-7` foi construida no commit `17b58c0`, SHA256
`c82c69341b4e1306899ae149d25a0c8953b42ee081291928adee8614d5b5b0b7`,
passou validacao offline e auditoria de artefato, foi gravada e fechou a prova
M5 na placa. A publicacao exata usou tres assets com hashes remotos conferidos e
nao moveu `latest`, que permaneceu no `totem-core`. A evidencia final esta em
`docs/evidence/c18-update-validation/20260710T190539Z-prod7-m5-production-autopull-c22/`.

`prod-7` nao e a imagem final de distribuicao: alem da retencao C23 de playback,
a senha root foi herdada da base e o onboarding revelou ajustes de prazo QR e
encerramento do wizard. Esses itens formam a rodada prod8; nao reabrem a prova
mecanica M5 do auto-pull C22.

Risco de primeira escala explicitamente aceito: acesso SSH por senha root
compartilhada de alta entropia permanece; credencial por device fica no M6.
Isso nao autoriza senha curta ou plaintext, Wi-Fi, identidade de laboratorio ou
chaves SSH reutilizadas entre placas.

### M6 - Robustez De Frota

Status: roadmap.

Valor: reduzir risco operacional depois da primeira escala.

Inclui:

- grupos/canary;
- dashboard;
- telemetria;
- kill switch;
- assinatura/attestation de frota e canais gerais alem do controle exact-target
  minimo promovido para M8;
- ponteiro stable generico alem do controle exact-target de `player-runtime`;
- A/B ou solucao equivalente para imagem/media-system.

Nao deve bloquear M2, M3 e M4 se a decisao de negocio continuar sendo avancar
com risco aceito.

### M7 - Display Profile / Compatibilidade De Tela

Status: frente aberta em 2026-07-06, subordinada ao macro.

Valor: reduzir risco de displays que nao negociam resolucao/taxa corretamente,
sem confundir problema de HDMI/sink com regressao de player ou OTA.

Registro da frente: `docs/C18_DISPLAY_PROFILE_STEERING.md`.

Direcao atual:

- observabilidade primeiro;
- perfil de tela somente depois de baseline real;
- forcar resolucao/taxa pertence a `media-system`/imagem, nao OTA comum;
- `totem-core` pode carregar diagnostico/status;
- `player-runtime` so entra se a mudanca for comportamento do player;
- a frente nao bloqueia M5/M4 salvo se virar risco direto de lote.

### M8 - Fonte Unica E Atualizacoes Futuras Do Player

Status: roadmap aprovado em 2026-07-12; implementacao adiada por prioridade de
produto.

Valor: permitir que C24, C25 e seguintes sejam desenvolvidos em uma fonte clara
e cheguem as placas sem regravar imagem para cada versao.

Este marco fecha quando:

- `kiosky-player/appliance-v0.1` e o `player-runtime` C23 estiverem
  reconciliados sem perder correcoes de nenhum lado;
- `orange_pi_totem` importar um commit exato e recusar edicao manual do
  snapshot;
- uma nova imagem carregar a chave publica e o controle remoto assinado;
- o controle selecionar somente alvo exato, nunca `latest` amplo;
- apply, pause, no-op, release ruim, rollback e quarentena passarem na placa;
- depois dessa imagem, uma nova versao do player chegar por OTA sem regravacao.

Plano de decisao e criterios:
`docs/product/198_C24_PLAYER_SOURCE_AND_SCALE_DECISION.md`.

### M9 - Wi-Fi De Produto E UX De Conexao

Status: em andamento desde 2026-07-16; itens 1 e 2 fechados na C21.20. O item
3 esta implementado e validado no pacote/OTA C21.21, com associacao em AP
aberto real ainda pendente. Os itens 4, 5 e 6 fecharam na candidata C21.22. O
item 7 fechou tecnicamente na candidata C21.23; falta a prova em portal real ou
emulado. O item 8, navegador restrito, continua separado.

Valor: permitir que um usuario configure a conectividade local sem caminho
impossivel, mensagem enganosa ou repeticao desnecessaria, preservando a rede
anterior quando a tentativa falhar.

Base ja fechada:

- C21.19 provou substituicao transacional do perfil Wi-Fi;
- sucesso exige ativacao e endereco IPv4;
- falha restaura o perfil anterior exato ou falha fechada;
- senha e identificadores privados nao entram em evidencia publica;
- player, Ethernet e demais servicos permanecem preservados.

Ordem macro:

1. tornar opcoes, cancelamento e mensagens fieis ao estado real;
2. reduzir passos e preservar contexto em nova tentativa;
3. suportar redes abertas comuns sem senha;
4. corrigir estados visuais;
5. explicar Ethernet, Wi-Fi e acesso ao servico Dadooh;
6. diferenciar falhas recuperaveis sem expor diagnostico bruto;
7. detectar portal cativo;
8. adicionar navegador temporario e restrito somente para portal;
9. fechar todos os caminhos na placa; logica/orquestracao segue por
   `totem-core`, e eventual runtime novo de navegador entra explicitamente na
   proxima imagem.

Fila detalhada e criterios de aceite:
`docs/C20_UX_ACCUMULATION_PLAN.md`.

Este marco nao reabre a mecanica transacional fechada em C21.19 salvo regressao
comprovada. Portal cativo e uma vertical posterior dentro do mesmo marco e nao
deve bloquear redes abertas comuns, copy correta e simplificacao do fluxo.

### M10 - Recuperacao Local Pelo Usuario

Status: fechado na `prod19` em 2026-07-19. Campanha fisica, publicacao stable,
prova remota, disparo natural correlacionado do timer, gate final e duas
auditorias independentes passaram sem blocker.

Valor: reduzir visitas tecnicas permitindo que uma pessoa nao tecnica entenda e
resolva localmente as falhas comuns, inclusive quando o totem estiver offline.

Direcao:

- `F10` continua sendo a unica entrada e abre diretamente o wizard atual;
- um controle discreto no wizard abre somente `Reiniciar totem`, `Desligar com
  seguranca` e `Restaurar para configuracao inicial`;
- nao criar `Configurar novamente`: o wizard atual ja cumpre esse papel sem
  apagar estado;
- nao criar home, `F12`, sexto passo, diagnostico granular ou restart manual do
  player; o sistema e a propria sessao F10 ja tratam o restart da exibicao;
- a restauracao remove config, vinculo, cache e estado operacional, mas
  preserva Wi-Fi, orientacao, identidade, imagem e toda a governanca OTA;
- o backend revoga somente a ativacao exclusiva atual em uma operacao
  idempotente; chave legada compartilhada perde apenas sua copia local, e uma
  credencial antiga nunca pode afetar uma ativacao posterior;
- intent persistido, bloqueio primeiro da config e retomada pelo firstboot gate
  impedem que queda de energia restaure dados antigos;
- entrega em duas releases coloca primeiro o motor invisivel no slot anterior;
  a acao so aparece quando `current` e `previous` entendem o reset, e auto-pull
  fica adiado pelo guard de settings ja enforcado enquanto houver operacao
  pendente;
- a imagem sucessora precisa provar em boot graph e placa que o firstboot
  recria esse guard antes dos agentes com atraso de 10/20 minutos. A `prod19`
  incorporou e provou essa ordem antes de expor a acao;
- reboot e poweroff passam pelo shell pai protegido, mantendo os locks de
  settings/update e sem comando livre vindo da UI;
- reinstalacao integral de boot/rootfs continua sendo regravacao externa;
  recovery partition ou raiz A/B permanecem em roadmap de imagem;
- rollback manual, shell e painel de logs permanecem fora da UI.

Plano e criterios: `docs/product/202_C26_LOCAL_SELF_SERVICE_RECOVERY_PLAN.md`.
Este marco e a proxima frente visivel de produto. O limite de polling GitHub
continua registrado, mas nao o bloqueia enquanto o lote esperado tiver apenas
duas ou tres placas por rede.

### M11 - Recuperacao Integral Do Sistema

Status: marco registrado para imagem futura; a bancada atual aceita
regravacoes durante o desenvolvimento.

Valor: permitir que o proprio usuario reinstale todo o sistema quando a
restauracao de configuracao nao for suficiente, reduzindo ainda mais visitas
tecnicas.

Direcao:

- nova imagem com recovery independente ou raiz A/B;
- acao local `Reinstalar sistema`, separada de `Restaurar para configuracao
  inicial` e protegida por confirmacao forte;
- imagem assinada/verificada, recuperacao de falha e queda de energia sem
  deixar a placa sem sistema inicializavel;
- politica explicita para preservar ou apagar configuracao/dados;
- campanha na placa com regravacao, imagem valida/invalida, interrupcao e boot
  final saudavel.

M11 nao bloqueia M10. A primeira instalacao dessa arquitetura exige uma
regravacao; depois, reinstalacoes completas podem ser locais e guiadas.

Fechamento M9.1-2 em 2026-07-16: C21.20 passou os gates `84/84`, foi bloqueado
pela policy stable, aplicado, rollbackado para C21.19 e reaplicado. A captura
real mostrou somente Ethernet ativa, Wi-Fi atual e escolha de outra rede; modo
de bancada ficou oculto. O player terminou ativo sem restart, o timer/policy
stable foi restaurado e a sessao visual nao alterou estado persistente.
Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T160720Z-c21-20-wifi-product-flow-board-e2e/`.

Fechamento tecnico M9.3 em 2026-07-16: C21.21 adicionou rede aberta sem senha,
IPv4 obrigatorio, rollback exato e retry direto, preservando WPA e privacidade.
Os gates de fonte e pacote passaram `84/84`; stable bloqueou com rc `41`; apply,
rollback para C21.20 e reaplicacao passaram com player sem restart. A placa
terminou em C21.21, policy/timer stable e ambas as conexoes atuais preservadas.
Falta somente repetir o fluxo com um AP aberto fisico; esse non-claim nao
impede avancar estados visuais e estado real da conexao. Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/`.

Fechamento M9.4-6 em 2026-07-16: C21.22 adicionou estados visuais completos,
estado real de transporte/acesso ao servico Dadooh e diagnostico/retry
sanitizado. Os gates passaram `84/84`; stable bloqueou com rc `41`; apply,
rollback para C21.21 e reaplicacao passaram. O pacote instalado gerou previews
e passou self-tests e coleta de rede somente leitura. A placa terminou em
C21.22, com C21.21 como retorno, player sem restart, conexoes preservadas e
policy/timer stable restaurados. Portal cativo e o proximo recorte; AP aberto
fisico continua pendente sem contaminar este claim. Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T202728Z-c21-22-wifi-state-recovery-board-e2e/`.

Fechamento M9.7 em 2026-07-16: C21.23 adicionou deteccao positiva de portal
cativo sem transformar falhas ambiguas em portal, bloqueou o prosseguimento
enquanto o acesso estiver pendente e preservou privacidade. Os gates de fonte e
pacote passaram `84/84`; stable bloqueou com rc `41`; apply, rollback para
C21.22 e reaplicacao passaram. O pacote instalado passou self-tests e a coleta
normal nao produziu falso portal. Player, redes, timer e policy terminaram
preservados. O portal fisico/emulado e o navegador permanecem non-claims.
Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/`.

## Consolidacao Prod15

Fechamento em 2026-07-17: `prod15` + C25B + C21.24 passa a ser a baseline de
distribuicao. A imagem exata foi recomputada, gravada do zero e concluiu wizard,
playback com HW decode, apply/no-op/freeze/rollback/restore do player-runtime,
reboot e no-op dos dois timers reais. Tres perspectivas independentes fecharam
sem blocker depois das correcoes de evidencia.

Limite de escala: polling sem token na API publica do GitHub falha fechado e
tenta novamente, mas compartilha cota por IP. Portanto a baseline esta fechada;
rollout concentrado sob o mesmo NAT nao deve ser prometido ate existir indice
stable sem polling ou credencial de leitura por dispositivo/coorte. Evidencia:
`docs/evidence/c18-update-validation/20260717T140500Z-prod15-postflash-board-validation/`.

## Consolidacao Prod19 / C26

Fechamento em 2026-07-19: `prod19` + C25B + C26.16 atual/C26.15 anterior passa
a ser a baseline de gravacao. A imagem exata foi gravada do zero e concluiu
boot, onboarding, playback com HW decode, fluxo `F10`, reinicio, restauracao
offline interrompida por corte real, retomada da mesma operacao, revogacao
exata, reativacao, roundtrip OTA, desligamento e boot final saudavel.

O SHA256 da imagem e
`991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`.
C26.15/C26.16 continuam embutidas como os dois slots de fabrica. A mesma arvore
executavel foi promovida como C26.17 stable, presa ao commit `0e02019`, e a
placa real baixou/aplicou essa release depois de rollback para C26.16; no-op,
gate operacional e health passaram. Clientes antigos ignoram C26.17 por
contrato e continuam encontrando C21.24. `prod15` e a baseline anterior;
reinstalacao completa permanece M11. Evidencia:
`docs/evidence/c26-local-recovery/20260719T162849Z-prod19-final-board-e2e/`.

## Checklist Contra Hiperfoco

Antes de abrir ou continuar uma tarefa, responder:

1. Qual marco macro esta sendo aproximado?
2. Essa tarefa reduz risco real ou entrega valor real?
3. Ela pode gerar regressao em player, boot, updater ou rollback?
4. Ela esta tentando resolver roadmap antes do minimo produtivo?
5. Se esta tarefa travar, qual vertical pode avancar em paralelo?

Se nenhuma resposta apontar para M2, M3, M4, M5, M8, M9 ou M10, a tarefa deve ser
pausada ou rebaixada.

## Proxima Decisao Padrao

Enquanto nada mudar, a ordem de execucao e:

1. Preservar C25 como entrada validada, sem reabrir microajustes salvo regressao
   ou blocker novo. C25A e o alvo C25B exato estao comprovados na placa em
   `docs/product/199_C25_VISIBLE_PRODUCT_STATES.md`.
2. `prod12` e C20.14 permanecem historico fechado: flash, wizard, playback,
   apply, rollback, reapply e reboot passaram sem regressao.
3. `prod13` foi construida, auditada e gravada. Boot, expansao, identidade SSH,
   wizard/QR/configuracao, retorno ao player, playback, timers, bloqueio de
   downgrade e guard de settings passaram. O alvo C25B exato tambem foi
   publicado sem mover `latest`.
4. O timer real da `prod13` encontrou um falso negativo estreito: o candidato
   tocava com HW decode e frames avancando, mas o health iniciou antes da
   publicacao inicial do status. A rejeicao foi fail-closed e colocou o alvo em
   quarantine. A arvore exata passou com espera inicial de oito segundos e o
   canario cobrindo toda a janela de health, sem afrouxar nenhum limite.
   Evidencia:
   `docs/evidence/c18-update-validation/20260714T145543Z-prod13-player-startup-window-rca/`.
5. Nao promover `prod13`. A sucessora estreita `prod14` foi construida,
   auditada e gravada. Seu player C25B concluiu timer real, apply, no-op,
   rollback ao fallback, reaplicacao e 600 segundos limpos, com freeze publico
   `rc=44` preservado.
6. O `totem-core` foi alinhado pela stable monotonicamente superior C21.12. O
   timer real aplicou a release, e no-op, rollback, restauracao e reboot final
   passaram sem restart do player.
7. Tres auditorias independentes e o gate global fecharam sem blocker.
   `prod14` + C25B + C21.12 substitui `prod8` + C23 como referencia de
   distribuicao.
8. Rodada atual: atacar a maior frente visivel, a jornada de ativacao e os
   estados do produto, mantendo M4 minimo em paralelo. Retomar M8 somente pelos
   gatilhos da decisao 198.
9. O incremento estreito C20.15 foi fechado como a candidata C21.13: hora de
   Sao Paulo sem mudar o UTC da placa, pendencias distintas no resumo e
   preservacao de ambiente/Wi-Fi somente quando o estado ativo e comprovado.
   Release gate `84/84`, sandbox, auditorias independentes, apply, rollback,
   reaplicacao, fluxo visual real e saude final passaram. Na placa sem perfil
   Wi-Fi dedicado, a reentrada falhou fechada como esperado; o caminho positivo
   ficou coberto pelos testes offline. Evidencia:
   `docs/evidence/c20-totem-core-ota/20260714T233330Z-c21-13-wizard-retained-status-board-e2e/`.
10. C21.13 e uma candidata validada e acumulavel, nao uma promocao publica.
    `prod14` + C25B + C21.12 continua sendo a referencia de distribuicao e
    retorno ate a proxima decisao explicita de stable/imagem. As proximas
    rodadas do wizard partem da C21.13 sem reabrir estes tres itens, salvo
    regressao comprovada.
11. C20.16 produziu a candidata
    `c21.14-wizard-connectivity-20260715T003032Z-4835ca8`, que passou o roundtrip
    de placa mas foi supersedida apos auditoria final. Os blockers foram falso
    `online` sem rota default e contador IPC sem teto. A correcao agora exige
    rota verificada, contador circular e orcamento total de leitura.
12. A sucessora C21.15 passou a validacao inicial, release gate
    `84/84`, sandbox, bloqueio stable, apply, rollback, reaplicacao, fluxo visual
    real e health final na placa, mas foi bloqueada na auditoria final: linhas
    de rota sem `RTF_UP` ou com mascara nao-default ainda podiam produzir falso
    `online`. O achado foi reproduzido. Um evento Panfrost isolado tambem ficou
    preservado sem RCA; seis ciclos adicionais nao o reproduziram. C21.13
    continua a candidata acumulada de homologacao, C21.12 continua stable de
    retorno e `prod14` continua imagem de referencia ate uma sucessora corrigida
    passar todo o ciclo.
    Evidencia:
    `docs/evidence/c20-totem-core-ota/20260715T014809Z-c21-15-wizard-connectivity-bounded-board-e2e/`.
13. C20.16 foi fechada na candidata C21.18. C21.16 e C21.17 foram
    supersedidas antes da placa para corrigir prioridade de entrada e
    apresentacao imediata; nenhuma foi promovida. C21.18 passou dois release
    gates `84/84`, bloqueio pela policy stable, apply, rollback para C21.13,
    reaplicacao, fluxo visual real e cancelamento sem escrita. O teste de 600
    segundos manteve recursos limitados e o teste instrumentado observou tres
    probes exatos em 60 segundos, com player ativo e zero restart. Um falso
    negativo do summary de playback durante transicao curta foi corrigido com
    fixtures positiva e negativa; os dados brutos originais ficaram
    preservados. Como o summary e fixo da imagem e nao pertence ao
    `totem-core`, a correcao entra obrigatoriamente na proxima imagem de
    referencia. A bancada terminou em C21.18 com C21.13 como previous.
    C21.12/prod14 continua a referencia publica e de retorno; nao houve stable,
    imagem nova ou promocao por inferencia. Evidencia:
    `docs/evidence/c20-totem-core-ota/20260715T055121Z-c21-18-wizard-connectivity-verified-board-e2e/`.
14. A frente de Wi-Fi persistente foi fechada na candidata C21.19. O perfil
    agora e substituido de forma transacional: conexao real com SSID contendo
    espacos finais foi mantida; uma rede inexistente restaurou byte a byte o
    perfil anterior. Stable bloqueou o prerelease, e apply, rollback para
    C21.18, reaplicacao, fluxo visual sem salvar e reboot passaram. A placa
    terminou com C21.19 current, C21.18 previous, timer stable ativo, Ethernet
    e Wi-Fi conectados e player sem restart. O ajuste estreito do summary de
    playback em `c075a55` e fixo de imagem e entra na proxima referencia; ele
    nao foi incluido por inferencia no pacote. C21.12/prod14 continua a
    referencia publica. Evidencia:
    `docs/evidence/c20-totem-core-ota/20260715T161137Z-c21-19-wifi-transactional-board-e2e/`.
15. M9 itens 1 e 2 foram fechados na candidata C21.20: gates `84/84`,
    bloqueio stable, apply/rollback/reapply, captura real e estado final da
    placa passaram sem restart do player ou escrita persistente na sessao
    visual. Rede aberta comum e o proximo item; estados, diagnostico, portal
    cativo e navegador restrito avancam depois, sem reabrir a base
    transacional C21.19. Cada recorte fechado entra no acumulo `totem-core` e
    na proxima imagem de referencia.
16. A acumulacao C21.23 foi promovida como C21.24 stable e embutida na prod15.
    A imagem passou validacao fisica, auditoria final e substitui a prod14 como
    referencia. A proxima frente de escala e retirar a descoberta de releases
    da cota publica compartilhada por IP; isso nao reabre wizard, playback,
    rollback ou a baseline ja comprovados.
17. Para o primeiro lote esperado de duas ou tres placas por rede, o limite
    publico compartilhado permanece conhecido, mas nao e a maior entrega agora.
    M10 foi fechado na `prod19`: as tres acoes locais, a retomada apos corte, a
    revogacao exata, o auto-pull C26.17 e a saude final passaram na placa. A
    proxima decisao volta para M4 e para a maior frente visivel de produto; M11
    continua roadmap e nao deve reabrir C26 sem regressao comprovada.
