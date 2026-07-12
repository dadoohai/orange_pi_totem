# C20 UX Accumulation Plan

Estado: 2026-07-07.

Objetivo: evoluir a experiencia visual e operacional do produto em rodadas
pequenas de `totem-core`, validando cada uma na placa e acumulando o conjunto
para um pacote/update consolidado e para a proxima imagem de referencia.

Atualizacao em 2026-07-12: C19/C20 e o pareamento C21 ja estao consolidados no
`totem-core` C21.11 stable e aplicados na placa. O pendente nao e reconstruir
esses pacotes; e fechar a jornada E2E na versao atual, evoluir somente estados
visiveis de impacto real e incorporar o conjunto na proxima imagem de
referencia. A arquitetura C24 de player foi preservada como roadmap e nao
compete com esta fila de UX.

## Direcao

- UX de produto, nao dashboard tecnico.
- Uma tarefa principal por tela.
- Texto curto, legivel e util em 1024x768.
- Sem excesso de atalhos, bullets ou diagnostico bruto.
- Cada rodada deve poder ser validada visualmente e revertida.
- C20 acumula melhorias; nao publica/promove cada uma isoladamente por padrao.
- Cada melhoria fechada por OTA entra no pacote `totem-core` acumulado e fica
  marcada para a proxima imagem de referencia.

## Leituras De Auditoria

Auditorias independentes usadas nesta abertura:

- UX/produto: priorizar hierarquia, densidade, navegacao, feedback e status
  publico;
- QA visual: transformar o runbook C19 em protocolo auditavel por rodada;
- escopo/risco: manter `totem-core` estreito e separar Wi-Fi real, display e
  player;
- auditor externo Claude Sonnet: achado visual concreto de sobreposicao entre
  painel lateral e preview na primeira tela de orientacao em paisagem.

Decisao central: incorporar o achado de sobreposicao como primeira correcao
C20, sem aceitar redesign amplo nesta rodada.

## Escopo Permitido

Entra em `totem-core`:

- wizard/settings;
- splash/transicoes visuais;
- telas publicas de status;
- foco, paginacao, copy, estados visuais e cancelamento;
- diagnostico publico read-only;
- evidencia, docs e checks de QA visual.

Fora deste pacote:

- `player-runtime`, MPV, playlist, timing ou comportamento de playback;
- display/EDID/resolucao/kernel/ffmpeg/hwdecode/imagem;
- Wi-Fi real persistente, NetworkManager real ou escrita de config real;
- midia, playlist, cache, dados de campo;
- updater, timer, policy, publish/stable, salvo empacotamento final governado.

## Verticais C20

### V2 - Hierarquia De Acao E Produto Visual

Status: validada para acumulo em 2026-07-08.

Objetivo do usuario: a tela deve parecer mais produto profissional e menos
formulario tecnico, mantendo eficiencia.

Mudancas aplicadas:

- cards mais solidos, com marcador retangular renderizavel no framebuffer;
- remocao da dependencia visual de `<circle>` nos cards;
- rodape transformado em barra de acoes, com acao principal em destaque;
- protecao para `Esc` nao sumir silenciosamente em rodapes longos;
- campo de senha/entrada reintegrado ao tema escuro;
- revisao reescrita como tela de decisao: `Pronto para concluir`;
- paleta escura ligeiramente mais profunda e focada em acento ciano.

Aceite:

- self-test do wizard verde;
- preview, Wi-Fi preview, replay e galeria verdes;
- capturas reais de orientacao, Wi-Fi, senha e revisao em paisagem;
- hash do wizard da placa restaurado apos as sessoes;
- player ativo, settings inativo e sem lock/request apos as sessoes.

Evidencia:

- `docs/evidence/c20-visual-qa/20260707T235900Z-c20-v2-pdca1-board-preview/`;
- `docs/evidence/c20-visual-qa/20260708T000400Z-c20-v2-pdca2-board-preview/`;
- `docs/evidence/c20-visual-qa/20260708T000700Z-c20-v2-review-decision-board/`;
- `docs/evidence/c20-visual-qa/20260708T001336Z-c20-v2-final-local-verification/`.

Non-claims:

- nao publica OTA;
- nao valida fluxo completo por teclado;
- nao grava configuracao real;
- nao altera Wi-Fi real, display/EDID, player-runtime, updater ou imagem.

### V0 - Sobreposicao No Preview De Orientacao

Status: validada para acumulo em 2026-07-07.

Objetivo do usuario: a primeira tela do wizard deve parecer limpa e legivel.

Achado:

- em paisagem, o painel lateral "Tela" pode invadir a caixa de preview;
- evidencia visual: `docs/evidence/c19-visual-qa/20260707T194848Z-wizard-navigation/01-orientation-visible.jpg`;
- a correcao deve ser localizada na composicao da tela de orientacao, sem
  redesenhar o wizard inteiro.

Aceite:

- captura real da orientacao em paisagem sem sobreposicao;
- preview em retrato sem sobreposicao;
- self-test do wizard verde;
- preview auto-exit restaura player;
- non-claim: nao valida fluxo interativo completo por teclado.

Evidencia:
`docs/evidence/c20-visual-qa/20260707T192000-c20-v0-final-preview-board/`.

### V1 - Hierarquia E Densidade Do Wizard

Status: validada para acumulo em 2026-07-07.

Objetivo do usuario: entender rapidamente a etapa atual e agir sem ler texto
demais.

Mudancas aplicadas:

- canvas nativo alinhado ao framebuffer atual: `1024x768` em paisagem e
  `768x1024` em retrato;
- cabecalho, etapa, titulo, area principal e painel lateral recalibrados para
  1024x768;
- lista Wi-Fi em paisagem mantida com 4 itens, descricao mais curta e rodape
  em uma linha;
- nota de layout fica restrita a etapa de orientacao;
- tela de revisao passa a mostrar resumo publico no corpo principal;
- geradores offline C20/C19 alinhados com a correcao V0.

Aceite:

- captura real de orientacao, Wi-Fi e revisao em paisagem;
- sem sobreposicao com rodape;
- rodape em uma linha;
- lista Wi-Fi continua com 4 itens em paisagem;
- nenhuma tela vira manual tecnico.

Evidencia:

- `docs/evidence/c20-visual-qa/20260707T224916Z-c20-v1-layout-preview-board/`;
- `docs/evidence/c20-visual-qa/20260707T225600Z-c20-v1-wifi-landscape-board-clean/`;
- `docs/evidence/c20-visual-qa/20260707T225800Z-c20-v1-review-landscape-board/`.

Non-claims:

- nao publica OTA;
- nao valida fluxo completo por teclado;
- nao altera Wi-Fi real, display/EDID, player, updater ou imagem;
- nao substitui pacote consolidado de `totem-core`.

### V3 - Navegacao E Cancelamento Previsiveis

Objetivo do usuario: saber quando esta voltando uma etapa e quando esta saindo
da configuracao.

Mudancas candidatas:

- tornar `Esc`, voltar e cancelar semanticamente consistentes;
- diferenciar retorno local dentro da lista Wi-Fi de cancelamento global;
- revisar rodapes para dizer so o comando essencial.

Aceite:

- matriz por tela: Enter, setas, Esc, voltar/cancelar;
- cancelamento global sempre restaura player;
- `totem-open-settings.service` sem `failed`;
- lock/request ausentes apos saida;
- nenhuma escrita real de Wi-Fi/config.

### V4 - Entrada E Saida De Settings

Objetivo do usuario: perceber que a placa entendeu o comando e voltou para a
midia sem parecer travada.

Mudancas candidatas:

- feedback curto ao abrir configuracao;
- transicao curta ao sair/salvar/voltar para midia;
- evitar tela intermediaria parada como se fosse erro.

Aceite:

- F10 abre feedback visivel rapido;
- saida retorna ao player `playing`;
- splash/transicao nao fica tempo demais na tela;
- nenhum terminal aparente.

### V5 - Status Publico Simplificado

Objetivo do usuario: entender o estado da placa em poucos segundos quando nao
ha midia normal.

Mudancas candidatas:

- revisar `config_missing`, `loading_content`, `player_error`,
  `maintenance_placeholder`;
- mostrar estado, acao esperada e codigo publico curto;
- remover detalhes internos que nao ajudam o usuario.

Aceite:

- leitura em ate 3 segundos;
- sem SSID, IP, token, API URL, UUID privada ou config real;
- renderer nao disputa com o player;
- evidencia visual por estado.

### V6 - Revisao E Conclusao Sem Dados Privados

Objetivo do usuario: confirmar o que sera aplicado sem expor segredo nem
tecnicismo.

Mudancas candidatas:

- tela final com escolhas publicas: orientacao, modo de conexao e ambiente;
- diferenciar `dry-run`, homologacao e escrita real com texto curto;
- deixar a acao principal inequivoca.

Aceite:

- sem senha, SSID sensivel, token, IP privado ou API URL;
- acao principal clara;
- cancelamento ainda restaura player;
- summary evidencia non-claims.

### V7 - Splash E Gramatica Visual Consistente

Objetivo do usuario: reconhecer estados do produto sem ruido visual.

Mudancas candidatas:

- padronizar mensagens de boot, setup, saving, config pending e shutdown;
- manter branding discreto;
- nao usar progresso falso.

Aceite:

- capturas reais ou framebuffer visivel dos modos tocados;
- sem glifos quebrados;
- orientacao respeitada;
- mensagens curtas e consistentes.

### V8 - Contrato De QA Visual Acumulavel

Objetivo do time: qualquer rodada UX so entra no acumulo com evidencia
comparavel.

Status: primeira rodada E2E executada em 2026-07-08.

Evidencia:
`docs/evidence/c20-e2e-rc/20260708T052100Z-c20-8-e2e-audit/`.

Resultado consolidado:

- replay offline do wizard passou;
- probe em placa abriu wizard, navegou ate revisao, bloqueou incompleto e
  cancelou;
- F10 por evento de teclado abriu settings e repetiu o mesmo caminho critico;
- apos espera curta, player ficou ativo, settings inativo, sem lock/request e
  guard verde;
- fluxo valido foi coberto por scripted `candidate-only`, sem writer real.

Nao-claims:

- sem escrita real de Wi-Fi/config;
- sem stable/producao;
- sem player-runtime;
- sem display/kernel/MPV;
- sem timezone/NTP/RTC.

Mudancas candidatas:

- criar manifesto por rodada visual;
- classificar evidencias como captura real decisiva, preview auxiliar ou
  invalida;
- padronizar checklist e hashes de imagens.

Aceite:

- cada rodada tem `summary.md`, `operation.log`, status before/opened/after,
  imagens `*.png` e `*-visible.jpg`;
- screenshot decisivo vem da placa durante sessao aberta;
- SVG nunca e decisivo;
- retorno ao player e guardrails registrados.

### V9 - Data/Hora Discreta No Wizard

Status: implementado, empacotado por `totem-core` e aplicado na placa em
2026-07-08.

Objetivo do usuario: permitir que operador/suporte vejam data/hora durante a
configuracao local sem poluir a tela nem criar uma nova decisao desnecessaria.

Direcao consolidada:

- primeira rodada read-only e visual;
- exibir data/hora como metadado passivo no cabecalho comum;
- em paisagem, reutilizar o slot de nota do cabecalho;
- em retrato, colocar data/hora na linha superior do cabecalho, a direita do
  titulo;
- exibir `DD/MM/YYYY HH:MM` em todas as etapas, inclusive `Tela`;
- nao usar mais `Layout paisagem/retrato` nesse slot;
- se o relogio for implausivel, exibir `Hora nao ajustada`;
- nao usar rodape nem painel lateral para informacao passiva;
- nao criar botao de ajustes nesta etapa;
- nao configurar hora, timezone, NTP, RTC ou servicos do sistema via wizard.

Risco principal:

- se o relogio do sistema estiver errado, a UI pode dar falsa confianca. A
  mitigacao minima e nao mostrar segundos, nao prometer sincronismo e trocar
  data implausivel por `Hora nao ajustada`.

Auditoria/convergencia:

- mockup inicial foi insuficiente porque nao tratava a colisao com `Layout
  paisagem` na etapa Tela;
- Sonnet trouxe esse achado e a regra final incorporou a exclusao por etapa;
- a R2 foi aprovada parcialmente, mas apontou que o retrato deixava a data/hora
  solta entre os passos e o titulo;
- a R3 moveu a data/hora de retrato para a linha superior do cabecalho e foi
  aprovada por tres auditores xhigh sem blockers.

Evidencia visual:

- `docs/evidence/c20-visual-qa/20260708T-c20-7-clock-pdca-design/round3/`.

Atualizacao C20.8:

- a excecao da etapa `Tela` foi removida por decisao de produto;
- o slot do cabecalho passa a ser exclusivamente de data/hora ou `Hora nao
  ajustada`;
- a informacao de orientacao continua disponivel no conteudo/preview da propria
  tela, sem ocupar o metadado global do cabecalho.

Evidencia de implementacao/aplicacao:

- pacote: `c20.8-clock-all-steps-20260708T045317Z-661c582`;
- gate OTA verde: 66 checks;
- current da placa: `releases/c20.8-clock-all-steps-20260708T045317Z-661c582`;
- rollback/previous: `releases/c20.7-clock-metadata-20260708T042733Z-b9d8a00`;
- galeria visual gerada na placa:
  `docs/evidence/c20-totem-core-ota/20260708T045500Z-c20-8-clock-all-steps-board-apply/direct-preview-svgs/`;
- PNGs renderizados para inspeccao:
  `docs/evidence/c20-totem-core-ota/20260708T045500Z-c20-8-clock-all-steps-board-apply/rendered/`;
- diretorio de evidencia:
  `docs/evidence/c20-totem-core-ota/20260708T045500Z-c20-8-clock-all-steps-board-apply/`.

Aceite futuro:

- self-test cobre formato/ausencia de overflow;
- preview/galeria mostram cabecalho em paisagem e retrato;
- captura real da placa confirma legibilidade;
- `Esc` restaura player;
- non-claims registram `time_changed=false`, `timezone_changed=false`,
  `ntp_changed=false`, `rtc_written=false`.

## Protocolo Minimo Por Rodada

Metodo central atualizado:
`docs/product/194_C20_WIZARD_E2E_RC_METHOD.md`.

Decisao de 2026-07-08: C20.x sao incrementos validados para acumulo. O marco de
produto e o **C20 Wizard E2E RC**, que prova a jornada completa do wizard em
`totem-core` sem promover stable/producao por inferencia.

1. Definir objetivo, escopo e non-claims.
2. Iterar localmente com preview/galeria quando possivel.
3. Rodar self-tests do script tocado.
4. Abrir wizard pelo fluxo real da placa quando a rodada for candidata.
5. Navegar roteiro curto e deterministico.
6. Capturar tela real e salvar imagem visivel.
7. Validar retorno ao player.
8. Marcar como `validada para acumulo` somente com evidencia completa.
9. Ao final de um conjunto, gerar pacote/update consolidado e validar
   apply/rollback antes da nova imagem de referencia.

Nota: rodadas que validam somente preview auto-exit devem registrar esse limite
explicitamente. Fluxos de navegacao por teclado precisam de captura interativa
se o claim depender de entrada real do usuario.

## Galeria Completa De Inspecao

Em 2026-07-08 foi criada uma galeria completa para evitar revisao visual
baseada em poucas capturas.

Evidencia:
`docs/evidence/c20-visual-qa/20260708T002900Z-c20-full-gallery-inspection/`.

Uso esperado:

- abrir `index.html` ou `contact-sheet-*.jpg` para revisao rapida;
- abrir `visible/*.jpg` para inspecao tela a tela;
- usar a galeria como base de decisao visual, mas nao como prova de interacao
  real na placa;
- quando uma rodada depender de comportamento real, complementar com captura
  framebuffer/HDMI da placa.

## OTA Local Para Inspecao Na Placa

Em 2026-07-08 foi gerado e aplicado localmente um pacote `totem-core` C20 para
inspecao visual real na placa.

Pacote:
`c20.visual-settings-20260708T003000Z-4e3a13d`.

Evidencias:

- `releases/core-updates/c20.visual-settings-20260708T003000Z-4e3a13d/`;
- `docs/evidence/c20-totem-core-ota/20260708T004241Z-visible-apply/`.

Claim permitido:

- a placa recebeu C20 via apply local governado de `totem-core` e abriu o wizard
  atualizado para inspeção humana.

Pendencia macro:

- decidir apos a inspeção se C20 fica aplicado ou se a placa volta para C18;
- gerar pacote/update consolidado;
- incluir o conjunto C20 na proxima imagem de referencia.

Non-claims:

- C20 nao foi publicado como GitHub Release;
- C20 nao foi promovido para `stable`;
- C20 ainda nao entrou em nova imagem de referencia.

## Auditorias

Rodadas C20 devem usar auditorias paralelas quando agregarem valor:

- UX/produto: clareza, hierarquia, densidade e polimento;
- QA visual: evidencia decisiva, reproducibilidade e falso-verde;
- escopo/risco: garantir que `totem-core` nao invada outras frentes;
- auditor externo opcional: leitura criativa e critica, sem escrita no repo nem
  acesso SSH a placa.

O decisor central consolida os retornos, descarta sugestoes fora de escopo e
atualiza este plano quando houver aprendizado real.

## Sintese Da Auditoria De Metodo C20 E2E

Em 2026-07-08, auditores independentes revisaram a metodologia C20. A conclusao
incorporada foi:

- o plano e robusto para verticais isoladas, mas precisava de um RC E2E unico;
- screenshots e SVGs ajudam, mas nao substituem fluxo real na placa quando o
  claim depende de comportamento humano/hardware;
- o pacote acumulado deve provar player ativo, settings limpo, rollback e
  fronteira `totem-core`;
- auditoria paralela deve ser usada em mudanca de navegacao, risco operacional
  ou fechamento RC, nao em todo microcopy;
- nao bloquear por polimento quando o usuario entende e a operacao esta segura.

O metodo final esta registrado em:
`docs/product/194_C20_WIZARD_E2E_RC_METHOD.md`.

## Pacote Acumulado Atual

Estado: C20.1-C20.9 aplicados e validados incrementalmente na placa por
`totem-core`.

Current observado apos C20.9:
`releases/c20.9-wifi-step-copy-20260708T060338Z-34a9537`.

Rollback imediato:
`releases/c20.8-clock-all-steps-20260708T045317Z-661c582`.

Ultimo pacote/evidencia:
`docs/evidence/c20-totem-core-ota/20260708T061500Z-c20-9-wifi-step-copy-board-apply/`.

Intencao macro: continuar acumulando apenas melhorias fechadas e reversiveis do
wizard/status/splash em `totem-core`, depois gravar o conjunto na proxima imagem
de referencia. Mudancas de player-runtime, MPV/kernel/display baixo nivel,
midia/config/cache e politica de OTA continuam fora deste pacote UX.

## Primeiras Rodadas Recomendadas

1. V0: corrigir a sobreposicao painel/preview na orientacao.
2. V1: revisar hierarquia/densidade das telas principais do wizard.
3. V2: reforcar hierarquia de acao e produto visual.
4. V3: revisar navegacao e cancelamento previsiveis.
5. V8: criar manifesto minimo de QA visual por rodada.

Regras para todas:

- manter a correcao C19 da lista Wi-Fi;
- nao mexer em Wi-Fi real;
- nao mexer em display/EDID;
- nao mexer em player;
- validar em 1024x768 com capturas reais.
