# C18 Macro Steering

Estado inicial: 2026-07-05.

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

Status: marco ativo agora.

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

Estado tecnico em 2026-07-05: a direcao aprovada para M5 e o comando publico
`totem-updatectl apply-player-runtime-authorized`, alimentado por uma
autorizacao local hash-bound ao alvo `9bebaf1`. O caminho generico
`apply-github-latest --component player-runtime` continua congelado, e a imagem
`production` deve carregar um timer separado para esse alvo exato. A imagem
`homologation` nao deve carregar autorizacao nem timer de `player-runtime`.

Atualizacao em 2026-07-10: o sucessor C22
`c18.player-runtime-homolog-20260710-c22-c023eae` passou pacote local,
deep-health, apply, rollback e reapply na placa. Isso fecha C22, mas ainda nao
fecha M5. Antes de reancorar o timer e obrigatorio:

- publicar os tres assets exatos do pacote e provar selecao remota por tag;
- gerar autorizacao nova hash-bound aos hashes C22, sem `latest`;
- colocar a placa em estado anterior ao alvo para provar apply automatico real;
- executar no device o updater C22 endurecido, hoje ainda diferente do binario
  embarcado na placa;
- provar no-op, negativos de autorizacao/hash e rollback pelo caminho publico
  autorizado.

O timer atual continua apontando para `9bebaf1` e rejeita downgrade com
`rc=45`. Nao trocar apenas o arquivo de autorizacao para silenciar esse estado;
release, updater, autorizacao e teste do timer formam uma unica mudanca M5.

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
marcadores contraditorios e chaves SSH clonadas herdados da base; ele esta
bloqueado e preservado apenas como evidencia negativa. A referencia seguinte e
`prod-6`. A release C22 ainda nao foi publicada nem a imagem gravada. O proximo
limite real e construir/auditar `prod-6`, publicar o alvo exato sem mover
`latest` e executar as cinco fases na placa. Nao repetir
soak ou a matriz de power-loss nesta rodada; C22 mudou o payload do player, mas
o objetivo M5 e provar a entrega automatica e seu retorno usando as evidencias
rapidas ja fechadas para o pacote.

Risco de primeira escala explicitamente aceito: acesso SSH por senha root
compartilhada permanece; credencial por device fica no M6. Isso nao autoriza
embutir Wi-Fi, senha em plaintext, identidade de laboratorio ou chaves SSH
reutilizadas entre placas.

### M6 - Robustez De Frota

Status: roadmap.

Valor: reduzir risco operacional depois da primeira escala.

Inclui:

- grupos/canary;
- dashboard;
- telemetria;
- kill switch;
- assinatura consumida no device;
- ponteiro stable assinado;
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

## Checklist Contra Hiperfoco

Antes de abrir ou continuar uma tarefa, responder:

1. Qual marco macro esta sendo aproximado?
2. Essa tarefa reduz risco real ou entrega valor real?
3. Ela pode gerar regressao em player, boot, updater ou rollback?
4. Ela esta tentando resolver roadmap antes do minimo produtivo?
5. Se esta tarefa travar, qual vertical pode avancar em paralelo?

Se nenhuma resposta apontar para M2, M3, M4 ou M5, a tarefa deve ser pausada ou
rebaixada.

## Proxima Decisao Padrao

Enquanto nada mudar, a ordem de execucao e:

1. Atacar M5: auto-pull publico de `player-runtime` por alvo exato.
2. Fechar o minimo de M4 em paralelo: inventario, rollback owner, emergencia e
   criterio de pausa.
3. Preservar M2/M3 como baseline de producao: `totem-core` auto-pull e imagem
   C18 gravavel.
4. Evoluir M6 conforme escala e incidentes reais.
