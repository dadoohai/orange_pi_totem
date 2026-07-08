# C20.7 Clock Design PDCA - Round 3

Status: design aprovado, sem implementacao ainda.

Objetivo: convergir a exibicao de data/hora no wizard sem criar uma nova
decisao local para o operador e sem alterar relogio, timezone, NTP, RTC ou
servicos do sistema.

Regra visual aprovada:

- paisagem: reutilizar o slot de nota do cabecalho;
- retrato: exibir na linha superior do cabecalho, a direita do titulo;
- etapa 0: preservar `Layout paisagem/retrato`;
- etapas 1-4: exibir `DD/MM/YYYY HH:MM`;
- hora implausivel: exibir `Hora nao ajustada`;
- sem segundos, sem relogio vivo, sem foco, sem botao, sem rodape.

Convergencia:

- Round 1: mockup inicial e variacoes; descartado como especificacao final
  porque nao tratava a colisao com a nota de layout.
- Round 2: regra por slot aprovada parcialmente; retrato ficou visualmente
  solto entre passos e titulo.
- Round 3: retrato movido para a linha superior do cabecalho; tres auditores
  xhigh aprovaram sem blockers.

Non-claims:

- nao declara horario correto;
- nao declara horario sincronizado;
- nao declara NTP ativo;
- nao declara RTC ajustado;
- nao declara timezone configurado;
- nao permite configurar hora pela UI;
- nao usa o relogio como criterio de sucesso do wizard.

Arquivos principais:

- `contact-sheet-clean.png`
- `png-clean/r3-header-datetime/connection-landscape.png`
- `png-clean/r3-header-datetime/connection-portrait.png`
- `png-clean/r3-header-datetime/environment-portrait.png`
- `png-clean/r3-header-datetime/orientation-landscape.png`
- `png-clean/r3-invalid-time/connection-landscape.png`
