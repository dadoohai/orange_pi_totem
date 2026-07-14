# C18 Macro Steering

Estado inicial: 2026-07-05. Atualizado em 2026-07-14.

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
- com snapshot/base `player-runtime 9bebaf1` aprovado;
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

Status: fechado para o alvo exato C23 na prod8 em 2026-07-11.

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

## Checklist Contra Hiperfoco

Antes de abrir ou continuar uma tarefa, responder:

1. Qual marco macro esta sendo aproximado?
2. Essa tarefa reduz risco real ou entrega valor real?
3. Ela pode gerar regressao em player, boot, updater ou rollback?
4. Ela esta tentando resolver roadmap antes do minimo produtivo?
5. Se esta tarefa travar, qual vertical pode avancar em paralelo?

Se nenhuma resposta apontar para M2, M3, M4, M5 ou M8, a tarefa deve ser
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
5. Nao promover `prod13`. A sucessora estreita `prod14` foi construida e
   auditada: somente identidade, espera production de oito segundos, canario
   cobrindo a janela e rotacao controlada da credencial mudaram. C20.14, C25B,
   kernel, boot e pilha de video ficaram fixos; nenhum delta inesperado foi
   encontrado. Isso ainda nao constitui a prova fisica da prod14.
6. Gravar `prod14` e provar na placa: timer real, apply exato, no-op, rollback
   para o player embutido, reapply exato, freeze publico `rc=44`, reboot e
   playback estrito final. Somente esse E2E verde pode substituir `prod8` + C23
   como referencia de distribuicao.
7. Alinhar a release `totem-core stable` ao core embutido e provar seu timer,
   rollback e restauracao sem downgrade.
8. Fechar o minimo de M4 em paralelo: inventario, rollback owner, emergencia e
   criterio de pausa. Retomar M8 somente pelos gatilhos da decisao 198.
