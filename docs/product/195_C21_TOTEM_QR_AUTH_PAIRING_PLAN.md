# 195 - C21 Totem QR Auth Pairing Plan

Estado: 2026-07-08.

## Objetivo

Trocar a configuracao manual de ambiente por um fluxo simples de pareamento:
o totem mostra um QR code, o operador autoriza pelo celular em `home.dadooh.ai`,
escolhe um ambiente permitido e o totem passa a ter a configuracao necessaria
para operar.

O alvo nao e login humano dentro da placa. O alvo e autorizar a placa e entregar
a ela uma credencial de maquina, limitada ao ambiente escolhido.

## Decisao Central

- O usuario faz login no `home.dadooh.ai`, usando o fluxo Firebase ja existente.
- A placa nunca guarda token Firebase de pessoa.
- O backend valida se o usuario pode acessar o ambiente escolhido.
- O backend emite uma credencial por dispositivo, revogavel e limitada.
- O totem continua usando o contrato atual do player:
  `api_url`, `api_key`, `environment_id` e, quando existir, `station_id`.
- A mudanca entra por `totem-core`; nao exige alterar `player-runtime` nesta
  etapa.

## Fatos Verificados Nesta Abertura

- `homeHabitat` na branch `feat/pills-media-doc` ja autentica com Firebase e
  carrega ambientes via `GET /environments?only_roots=true`.
- `Habitat` em `firebase-functions/functions/src` ja aceita Firebase Bearer e
  `x-api-key`, possui `api_tokens` e filtra ambientes por permissoes/allowed
  roots.
- O wizard atual do totem ja valida ambiente remoto usando `api_url`/`api_key`
  privados e ja sanitiza saidas publicas.
- O writer real ja sabe gravar uma configuracao com `api_url`, `api_key`,
  `environment_id` e `station_id`.
- Nao existe ainda um fluxo proprio de pareamento por QR. `connection-pins`
  nao e pareamento de dispositivo.

## Fluxo Alvo

1. O operador abre o wizard no totem.
2. Depois de rede disponivel, o totem pede ao backend uma sessao curta de
   pareamento.
3. O totem mostra QR code, codigo curto e tempo de expiracao.
4. O celular abre `home.dadooh.ai/totem/activate?code=...&activation_id=...`.
5. Se necessario, o usuario faz login.
6. O front mostra os ambientes permitidos para aquele usuario.
7. O usuario escolhe o ambiente e confirma a autorizacao do totem.
8. O backend valida a permissao, cria/atualiza o dispositivo e emite uma
   credencial de maquina.
9. O totem faz polling ate receber `api_url`, `api_key`, `environment_id` e
   opcionalmente `station_id`.
10. O wizard mostra revisao, grava candidata privada e usa o writer real
    existente para concluir.
11. O player volta usando a configuracao final.

## Fronteiras De Responsabilidade

- `homeHabitat`: tela de autorizacao pelo celular, login, lista de ambientes,
  escolha de ambiente e confirmacao.
- `Habitat/functions`: sessoes de pareamento, expiracao, autorizacao,
  emissao/revogacao de token de dispositivo, auditoria e validacao de permissao.
- `orange_pi_totem` / `totem-core`: tela QR no wizard, polling, estados de
  sucesso/erro/expirado, revisao, candidata privada, handoff para writer e QA
  visual/OTA.
- `player-runtime`: fora desta etapa, salvo se o contrato final do config mudar
  de forma incompativel, o que nao e o plano.

## Guardrails

- Nao persistir token Firebase humano na placa.
- Nao publicar `api_key`, token, URL privada, ambiente bruto ou dados de usuario
  em SVG, status publico, evidencia, journal ou README.
- Codigo de pareamento deve expirar, ser de uso unico e aceitar cancelamento.
- Rotas de pareamento nao devem confiar em `x-user-id` como autenticacao de
  producao.
- Credencial de maquina deve ser hashada no backend, revogavel e limitada ao
  ambiente/dispositivo.
- Manter fallback manual de ambiente para laboratorio e suporte.
- Se novo helper entrar em `totem-core`, atualizar allowlist do pacote, updater
  e gate OTA antes de aplicar na placa.
- F10/settings precisa continuar restaurando player, limpando locks e
  preservando rollback.

## Verticais De Entrega

### C21.0 - Contrato E Mock

Definir nomes de endpoints, payloads, estados e erros. Criar testes com backend
mockado antes de tocar placa real.

Estados minimos: `pending`, `authorized`, `expired`, `denied`,
`backend_unavailable`, `empty_environment_list` e `already_used`.

### C21.1 - Backend Real

Adicionar endpoints de pareamento em `Habitat/functions`, com testes de:
permissao, TTL, uso unico, token hashado, revogacao, rate limit e bloqueio do
fallback inseguro por `x-user-id`.

### C21.2 - Front De Autorizacao

Adicionar rota no `homeHabitat` para abrir pelo QR, reaproveitar login atual,
listar ambientes do usuario e confirmar a autorizacao.

### C21.3 - Totem Candidate-Only

Adicionar cliente de pareamento e tela QR no wizard, mas primeiro gerar apenas
candidata em `/tmp`/`/run`, sem escrita real de config.

### C21.4 - Integracao Em Placa

Rodar o fluxo real com a placa, ainda em modo controlado: QR, celular, ambiente,
polling, candidata, revisao, cancelamento, expiracao e retorno ao player.

### C21.5 - Escrita Real E OTA

Conectar o resultado autorizado ao writer real, validar rollback, empacotar em
`totem-core`, aplicar por OTA na placa e registrar evidencia visual.

### C21.6 - Hardening Para Escala

Antes de tratar como padrao de escala: revogacao/rotacao por dispositivo,
auditoria no backend, limites de tentativa, CORS/rate limit apropriados,
desativacao do fallback inseguro onde couber e politica clara para estacao
existente versus nova estacao.

## Testes Obrigatorios

- Backend: self-tests/integracao para sessao criada, autorizada, expirada,
  negada, reutilizada, usuario sem permissao e token revogado.
- Front: usuario logado, usuario deslogado com retorno apos login, lista vazia,
  multiplos ambientes, erro de rede e confirmacao.
- Totem: self-test do cliente, QR renderizado localmente, polling, timeout,
  cancelamento, lista de ambientes, candidata privada e sanitizacao.
- Wizard/placa: C19 visual QA, replay de teclado, F10 abre, Esc/cancelar volta,
  player ativo ao final e sem lock/request residual.
- OTA: gate `c18_ota_release_gate.py`, pacote `totem-core`, apply e rollback.
- Privacidade: varredura para provar que segredos nao foram escritos em
  evidencia publica.

## Decisoes A Fechar Sem Travar A Frente

- Nome final das rotas (`/totem-pairing/...` ou equivalente).
- Se a autorizacao escolhe uma estacao existente, cria uma nova ou permite ambos.
- Tempo de expiracao do QR e politica de renovacao.
- Prazo de validade da credencial de maquina.
- URL final de autorizacao em producao.

Essas decisoes nao bloqueiam C21.0 com mock e contrato; bloqueiam somente a
integracao real.

## Contrato Backend V0

Estado em 2026-07-08: o contrato real implementado usa prefixo
`/totem-auth`, nao `/totem-pairing`. A estrutura conceitual abaixo continua
valida, mas os nomes efetivos sao:

- `POST /totem-auth/activations`
- `GET /totem-auth/activations/lookup?code=...&activation_id=...`
- `POST /totem-auth/activations/:activationId/approve`
- `POST /totem-auth/activations/:activationId/poll`

O front efetivo e `home.dadooh.ai/totem/activate`.

Prefixo proposto: `/totem-pairing`.

- `POST /totem-pairing/sessions`
  - Chamado pela placa sem Firebase.
  - Cria sessao curta com `session_id`, `code`, `authorize_url`,
    `expires_at`, `poll_interval_seconds` e `poll_token`.
  - `poll_token` nao entra no QR, nao vai ao browser e deve ser hashado no
    backend.

- `GET /totem-pairing/sessions/lookup?code=...`
  - Chamado pelo front com Firebase Bearer.
  - Nao deve aceitar `x-user-id` como autenticacao efetiva.
  - Mostra ao usuario somente estado publico da sessao/dispositivo.

- `POST /totem-pairing/sessions/:session_id/authorize`
  - Chamado pelo front com Firebase Bearer.
  - Valida permissao do usuario no ambiente escolhido.
  - Autoriza ambiente e opcionalmente estacao.
  - Nunca retorna `api_key` ao browser.

- `GET /totem-pairing/sessions/:session_id`
  - Chamado pelo totem com `x-pairing-token`.
  - Enquanto pendente, retorna `pending`.
  - Quando autorizado, retorna credencial de maquina:
    `api_url`, `api_key`, `environment_id`, `station_id` opcional,
    `token_type=x-api-key`, `api_token_id` e validade.

Estados backend: `pending`, `authorized`, `expired`, `denied`,
`already_used`.

Estados cliente/totem adicionais: `backend_unavailable` e
`empty_environment_list`.

Riscos bloqueantes do backend real:

- decidir se token de maquina impersona operador ou usa principal de
  dispositivo;
- garantir enforcement global de `allowed_root_ids` para `x-api-key`;
- rejeitar fallback por `x-user-id` nas rotas de pareamento;
- persistir sessoes/dispositivos com hashes de codigo e `poll_token`;
- rate limit especifico para codigo curto;
- retorno ao `authorize_url` apos login no `homeHabitat`.

## Proximo Passo

Executar C21.0: escrever o contrato tecnico minimo e os mocks de teste. Em
seguida, implementar o caminho `candidate-only` no wizard antes de qualquer
escrita real de configuracao ou mudanca de producao.

Nota de governanca: para slices OTA em placas ja em campo, nao basta o HEAD
aceitar novos arquivos. O pacote precisa ser aceito pelo updater que ja esta
instalado na placa. Quando possivel, preferir evoluir o wizard dentro dos
binarios ja permitidos; helpers novos podem ficar no repo/na proxima imagem,
mas nao devem bloquear o OTA atual.

## C21.0 - Resultado Inicial

Implementado o primeiro slice executavel em `totem-core`:

- helper `scripts/board/totem_qr_pairing_client.py`;
- contrato mock com estados `pending`, `authorized`, `expired`, `denied`,
  `backend_unavailable`, `empty_environment_list` e `already_used`;
- artefatos publicos:
  `pairing-session.public.json`, `pairing-result.public.json` e
  `pairing-card.svg`;
- credencial de maquina somente em `private-values.json` com modo `0600`;
- self-test cobrindo autorizacao, estados nao-autorizados, path seguro em
  `/tmp` e ausencia de vazamento de segredo nos artefatos publicos.

Nota posterior C21.2: o helper ficou como contrato/teste no repo, mas nao deve
ser exigido pelo pacote OTA enquanto houver placas com updater anterior que nao
aceita esse arquivo novo na allowlist.

Non-claims desta fatia:

- ainda nao e backend real;
- ainda nao e login real do usuario;
- ainda nao e QR escaneavel final;
- ainda nao escreve configuracao real;
- ainda nao altera placa ou producao.

Proximo slice robusto: integrar esse helper no wizard como fluxo
`Entrar com codigo/QR`, em modo `candidate-only`, preservando o campo manual de
ambiente como fallback.

## C21.1 - Wizard Candidate-Only

Implementado o slice de wizard sem backend real e sem escrita real:

- etapa `Ambiente` agora oferece:
  - `Entrar com codigo/QR`;
  - `Digitar ID manual`;
- o caminho manual preserva validacao UUID e preflight existentes;
- o caminho `codigo/QR` usa o helper C21 mock, gera artefatos em subdir privado
  sob `/tmp`, le somente o `environment_id` do `private-values.json` e avanca
  para Revisao;
- estados nao autorizados voltam para a escolha de Ambiente sem abortar o
  wizard;
- se ja existir ambiente preenchido, o wizard favorece o caminho manual para
  edicao/suporte;
- galeria offline inclui a tela de escolha, manual e pareamento autorizado;
- self-test do wizard cobre pareamento autorizado, `already_used`, permissao
  `0600` da credencial privada e ausencia de vazamento nos artefatos publicos
  do pareamento.

## C21.3 - Backend E Front Reais

Implementado o primeiro slice real fora da placa:

- `Habitat/functions`:
  - sessao de ativacao criada pela placa sem Firebase;
  - codigo e segredo do dispositivo persistidos somente como hash;
  - aprovacao exige Firebase Bearer real, nao apenas fallback por `x-user-id`;
  - browser nunca recebe `api_key` nem `device_secret`;
  - poll da placa exige `device_secret` e entrega `x-api-key` uma unica vez;
  - token de maquina recebe `allowed_root_ids` e o middleware passou a enforcar
    esse limite em permissoes e rotas environment-scoped usadas por dispositivo;
  - migration limpa corrigida para criar `api_tokens` antes do indice.

- `homeHabitat`:
  - rota `/totem/activate` criada fora do dashboard;
  - preserva `code` e `activation_id` do QR;
  - login acontece inline, sem perder a URL do QR;
  - lista ambientes acessiveis e envia aprovacao para o backend;
  - nao chama `poll` e nao recebe credencial do dispositivo.

Validacoes feitas:

- backend: ESLint dos arquivos alterados, typecheck filtrado sem erro C21 e
  transpilacao SWC dos modulos novos;
- front: rota `/totem/activate?...` compilou no Next dev server e respondeu
  `200 OK`;
- typecheck/build globais dos repos continuam vermelhos por dividas antigas
  fora do C21, portanto nao sao usados como criterio isolado desta fatia.

Pendencias antes de chamar isso de fluxo ponta a ponta:

- trocar o mock do wizard pelo backend real `/totem-auth`;
- decidir se a aprovacao seleciona estacao existente, cria estacao nova ou fica
  inicialmente somente em nivel de ambiente;
- remover ou substituir chaves hardcoded legadas em front antigo antes de tratar
  a credencial por dispositivo como postura final de seguranca;
- rodar fluxo real placa + celular + backend + homeHabitat;
- empacotar em `totem-core`, aplicar por OTA e registrar evidencia visual.

Non-claims desta fatia:

- ainda nao ha polling real;
- ainda nao ha QR escaneavel final;
- ainda nao ha tela real em `homeHabitat`;
- ainda nao ha backend `/totem-pairing`;
- ainda nao ha escrita real de configuracao no final do fluxo QR.

## C21.2 - Compatibilidade OTA Em Campo

Achado de placa: o pacote C21.1 passou nos gates locais, mas a placa em C20.9
recusou o apply porque o updater instalado ainda nao permitia o novo arquivo
`totem_qr_pairing_client.py` no tar `totem-core`.

Correcao aplicada ao desenho:

- o helper C21 permanece no repo como contrato/teste para o backend real e para
  imagem futura;
- o wizard passa a ter fallback embutido para o mock de pareamento, sem exigir
  binario novo no pacote OTA;
- o pacote `totem-core` deixa de incluir o helper novo;
- o health check do pacote nao exige o helper;
- o objetivo de placa desta fatia e: pacote aceito pelo updater atual, wizard
  abre com a opcao de codigo/QR, artefatos privados seguem sanitizados, player
  volta ativo e rollback permanece disponivel.

Non-claims desta fatia:

- ainda nao e backend real;
- ainda nao e autorizacao real em `home.dadooh.ai`;
- ainda nao emite credencial real de maquina;
- ainda nao substitui o contrato backend C21 planejado.

## Auditoria Da Abertura

Esta especificacao foi montada a partir de leitura local dos tres repositorios e
auditoria independente por subagentes nas frentes:

- wizard/totem-core;
- `homeHabitat`;
- `Habitat/functions`.

A auditoria externa por Sonnet nao entrou como evidencia desta rodada porque a
CLI local nao estava autenticada. Isso nao bloqueia o plano; ela pode entrar na
revisao visual e de produto das proximas rodadas.
