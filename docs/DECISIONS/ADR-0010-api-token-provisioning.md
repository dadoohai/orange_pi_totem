# ADR-0010 - Provisionamento de token/API para config real

## Status

Proposta.

## Contexto

O totem precisa de `api_url` e token/API key para operar. A config minima
esperada pelo player inclui esses campos privados, e C6 precisa de uma forma
segura de provisionar a config real sem bloquear o produto ate existir
ativacao, login ou codigo curto.

Restricoes atuais:

- operador nao deve digitar `api_key` ou token na UI;
- operador nao deve ver `api_key` ou token em tela publica;
- Codex nao deve receber `api_key` ou token;
- README, evidencia, status, summary, diff, log e chat nao devem publicar
  valores reais;
- C6 precisa conseguir validar e escrever config real em desenvolvimento sem
  implementar backend de ativacao agora;
- backend/API pertencem ao projeto, entao modelos futuros de ativacao, login,
  lista de ambientes e emissao de token sao possiveis.

## Decisao proposta para a fase atual

- Manter o modelo API + token.
- Tratar o token como credencial de runtime do totem, nao como token de usuario
  humano.
- Para C6/C6.3, permitir provisionamento local privado da config real.
- Dados reais chegam por canal local privado, fora do Git, fora do Codex, fora
  de README e fora de evidencia publica.
- Operador nao digita token na UI.
- Codex nao ve token.
- Evidencias registram apenas `api_key_present=true/false` e
  `placeholder_detected=true/false`.
- Token pode ficar em `/data/config/config.json` nesta fase, desde que o
  arquivo tenha owner/group/mode restritos conforme plano C6.
- Futuramente, o token deve poder ser emitido, rotacionado e revogado pelo
  backend.

Nesta ADR, `token` e `api_key` nomeiam a mesma classe de segredo operacional
para C6. O nome exato do campo pode continuar como `api_key` enquanto o contrato
existente exigir esse campo.

## Direcao futura

Futuramente, ativacao por codigo, login ou lista de ambientes pode emitir uma
config segura para o totem.

Diretrizes:

- usuario/humano autentica para autorizar provisionamento;
- totem recebe token proprio de dispositivo/station;
- runtime do totem nao deve depender de token permanente de usuario humano;
- token deve ser por dispositivo/station, escopado, revogavel, rotacionavel e
  auditavel;
- token deve ter permissoes minimas para playlist, midia, status e telemetria,
  conforme necessidade real.

## Alternativas consideradas

### Operador digitar api_key na UI

Rejeitada. `api_key`/token e secret e nao deve ser digitado, visto ou
manipulado por operador nao tecnico.

### Codex receber api_key

Rejeitada. Codex, chat, transcript, comandos e evidencia nao devem receber
secrets reais.

### Token global compartilhado por todos os totens

Rejeitado como producao. No maximo pode existir como mock ou bancada se estiver
explicitamente marcado como tal, com escopo controlado e sem ser confundido com
credencial de campo.

### Login do usuario diretamente no totem

Possivel no futuro, mas fora da fase atual. Exige backend, sessao,
autorizacao, tratamento de erro e UX propria.

### Codigo curto de ativacao

Possivel no futuro, mas fora da fase atual. Exige expiracao, troca segura por
config/token, backend e tratamento de falhas remotas.

### Arquivo local privado temporario

Aceito para C6 como caminho de bancada/desenvolvimento. O arquivo deve ficar
fora do Git, fora do Codex e fora de evidencia publica, com permissao restrita
e ciclo de vida definido.

### Variavel de ambiente

Possivel, mas precisa avaliar risco de vazamento em `systemd`, ambiente de
processo, logs, diagnostico e ferramentas de suporte antes de ser adotada.

## Consequencias

- C6 pode avancar sem backend de ativacao.
- Produto nao fica travado por login ou codigo curto agora.
- Ainda sera necessario resolver ciclo de vida do token antes de producao ou
  campo.
- Config real e backups passam a conter secret e exigem permissao, rollback e
  privacidade rigorosos.
- Evidencias nunca devem incluir conteudo real da config.
- C6.2 pode implementar writer real consumindo candidata privada local, mas
  C6.3 continua dependendo de aprovacao humana e dados reais fora do Codex.

## Riscos

- Token em config vazado por backup ou evidencia.
- Token global usado em muitos totens.
- Token sem revogacao.
- Token de usuario humano usado como runtime.
- Falta de rotacao.
- Permissoes fracas em `/data/config/config.json`.
- Placeholder virar producao.

## Mitigacoes

- Permissao restrita para config real.
- Backup restrito e nao versionado.
- Validador bloqueando placeholders.
- Evidencia sanitizada, registrando apenas presenca/ausencia e
  placeholder detectado.
- Token por dispositivo/station no futuro.
- Revogacao e rotacao planejadas.
- Nenhum valor real em docs, chat, README, diff, log, summary ou evidencia.
- Config real fora do Git.

## Proximos passos

1. Atualizar C6.0/C6.1 com esta decisao.
2. C6.2 pode implementar writer real consumindo candidato privado local.
3. C6.3 so executa com dados reais fornecidos fora do Codex.
4. Fase futura deve desenhar ativacao, login ou codigo para emitir token de
   dispositivo.
