# C6.2.2 - guardrails para modo real do writer

Status: implementacao local de guardrails. Nao executa escrita real.

Data: 2026-05-02

## Objetivo

C6.2.2 prepara o writer para uma execucao futura C6.3A com escrita real em
`/data/config/config.json`, sem executar essa escrita agora.

Objetivos:

- manter o comportamento padrao restrito a `/tmp`;
- adicionar modo real protegido por flags explicitas;
- permitir somente o destino real aprovado;
- restringir backup real a local aprovado;
- exigir candidata privada fora do Git e sob `/tmp`;
- testar guardrails sem escrever em `/data`;
- preparar C6.3A com servico parado.

C6.2.2 nao toca placa, nao usa SSH, nao executa `systemctl`, nao para servico,
nao inicia player, nao le `/data/config/config.json`, nao escreve em `/data` e
nao usa token real.

## Flags obrigatorias

Modo real exige todas as flags abaixo:

```sh
--enable-real-write
--confirm-service-stopped
--confirm-human-approved-real-write
```

Sem as tres flags, qualquer destino fora de `/tmp` continua recusado.

O writer nao verifica nem altera o servico. A flag
`--confirm-service-stopped` e apenas declaracao operacional do operador; a
verificacao real do servico fica para C6.3A.

Status e summary registram apenas flags agregadas:

- `real_write_enabled`;
- `service_stop_confirmed_by_operator`;
- `human_approved_real_write`;
- `real_dest_exact_match`;
- `real_backup_dir_exact_match`;
- `real_candidate_private_tmp`.

## Destino real permitido

Com as flags completas, o unico destino real permitido e:

```text
/data/config/config.json
```

O writer recusa:

- qualquer outro arquivo em `/data`;
- qualquer outro diretorio em `/data`;
- destino em `/opt`;
- destino em `/home`;
- destino dentro do repositorio;
- path relativo;
- path que resolva por symlink para fora do destino aprovado.

Em modo real, o writer esta preparado para aplicar:

- owner `root`;
- group `totem`;
- mode `0640`.

Se owner/group/mode nao puderem ser aplicados em C6.3A, a execucao deve falhar
antes de ser considerada sucesso.

## Backup real permitido

O unico backup-dir real aprovado para C6.3A e:

```text
/data/config/backups
```

Esse diretorio e seus arquivos podem conter secrets porque backup copia config
real. Regras:

- nao versionar;
- nao copiar para evidencia;
- nao imprimir conteudo;
- usar permissoes restritas;
- validar permissoes na placa em C6.3A;
- registrar em evidencia apenas estado agregado, como `backup criado: sim/nao`.

## Candidata privada em /tmp

Em modo real, a candidata deve ser um arquivo absoluto, privado, fora do Git e
sob `/tmp`, por exemplo:

```text
/tmp/dadooh-c6-private/candidate.real.json
```

O writer recusa candidata em:

- path relativo;
- repositorio, quando detectavel;
- `/data`;
- `/opt`;
- `/home`;
- qualquer path que nao resolva sob `/tmp`.

A candidata real deve ser criada e preenchida por canal local privado fora do
Codex, chat, README, diff, log e evidencia.

## Por que self-test nao escreve /data

C6.2.2 e preparacao de codigo, nao execucao real. Por isso, o self-test:

- roda somente em `/tmp`;
- cria candidata sintetica nao-secret em `/tmp`;
- testa o modo real apenas chamando a validacao interna de paths;
- nao chama o fluxo operacional de escrita real;
- nao cria `/data/config`;
- nao le nem escreve `/data/config/config.json`.

## Como prepara C6.3A

C6.2.2 deixa o writer pronto para C6.3A ao exigir:

- flags multiplas para modo real;
- destino exato `/data/config/config.json`;
- backup exato `/data/config/backups`;
- candidata privada em `/tmp`;
- servico declarado como parado pelo operador;
- saida sanitizada sem valores reais;
- mode real `0640` preparado para config ativa;
- owner/group `root:totem` preparados para aplicacao real.

C6.3A continua sendo a primeira fase autorizada a executar escrita real em
`/data`, com a placa de desenvolvimento, servico parado e aprovacao humana.

## Criterios de aceite

- `--help` mostra as flags de modo real;
- self-test passa;
- sem `--enable-real-write`, destino `/data/config/config.json` falha;
- flags incompletas falham;
- com todas as flags, o guardrail aceita apenas o path real aprovado sem
  executar escrita em `/data` durante self-test;
- destino real diferente falha;
- backup-dir real diferente falha;
- candidata em repositorio, `/data` ou `/opt` falha;
- modo padrao em `/tmp` continua passando;
- `api_key` sintetica nao aparece em status/summary;
- nada e escrito em `/data`;
- modo real nao e executado em C6.2.2.

## Criterios de abortar

Abortar C6.3A futura se:

- qualquer flag obrigatoria estiver ausente;
- servico nao estiver parado;
- humano nao aprovar escrita real;
- candidata real precisar passar pelo Codex;
- candidata nao estiver em path privado sob `/tmp`;
- destino real nao for exatamente `/data/config/config.json`;
- backup-dir nao for exatamente `/data/config/backups`;
- owner/group/mode nao puderem ser aplicados;
- `real-dry-run` falhar;
- evidencia exigiria publicar segredo.

## Riscos

- flag real usada acidentalmente;
- path real amplo demais;
- backup real com secret em local errado;
- candidata real versionada no repositorio;
- operador confirmar servico parado sem verificacao real;
- output publicar `api_key`, `api_url`, `environment_id` ou `station_id`.

Mitigacoes:

- tres flags obrigatorias;
- destino real exato;
- backup-dir real exato;
- candidata real apenas sob `/tmp` e fora do Git;
- self-test de guardrails;
- C6.3A separada, com verificacao real do servico parado;
- status/summary sanitizados com estados agregados.
