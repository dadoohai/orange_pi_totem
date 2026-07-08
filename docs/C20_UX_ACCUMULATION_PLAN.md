# C20 UX Accumulation Plan

Estado: 2026-07-07.

Objetivo: evoluir a experiencia visual e operacional do produto em rodadas
pequenas de `totem-core`, validando cada uma na placa e acumulando o conjunto
para um pacote/update consolidado e para a proxima imagem de referencia.

## Direcao

- UX de produto, nao dashboard tecnico.
- Uma tarefa principal por tela.
- Texto curto, legivel e util em 1024x768.
- Sem excesso de atalhos, bullets ou diagnostico bruto.
- Cada rodada deve poder ser validada visualmente e revertida.
- C20 acumula melhorias; nao publica/promove cada uma isoladamente por padrao.

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

## Protocolo Minimo Por Rodada

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

## Auditorias

Rodadas C20 devem usar auditorias paralelas quando agregarem valor:

- UX/produto: clareza, hierarquia, densidade e polimento;
- QA visual: evidencia decisiva, reproducibilidade e falso-verde;
- escopo/risco: garantir que `totem-core` nao invada outras frentes;
- auditor externo opcional: leitura criativa e critica, sem escrita no repo nem
  acesso SSH a placa.

O decisor central consolida os retornos, descarta sugestoes fora de escopo e
atualiza este plano quando houver aprendizado real.

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
