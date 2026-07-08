# C20.6 Totem-Core Board Apply

## Resultado

C20.6 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.6-top-step-preview-20260708T031956Z-5686f83`
- Payload SHA256: `5746b7b4dc969d8f04c0ef4c09778c82fb651431f2ef1f2a2a82ac7ed1856d54`
- Antes: `releases/c20.5-f10-transition-timeout-20260708T040500Z-6ef0b0b`
- Depois: `releases/c20.6-top-step-preview-20260708T031956Z-5686f83`
- Rollback: `releases/c20.5-f10-transition-timeout-20260708T040500Z-6ef0b0b`

## Mudanca Validada

O menu superior agora troca a etapa ativa imediatamente. Em foco no topo:

- `esquerda/direita` mudam a etapa destacada e renderizam o conteudo abaixo;
- `baixo` entra no primeiro controle da etapa ja exibida;
- `Enter` no conteudo confirma o item selecionado.

## Evidencia

- `board/apply-local.txt`: apply governado com `apply_success`.
- `board/uinput-navigation-test.txt`: injecao real `cima` + `direita` via
  `/dev/uinput`, gerando `0003-02-connection.svg`.
- `board/uinput-down-test.txt`: `baixo` entra no conteudo da etapa Conexao.
- `captures/03-after-uinput-up-right.jpg`: Conexao aparece sem pressionar
  `baixo`.
- `captures/04-after-down-enters-content.jpg`: foco entra na lista de Conexao.

## Estado Operacional

O teste deixou o wizard aberto na tela Conexao para confirmacao do operador.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull ou stable.
