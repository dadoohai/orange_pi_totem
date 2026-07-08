# 193 - C20 Totem-Core UX Rollout Plan

## Objetivo

Fechar melhorias de configuracao local por `totem-core` OTA com foco em uso real:
wizard mais claro, tela legivel, retorno seguro ao player e pacote acumulado para
a proxima imagem de referencia.

## Direcao Macro

- Wizard, splash, status e ajustes de configuracao seguem em `totem-core`.
- Player/runtime segue fora desta rodada.
- MPV, kernel, decode e imagem base seguem fora de OTA comum.
- Cada melhoria concluida deve entrar em pacote de atualizacao e tambem ficar
  marcada para a proxima imagem gravavel.
- Nao aceitar regressao: player volta, timer/politica continuam controlados e
  rollback permanece possivel.

## Rodada Atual

Fechar C20.1 como ajuste pequeno e seguro:

- corrigir overflow/copy da tela Ambiente;
- remover instrucao visivel confusa sobre `Ctrl+U`/setas;
- manter atalhos existentes funcionando;
- alinhar galeria QA com o wizard real;
- validar por self-test, galeria e captura da placa antes de considerar pronto.

## Navegacao Por Etapas

Boa direcao, mas nao deve entrar como atalho improvisado. Para permitir pular
entre Tela, Conexao, Ambiente e Revisao, antes precisamos de estado explicito:

- `confirmado`;
- `default`;
- `pendente`;
- `nao_validado`;
- `aviso`.

A Revisao pode mostrar pendencias/defaults, mas salvar/concluir so deve liberar
quando os obrigatorios estiverem validos. Essa vertical fica planejada para
rodada posterior, sem bloquear o pacote C20.1.

## C20.1 Fechado

- Pacote `totem-core` criado:
  `c20.1.environment-copy-20260708T011500Z-7a29d1a`.
- Gate de release verde e commitado junto do pacote.
- Aplicado na placa por `totem-updatectl apply-local`.
- Captura real do framebuffer da tela Ambiente registrada em:
  `docs/evidence/c20-totem-core-ota/20260708T012412Z-c20-1-environment-copy-board-apply/`.
- Deve entrar no pacote acumulado da proxima imagem de referencia.

## C20.2 Fechado

- `Tab` abre o menu de etapas do wizard.
- O operador pode ir para Tela, Conexao, Ambiente ou Revisao sem completar a
  etapa anterior.
- A Revisao mostra `Default`, `Pendente`, `Precisa validar`, `Validado` ou
  `Bloqueado`.
- Nenhuma candidata e gerada quando falta rede ou ambiente validado.
- Testes offline cobrem self-test, galeria visual e replay de entrada
  `step_menu_pending_review`.
- Pacote `totem-core` criado:
  `c20.2.step-navigation-20260708T022700Z-1fa33d2`.
- Gate de release verde e commitado junto do pacote.
- Aplicado na placa por `totem-updatectl apply-local`.
- Capturas reais do framebuffer do menu de etapas e da revisao bloqueada
  registradas em:
  `docs/evidence/c20-totem-core-ota/20260708T030000Z-c20-2-step-navigation-board-apply/`.
- Deve entrar no pacote acumulado da proxima imagem de referencia.
- Observacao: C20.2 ficou funcional, mas a UX por `Tab` foi rejeitada em teste
  real porque nao deixava claro onde estava o foco. C20.3 substitui essa
  navegacao por foco unico com setas.

## C20.3 Fechado

- Remover a navegacao por `Tab`/menu modal.
- Usar foco unico, no padrao controle remoto/TV:
  - foco no conteudo: `cima` no primeiro item sobe para o menu superior;
  - foco no menu superior: `esquerda/direita` escolhem etapa;
  - `baixo` volta para os itens da etapa atual;
  - `Enter` abre a etapa focada ou confirma o item focado.
- Diferenciar visualmente etapa ativa e foco real:
  - etapa ativa permanece marcada;
  - foco real recebe destaque forte;
  - item interno fica atenuado quando o foco esta no menu superior.
- Manter a regra de seguranca: revisar estado parcial e bloquear salvamento
  incompleto.
- Testes offline cobrem self-test, galeria visual e replay de foco
  `step_focus_pending_review`.
- Pacote `totem-core` criado:
  `c20.3.focus-navigation-20260708T033000Z-f343c99`.
- Gate de release verde e commitado junto do pacote.
- Aplicado na placa por `totem-updatectl apply-local`.
- Capturas reais do framebuffer do foco no conteudo e foco no topo registradas
  em:
  `docs/evidence/c20-totem-core-ota/20260708T034000Z-c20-3-focus-navigation-board-apply/`.
- Deve entrar no pacote acumulado da proxima imagem de referencia.

## C20.4 Fechado

- Corrigir regressao operacional do F10 apos C20.3.
- Sintoma real: F10 era detectado, mas `totem-open-settings.service` ficava
  preso no `ExecStartPre` do `totem_visual_tty_guard.sh`.
- Causa: operacoes de escrita/limpeza em `/dev/tty2` podiam bloquear sem timeout.
- Correcao: cada operacao sensivel do guard passa a rodar com timeout curto,
  sem impedir que o wizard abra.
- Validado: `bash -n`, teste do guard em `/tmp` na placa, pacote `totem-core`,
  gate verde e apply por `totem-updatectl`.
- Limite honesto: C20.4 removeu o bloqueio do `ExecStartPre`, mas revelou um
  segundo bloqueio no `show_transition`. C20.5 fecha esse segundo ponto.

## C20.5 Fechado

- Completar a correcao do F10 no script de sessao.
- Sintoma apos C20.4: `ExecStartPre` passou, mas `show_transition` ainda podia
  bloquear ao escrever splash diretamente em `/dev/tty2`.
- Correcao: `chvt`, limpeza do TTY, `printf` e splash passam por helpers com
  timeout curto.
- Validado: `bash -n`, self-test do wizard, pacote `totem-core`, gate verde,
  apply por `totem-updatectl`, abertura real do service ate o processo do wizard
  e captura real do framebuffer.
- Pacote `totem-core` criado:
  `c20.5-f10-transition-timeout-20260708T040500Z-6ef0b0b`.
- Evidencia:
  `docs/evidence/c20-totem-core-ota/20260708T041000Z-c20-5-f10-transition-board-apply/`.
- Deve entrar no pacote acumulado da proxima imagem de referencia.

## C20.6 Fechado

- Refinar a navegacao superior para se comportar como menu de BIOS/TV.
- Quando o foco esta no menu superior, `esquerda/direita` mudam a etapa ativa
  imediatamente e o conteudo abaixo ja acompanha a etapa destacada.
- `baixo` deixa de ser necessario para renderizar a etapa; ele apenas entra no
  primeiro controle do conteudo ja exibido.
- A regra vale para Tela, Conexao, Ambiente e Revisao.
- Validado: self-test cobrindo salto imediato, release gate 66/66, apply por
  `totem-updatectl`, abertura real do wizard e injecao de teclado via
  `/dev/uinput` com capturas reais.
- Pacote `totem-core` criado:
  `c20.6-top-step-preview-20260708T031956Z-5686f83`.
- Evidencia:
  `docs/evidence/c20-totem-core-ota/20260708T032600Z-c20-6-top-step-preview-board-apply/`.
- Deve entrar no pacote acumulado da proxima imagem de referencia.

## C20.7 Design Aprovado - Data/Hora No Wizard

- Objetivo: exibir data/hora de forma discreta para operador/suporte, sem
  transformar o wizard em painel tecnico.
- Decisao de design aprovada: metadado passivo no cabecalho, sem foco, sem
  botao novo, sem rodape e sem item no painel lateral.
- Regra visual aprovada:
  - em paisagem, reutilizar o slot de nota do cabecalho;
  - em retrato, prender a data/hora na linha superior do cabecalho, a direita
    de `Configuracao do Totem`;
  - na etapa 0, preservar `Layout paisagem/retrato` no lugar da data/hora;
  - nas etapas 1-4, exibir `DD/MM/YYYY HH:MM`;
  - se o relogio for implausivel, exibir `Hora nao ajustada`.
- Sem segundos e sem relogio vivo. O valor atualiza quando a tela e
  renderizada, nao a cada segundo.
- Escopo permitido nesta primeira rodada:
  - renderizar data/hora local como metadado visual;
  - manter tudo dentro de `totem_setup_visual_wizard.py`;
  - validar em preview, self-test, OTA `totem-core` e captura real da placa.
- Fora desta primeira rodada:
  - configurar hora manualmente;
  - alterar timezone;
  - mexer em NTP/chrony/timesyncd;
  - escrever `/etc/localtime`, `hwclock`, systemd ou qualquer politica de base.
- Risco central: hora errada em placa sem NTP/RTC pode confundir. Se isso for
  relevante no teste visual, a primeira implementacao deve mostrar `Hora nao
  ajustada` quando a data for implausivel, sem permitir ajuste manual.
- Auditorias desta abertura: Sonnet apontou colisao com `Layout paisagem` no
  mockup inicial; a regra final incorporou isso. Tres auditores xhigh aprovaram
  a R3 sem blockers.
- Evidencia visual aprovada:
  `docs/evidence/c20-visual-qa/20260708T-c20-7-clock-pdca-design/round3/`.
- Non-claims: nao declara horario correto, sincronizado, NTP ativo, RTC
  ajustado ou timezone configurado; o horario nao e criterio de sucesso do
  wizard.

## Proximo Marco

Continuar as melhorias de UX do wizard por verticais pequenas, sempre com:
self-test, galeria visual, replay quando houver fluxo de teclado, pacote
`totem-core`, aplicacao na placa e captura real antes de marcar como fechado.
