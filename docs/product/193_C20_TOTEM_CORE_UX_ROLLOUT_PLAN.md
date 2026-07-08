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

## Proximo Marco

Aplicar C20.1 por `totem-core` OTA na placa, abrir o wizard e capturar framebuffer
real da tela Ambiente. Se aprovado, manter como pacote acumulado para a imagem de
referencia seguinte.
