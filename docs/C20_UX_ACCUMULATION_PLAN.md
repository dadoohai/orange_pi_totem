# C20 UX Accumulation Plan

Estado: 2026-07-16.

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
- adapter Wi-Fi transacional e perfis protegidos/abertos;
- deteccao e orquestracao visual de portal cativo;
- evidencia, docs e checks de QA visual.

Fora deste pacote:

- `player-runtime`, MPV, playlist, timing ou comportamento de playback;
- display/EDID/resolucao/kernel/ffmpeg/hwdecode/imagem;
- manipulacao manual de NetworkManager fora do adapter governado;
- instalacao silenciosa de navegador, desktop ou dependencia nova de sistema;
- midia, playlist, cache, dados de campo;
- updater, timer, policy, publish/stable, salvo empacotamento final governado.

Nota de evolucao: as verticais historicas abaixo preservam seus non-claims da
epoca. Desde C21.19, Wi-Fi real transacional pertence ao escopo atual de M9,
sem apagar o limite original das rodadas anteriores.

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

Estado em 2026-07-15: a frente seguinte fechou Wi-Fi persistente transacional
na candidata C21.19, acumulada sobre C21.18.

Candidata acumulada atual:
`releases/core-updates/c21.19-wifi-transactional-20260715T145334Z-a214648`.

Referencia stable de distribuicao e retorno:
`releases/core-updates/c21.12-prod14-stable-alignment-20260714T204248Z-766b1ea`.

Ultimo pacote/evidencia:
`docs/evidence/c20-totem-core-ota/20260715T161137Z-c21-19-wifi-transactional-board-e2e/`.

O C21.19 passou os gates `84/84`, bloqueio de prerelease pela policy stable,
apply, rollback para C21.18, reaplicacao, Wi-Fi positivo e negativo real,
cancelamento visual sem escrita e reboot com playback preservado. Ele e a
candidata acumulada de `totem-core` em homologacao; nao substitui C21.12 como
stable nem muda a imagem oficial por inferencia.

Intencao macro: continuar acumulando apenas melhorias fechadas e reversiveis do
wizard/status/splash em `totem-core`, depois gravar o conjunto na proxima imagem
de referencia. Mudancas de player-runtime, MPV/kernel/display baixo nivel,
midia/config/cache e politica de OTA continuam fora deste pacote UX.

## Rodada C20.15 - Reentrada e leitura operacional

Objetivo: corrigir tres atritos visiveis sem ampliar o escopo do wizard:

- mostrar data/hora de Sao Paulo, mantendo sistema e logs da placa em UTC;
- distinguir no resumo o que esta confirmado, pendente ou bloqueado;
- ao reabrir configuracoes, manter ambiente e Wi-Fi somente quando o estado
  ativo da sessao e o perfil dedicado existente e ativo comprovarem isso.

Regras de seguranca:

- contexto persistente antigo pode preencher campos, mas nao provar estado
  ativo nem dispensar validacao;
- mudanca de ambiente continua exigindo o preflight normal;
- ausencia ou incerteza sobre o perfil Wi-Fi falha fechada e volta ao fluxo de
  configuracao;
- a leitura do perfil e read-only; a rodada nao altera rede, API, player,
  updater, kernel ou imagem.

Estado em 2026-07-14: rodada fechada como a candidata homologation
`c21.13-wizard-retained-status-20260714T231059Z-81d64ee`. O replay passou 9
cenarios e 24 assercoes; release gate `84/84`, sandbox, duas auditorias
independentes, apply, rollback, reaplicacao e E2E visual real passaram. O
player voltou saudavel, sem restart. A placa da rodada nao possuia perfil Wi-Fi
dedicado ativo: por isso, o hardware comprovou o caminho fail-closed e o caminho
positivo de retencao ficou comprovado por self-test/replay. O ambiente atual foi
mantido no fluxo real. Evidencia:
`docs/evidence/c20-totem-core-ota/20260714T233330Z-c21-13-wizard-retained-status-board-e2e/`.

Conclusao funcional: os tres itens estao fechados. C21.13 permanece candidata
acumulada de homologacao; `prod14` + C25B + C21.12 permanece a referencia de
distribuicao e rollback ate promocao explicita.

## Rodada C20.16 - Estado discreto de conectividade

Objetivo: mostrar no cabecalho do wizard, ao lado da hora, o transporte atual e
o estado de internet sem transformar a tela em painel tecnico.

Contrato funcional:

- Ethernet ou Wi-Fi sao mostrados por simbolo; Wi-Fi usa sinal fraco, medio ou
  forte;
- internet usa `OK`, `!`, `X` ou `?`, com cor e simbolo para nao depender so de
  cor;
- Ethernet ou Wi-Fi local pode ser mostrado quando a interface esta conectada
  e ativa, mesmo sem rota; nesse caso a reachability continua `?`;
- `OK` ou `!` exige uma unica rota IPv4 default preferida cuja interface
  tambem esteja conectada e ativa no NetworkManager;
- `OK` exige `HEAD` 200 na URL fixa de health do servico Dadooh, sem proxy,
  redirect, autenticacao, cookie, query ou identificador da placa;
- `!` significa rota verificada mas servico Dadooh inacessivel; `X` significa
  nenhum transporte ativo comprovado; `?` significa leitura inconclusiva;
- leitura ausente, inconsistente, expirada ou ambigua falha fechada para `?`;
- nao ha speedtest, rescan, SSID, credencial ou mudanca de rede;
- o indicador nao afirma velocidade, saude de CDN/midia, Internet inteira nem
  que o probe ficou preso fisicamente a uma interface durante toda a chamada.

Contrato 24/7:

- existe somente um snapshot em memoria, substituido a cada leitura;
- o snapshot vale por 15 segundos e a coleta tem orcamento total de dois
  segundos;
- existe no maximo um worker, um resultado pendente e uma thread de coleta;
  nao existe fila, historico nem persistencia;
- o loop consulta o worker a cada 100 ms sem bloquear entrada; tecla pronta tem
  prioridade sobre repaint do indicador;
- o framebuffer nao gera arquivo por refresh; o fallback MPV reutiliza dois
  arquivos temporarios;
- os SVGs temporarios da sessao usam anel fixo de 64 arquivos.

Estado em 2026-07-15: a primeira candidata homologation
`c21.14-wizard-connectivity-20260715T003032Z-4835ca8` passou a validacao inicial,
mas a auditoria final encontrou dois blockers: falso `online` sem rota default
e contador IPC sem teto. C21.14 foi supersedida sem promocao. Evidencia
historica:
`docs/evidence/c20-totem-core-ota/20260715T005134Z-c21-14-wizard-connectivity-board-e2e/`.

A primeira correcao foi empacotada na candidata
`c21.15-wizard-connectivity-bounded-20260715T011533Z-0c08a26`: ela pretendia
exigir rota verificada para qualquer estado positivo, adicionou contador
circular e um unico orcamento de tempo para toda a coleta. A reauditoria do
codigo teve zero blockers. O pacote passou `84/84`, sandbox, bloqueio stable,
apply, rollback,
reaplicacao, E2E visual e health final na placa. A implementacao permanece
limitada para uso 24/7: um snapshot substituivel, sem fila/historico/thread,
arquivos temporarios fixos ou em anel e coleta read-only com prazo total.

Um evento Panfrost observado perto da primeira sessao visual foi preservado e
nao recebeu RCA por inferencia. Tres novos ciclos do wizard e tres probes
oficiais de parada nao reproduziram o evento; o health delta final passou. O
registro completo esta em:
`docs/evidence/c20-totem-core-ota/20260715T014809Z-c21-15-wizard-connectivity-bounded-board-e2e/`.

A auditoria final encontrou um blocker adicional e o decisor central o
reproduziu: linhas de rota sem `RTF_UP` ou com mascara nao-default ainda podiam
produzir falso `online`. C21.15 foi bloqueada e supersedida sem promocao. A
sucessora passou a usar a saida JSON tipada de `ip route`, validar a rota
completa, conferir o device ativo e testar o servico Dadooh de forma limitada.

C21.16 e C21.17 foram empacotadas, mas supersedidas antes de qualquer apply na
placa para fechar, respectivamente, prioridade de entrada e apresentacao
imediata do estado. Nenhuma foi promovida.

A candidata final
`c21.18-wizard-connectivity-verified-20260715T045523Z-3bdbd18` passou os gates
`84/84` e o roundtrip real na placa. A tela mostrou Ethernet + `OK` por pixels
reais e pela captura visual; navegacao e cancelamento preservaram configuracao,
contexto e estado de rede. Um teste de 600 segundos manteve RSS, FDs, threads e
arquivos limitados; outro teste instrumentado observou tres probes exatos em 60
segundos e terminou com o player ativo, tocando e sem restart.

Uma coleta de playback encontrou tres amostras classificadas como desconhecidas
durante uma troca curta, embora frames, HW decode e alinhamento final estivessem
verdes. O RCA mostrou conflito entre dois checks do summary. O gate passou a
aceitar somente a transicao forward delimitada, progressiva e recuperada, com
sequencia e tempo continuos inclusive nas duas amostras alinhadas que delimitam
a troca. Continua negando transicao terminal, destacada ou sem progresso. Os
mesmos dados brutos foram reavaliados com resultado verde; a evidencia negativa
original foi preservada.

O summary e uma ferramenta fixa da imagem, deliberadamente excluida do pacote
`totem-core`. A correcao fica registrada como entrada obrigatoria da proxima
imagem de referencia; C21.18 nao altera esse binario na placa por inferencia.

Estado final da bancada: current C21.18, previous C21.13, policy/timer stable
restaurados e player ativo. C21.12 continua stable de retorno e `prod14`
continua imagem de referencia ate decisao explicita de promocao ou nova imagem.

## Rodada C20.17 - Wi-Fi persistente transacional

Objetivo: tornar a configuracao Wi-Fi real segura para reentrada e falhas de
campo sem perder a conectividade anterior.

Contrato fechado:

- SSID e senha preservam exatamente os bytes informados, inclusive espacos nas
  bordas;
- o perfil antigo permanece disponivel durante a tentativa;
- somente ativacao com IPv4 confirma sucesso e retencao do novo perfil;
- falha de ativacao ou IP restaura o perfil anterior exato;
- primeira configuracao falha nao deixa perfil parcial;
- se a fonte anterior nao puder ser preservada, a operacao falha fechada;
- status e UI distinguem tentativa, sucesso e restauracao sem expor segredo;
- Ethernet de recuperacao, player, config real e servicos fora da rede nao sao
  modificados pelo adaptador.

Estado: fechado na candidata homologation
`c21.19-wifi-transactional-20260715T145334Z-a214648`. O roundtrip OTA real,
rede positiva com SSID de espacos finais, falha sintetica com restauracao,
fluxo visual sem salvar e reboot final passaram. A placa terminou com C21.19
current, C21.18 previous, policy/timer stable restaurados, dois links ativos e
player sem restart. Evidencia:
`docs/evidence/c20-totem-core-ota/20260715T161137Z-c21-19-wifi-transactional-board-e2e/`.

O RCA gerou tambem o commit image-fixed `c075a55`, que reconhece somente uma
ponte final desconhecida em transicao encadeada de playback quando ha prova
completa de limites, decode, sequencia, tempo e progresso. Ele nao pertence ao
payload `totem-core` e deve entrar na proxima imagem de referencia.

## Rodada C25 - Estados Visiveis

C25 continua o acumulo por `totem-core` com um contrato visual verdadeiro para
config pendente, inicio, carregamento, ausencia de conteudo e recuperacao. A
rodada tambem corrige a ordem perceptiva do writer: `Pronto para salvar` antes
da gravacao e `Configuracao salva` somente depois do sucesso.

Fonte da rodada: `docs/product/199_C25_VISIBLE_PRODUCT_STATES.md`.

Estado: C25A (`totem-core`) e C25B (`player-runtime`) foram validados na placa
com rollback e incorporados na prod12. Os hardenings de settings posteriores
foram acumulados no C20.14. Esse core foi embutido na prod13, que passou a
auditoria pre-flash sem delta inesperado. A pendencia e repetir o E2E na imagem
gravada; C25B nao foi promovida para `stable` nem liberada como novo alvo de
auto-pull publico.

## Fila Priorizada Atual - Wi-Fi De Produto

Estado: itens 1 e 2 fechados na placa pela C21.20. O item 3 foi implementado,
empacotado e exercitado por OTA na C21.21; falta somente a prova de associacao
em um AP aberto real.

Objetivo: transformar a base transacional ja comprovada em uma jornada curta,
verdadeira e utilizavel por cliente. A ordem abaixo prioriza maior valor com
menor esforco e deve ser seguida sem transformar portal cativo em bloqueio para
as entregas anteriores.

1. **Corrigir opcoes e mensagens enganosas.**
   Mostrar `Usar Wi-Fi ja configurado` somente quando o perfil estiver valido,
   ocultar `modo de bancada` da superficie de producao e informar corretamente
   o que ja foi aplicado quando o usuario volta ou cancela.
2. **Simplificar o fluxo de conexao.**
   Remover confirmacoes repetidas, unir senha e acao `Conectar`, avancar apos
   sucesso e preservar rede/senha/contexto quando a tentativa falhar.
3. **Suportar redes abertas comuns.**
   Criar perfil sem WPA/PSK, conectar sem pedir senha, exigir endereco de rede e
   manter o mesmo rollback transacional da rede protegida.
4. **Corrigir estados visuais.**
   Resolver item oculto no modo retrato, lista vazia, lista anterior/cache,
   rodapes que prometem outra acao e capturas ausentes de conectando, sucesso,
   falha e restauracao.
5. **Explicar o estado real da conexao.**
   Distinguir visualmente Ethernet, Wi-Fi associado, internet disponivel,
   internet limitada, sem internet e estado inconclusivo.
6. **Melhorar diagnostico e recuperacao.**
   Mapear categorias seguras para senha/autenticacao, timeout, sinal/rede
   indisponivel e ausencia de IPv4; cada falha deve oferecer retry direto sem
   apagar contexto nem expor log bruto.
7. **Detectar portal cativo.**
   Depois da associacao local, identificar quando o acesso exige pagina de
   autenticacao e separar esse estado de `sem internet`.
8. **Adicionar navegador temporario para portal.**
   Abrir uma sessao local restrita, sem downloads, historico ou senha salva;
   monitorar a conectividade, fechar ao liberar internet e remover os dados
   temporarios. Timeout ou cancelamento restaura a rede anterior. Antes de
   implementar, auditar a imagem: se faltar runtime adequado, adiciona-lo pela
   proxima imagem, nunca como dependencia de sistema escondida no `totem-core`.
9. **Fechar na placa e por OTA.**
   Validar rede atual, protegida, aberta, lista vazia/cache, falhas, portal,
   paisagem/retrato, privacidade, retorno ao player, apply e rollback. Cada
   recorte aprovado entra no pacote acumulado `totem-core` e na proxima imagem
   de referencia.

### Rodada M9.1-2 - Verdade E Fluxo Curto

Implementado:

- conexao atual so aparece quando Ethernet ou o perfil Wi-Fi dedicado estao
  comprovadamente ativos;
- modo de bancada fica oculto em producao;
- lista vazia, rede aberta ainda nao suportada, cancelamento, rollback e Wi-Fi
  aplicado usam mensagens distintas e verdadeiras;
- rede protegida segue direto de lista para senha/conexao, avanca apos sucesso
  e preserva lista, rede e senha mascarada para retry;
- status de uma execucao antiga nao pode contaminar o cancelamento atual;
- quatro redes ficam integralmente visiveis por pagina em retrato.

Fechamento: self-tests, replay completo, galeria visual e verificacao de
segredo passaram. O pacote homologation C21.20 passou os gates `84/84`; a
policy stable o bloqueou; apply, rollback para C21.19 e reaplicacao passaram.
A captura real mostrou as tres opcoes validas, sem modo de bancada, e a sessao
visual encerrou sem escrita persistente. Player, timer e policy terminaram
saudaveis. Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T160720Z-c21-20-wifi-product-flow-board-e2e/`.

Hardening nao bloqueante registrado: o caminho de produto ja serializa a
sessao antes de abrir o wizard, mas o scratch legado de segredo Wi-Fi ainda
pode ser tornado especifico por sessao contra invocacao privilegiada direta.
Isso nao reabre C21.20 nem precede o item 3.

### Rodada M9.3 - Rede Aberta Comum

Implementado:

- rede aberta aparece como `Aberta | Sem senha` e segue direto para conexao;
- o perfil NetworkManager aberto omite WPA, PSK e qualquer credencial;
- sucesso continua exigindo ativacao e endereco IPv4;
- falha restaura exatamente o perfil anterior e permite retry direto;
- redes abertas e protegidas com o mesmo SSID permanecem escolhas distintas;
- o status final registra ausencia de credencial sem publicar SSID;
- o fluxo protegido anterior e seus retries permanecem cobertos.

Fechamento tecnico: os gates de fonte e pacote passaram `84/84`. A policy
stable bloqueou a candidata homologation com rc `41`; apply, rollback para
C21.20 e reaplicacao da C21.21 passaram com rc `0`. Player, Ethernet, Wi-Fi,
timer e policy terminaram saudaveis, sem restart do player. Evidencia:
`docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/`.

Limite honesto: a placa nao trocou sua rede atual porque nao havia AP aberto
disponivel. Assim, M9.3 esta pronta como candidata e validada no OTA, mas o
aceite fisico final de associacao aberta permanece pendente. Isso nao bloqueia
o inicio dos itens 4 e 5.

## Criterio De Fechamento Da Frente

- nenhuma opcao selecionavel leva a caminho impossivel;
- nenhuma mensagem contradiz o estado persistido;
- retry nao obriga repetir toda a jornada;
- redes protegidas e abertas preservam rollback;
- portal e distinguido de falha comum de internet;
- nenhum elemento fica oculto, sobreposto ou inacessivel;
- senha, SSID e dados de portal nao aparecem em evidencia publica;
- player volta saudavel, settings encerra limpo e testes existentes nao
  regridem;
- galeria visual auxilia, mas o aceite final depende de fluxo real na placa.

Regras de escopo:

- manter em `totem-core` a UI, o adapter e a orquestracao;
- introduzir runtime novo de navegador somente pela imagem;
- nao alterar `player-runtime`, MPV, kernel, display/EDID ou politica OTA;
- nao reabrir C21.19 salvo regressao comprovada;
- navegador para portal e vertical posterior e nao bloqueia o suporte a rede
  aberta comum.
