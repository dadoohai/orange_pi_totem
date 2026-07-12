# 198 - C24 fonte do player e atualizacao em escala

Estado em 2026-07-12: decisao arquitetural consolidada e preservada como
roadmap; implementacao adiada para priorizar melhorias de impacto direto ao
usuario.

## Decisao De Prioridade

Esta frente nao e o proximo trabalho. C23 continua como baseline funcional e a
estrutura atual nao sera reaberta enquanto as rodadas de produto puderem
avancar por `totem-core` sem tocar o player.

Retomar esta decisao quando ocorrer pelo menos um destes gatilhos:

- existir uma mudanca de player que precise chegar a placas em campo sem
  regravacao;
- a divergencia entre os dois repositorios impedir ou atrasar uma correcao
  real;
- formos fechar a nova imagem de referencia que deve carregar o controle
  assinado;
- a operacao de lote exigir pause/rollback remoto de player em escala.

Ate la, uma correcao urgente de player continua usando o snapshot governado e
o caminho exact-target ja existente. Isso e uma ponte operacional, nao a
arquitetura final descrita abaixo.

## Objetivo

Permitir que a equipe altere o player em um repositorio claro e que placas em
producao recebam C24, C25 e seguintes automaticamente, sem regravar a imagem a
cada versao e sem abrir `latest` amplo para `player-runtime`.

## Decisao

1. O C23 atual permanece como baseline funcional e nao sera reescrito.
2. Depois da convergencia, `dadoohai/kiosky-player`, branch
   `appliance-v0.1`, sera a fonte editavel do comportamento do player.
3. `dadoohai/orange_pi_totem` continua sendo a unica fonte de entrega para as
   placas C18: importa um commit exato do player, testa, empacota, publica e
   governa o `player-runtime`.
4. O snapshot importado em `orange_pi_totem` deixa de ser editado manualmente.
   Um importador reproduzivel deve atualizar o arquivo e `SOURCE.json`, e um
   gate deve recusar divergencia.
5. Futuras placas usarao um controle remoto assinado que autoriza um alvo exato.
   Nao sera usado GitHub `latest` para escolher player.

Isso cria duas responsabilidades, sem dois deploys concorrentes:

| Responsabilidade | Fonte |
| --- | --- |
| Desenvolvimento e testes do comportamento do player | `kiosky-player/appliance-v0.1` |
| Integracao com a imagem C18, gates, pacote e distribuicao | `orange_pi_totem/player-runtime` |

O repo `kiosky-player` nunca publica diretamente para placas. O repo
`orange_pi_totem` nunca inventa uma segunda versao editavel do player.

## Fatos Que Sustentam A Decisao

- O auto-pull de C23 ja funciona na prod8 com alvo exato, no-op, rollback,
  restauracao e health em placa.
- A autorizacao atual esta embutida na imagem e aceita somente C23. Publicar
  C24 no GitHub nao move uma placa prod8 automaticamente.
- O `kiosky-player` atual tem 3.558 linhas e o snapshot C23 tem 4.106. Os dois
  possuem correcoes exclusivas.
- Na execucao local desta rodada, a suite atual do `kiosky-player` passou
  105/105; os testes C18 do runtime e do release gate tambem passaram.
- No ensaio temporario desta rodada, substituir o arquivo do repo pelo snapshot
  C23 sem reconciliacao quebrou 19 dos 105 testes. Portanto, copiar por cima
  foi rejeitado.

## Vertical 1 - Convergencia Da Fonte

1. Preservar em remoto o commit local `cc8e995` antes de iniciar a integracao.
2. Criar uma branch de convergencia a partir de `appliance-v0.1`.
3. Reconciliar por comportamento, nao por overwrite:
   - manter normalizacao e origem da duracao do `kiosky-player`;
   - manter `source_path`, integridade de midia, sidecar H.264 e
     last-known-good da C22;
   - manter wrapper de HW decode, verificacao do path real, teardown seguro e
     IPC fresh serializado da C18/C23;
   - manter defaults especificos do perfil appliance sem rebaixar o perfil
     generico de desktop.
4. Levar para o repo fonte os testes de comportamento que hoje existem somente
   no repo de entrega.
5. Criar o importador por repo, branch, commit, path e SHA exatos.
6. Importar o resultado em `orange_pi_totem`, executar gates e provar apply,
   no-op, rollback e restauracao na placa.

A convergencia fecha quando:

- nenhum commit necessario existe apenas localmente;
- os testes dos dois repos passam;
- o importador e idempotente;
- o snapshot e derivavel byte a byte do commit declarado;
- alteracao manual do snapshot falha no gate;
- o C23 continua reproduzindo sem regressao antes de promover qualquer C24.

## Vertical 2 - Autorizacao Remota De Novos Alvos

A prod8 possui timer e apply seguros, mas a autorizacao C23 e local. A proxima
imagem de referencia deve acrescentar:

- chave publica de producao no device; a chave privada fica fora do repo e da
  imagem;
- leitura de registros de controle assinados e imutaveis, publicados pela
  esteira de entrega;
- `component=player-runtime` obrigatorio; `totem-core`, `kiosky-player`,
  `media-system` e `field-data` devem ser recusados;
- geracao monotona persistida atomicamente antes de qualquer efeito; `apply`,
  `pause` e `rollback` com geracao menor ou igual a ultima vista devem ser
  recusados;
- acoes explicitas `apply`, `pause` e `rollback`;
- alvo exato preso a repo, tag, versao, commits e hashes de manifest, payload e
  release gate;
- falha de download, assinatura ou schema como no-op fail-closed;
- rollback e quarentena existentes; um alvo exato em quarentena continua
  bloqueado mesmo sob nova geracao e so pode ser repetido por acao assinada
  explicita de `retry/unquarantine`.

O controle assinado escolhe uma release imutavel. Ele nao move nem consulta
`latest` de player. O fluxo existente de download, verify-then-promote, health,
marker, symlink e rollback deve ser reutilizado, nao reimplementado.

Essa capacidade exige uma nova imagem uma vez, provisoriamente chamada prod9,
porque o updater e a chave de confianca ficam na parte fixa da imagem. Depois
dela, futuras versoes do player nao devem exigir regravacao. Em uma frota
mista, prod8 ignora o controle assinado e permanece em C23; prod9 consome o
controle v1. Publicar C24 nao altera prod8. Um bootstrap assistido alternativo
so pode entrar depois de validar image tag e chave de confianca da placa.

## Operacao Normal Depois Da Transicao

1. Dev abre PR no `kiosky-player/appliance-v0.1` e passa testes de comportamento.
2. Uma promocao importa o commit exato para `orange_pi_totem`.
3. O repo de entrega roda gates, simulacao e teste proporcional ao risco na
   placa.
4. A release imutavel e publicada sem `latest` de player.
5. O operador publica um novo registro assinado apontando para aquela release.
6. O timer das placas verifica o registro, aplica, valida e volta sozinho se a
   versao falhar.

No primeiro momento o rollout pode continuar global com atraso aleatorio,
conforme o risco de negocio ja aceito. Grupos, dashboard e telemetria de frota
continuam no roadmap e nao mudam esta fronteira.

## Teste Decisivo Da Nova Estrutura

Antes de escala, uma imagem nova deve provar na placa:

1. registro ausente, adulterado, antigo ou pausado nao altera o player;
2. release boa e assinada aplica, passa health e vira `current`;
3. repeticao da mesma autorizacao e no-op;
4. release propositalmente ruim nao vira ativa, ou volta para a anterior;
5. o alvo ruim fica em quarentena e nao entra em loop de tentativas;
6. nova geracao para o mesmo alvo ruim continua bloqueada sem `retry` assinado;
7. comando assinado de rollback retorna ao alvo anterior;
8. C23 e a imagem continuam sendo fallback conhecido.

## Fora Desta Decisao

- atualizar MPV, FFmpeg, kernel ou imagem por `player-runtime`;
- liberar `latest` amplo para player;
- publicar diretamente pelo caminho legado `kiosky-player`;
- exigir grupos, dashboard ou A/B de imagem para o primeiro slice;
- afirmar que a convergencia, o controle assinado ou a nova imagem ja foram
  implementados.
