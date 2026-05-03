# C8.7 - gate operacional final antes da escrita real

Status: preflight read-only. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.7 prepara a primeira execucao real integrada setup -> writer/config, mas
ainda aborta antes de qualquer escrita em `/data`.

Esta etapa responde:

- se a placa esta pronta para uma rodada real futura;
- se os guardrails do writer C6 continuam presentes;
- se o fluxo C8.6/C8.6.1 consegue gerar candidata privada, validar
  `real-dry-run` e limpar temporarios;
- quais pontos bloqueiam ou alertam antes da primeira escrita real;
- qual roteiro exato deve ser usado somente na rodada real aprovada.

## 2. Por que C8.7 existe

C8.6 definiu o rito de valores privados em `/tmp`. C8.6.1 provou que
`candidate-private.json` e `private-values.json` podem ser removidos,
preservando apenas evidencia sanitizada.

Antes de acionar C6 em modo real, ainda falta uma decisao operacional: a placa
tem `/data/config`, grupo/usuario, backup-dir e servico em estado compativel
com escrita real? C8.7 faz essa inspecao sem ler config, sem parar servico e
sem chamar writer real.

## 3. Relacao com C6

C6.2.2 e C6.3 ja definiram os guardrails do writer real:

- destino real exato: `/data/config/config.json`;
- backup-dir real exato: `/data/config/backups`;
- flags obrigatorias:
  - `--enable-real-write`;
  - `--confirm-service-stopped`;
  - `--confirm-human-approved-real-write`;
- validacao C5.1 `real-dry-run` antes e depois da escrita;
- backup atomico quando ja existe config ativa;
- rollback se a escrita falhar depois do backup.

C8.7 nao executa esse writer em modo real. Ele apenas verifica se o script C6
continua contendo essas travas e se o self-test do writer passou.

## 4. Script

Script:

```text
scripts/board/totem_c8_7_operational_gate.py
```

Saida padrao:

```text
/tmp/dadooh-c8-7-operational-gate/
```

Artefatos:

- `operational-gate-status.json`;
- `summary.txt`.

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

## 5. Inspecao read-only da placa

C8.7 observa somente metadados e categorias:

- existencia e tipo de `/data`;
- existencia, tipo, owner, group e modo de `/data/config`;
- existencia, tipo, owner, group e modo de `/data/config/config.json`;
- existencia, tipo, owner, group e modo de `/data/config/backups`;
- existencia de usuario/grupo esperados;
- estado read-only de `kiosky-player.service`;
- contagem de processos relevantes por categoria.

C8.7 nao le conteudo de:

- `/data/config/config.json`;
- backups;
- candidata privada;
- arquivo de valores privados;
- logs brutos;
- linhas de comando de processos.

## 6. Verificacao do fluxo C8.6

O gate espera que a etapa anterior tenha deixado status C8.6.1 sanitizado em:

```text
/tmp/dadooh-c8-6-handoff-preflight/handoff-preflight-status.json
```

Ele confirma apenas booleans e contadores:

- cleanup C8.6.1 executado;
- C5.1 `real-dry-run` passou antes do cleanup;
- writer real permaneceu bloqueado;
- `candidate-private.json` nao existe mais;
- `private-values.json` nao existe mais.

## 7. Go/no-go

Saida principal:

```text
go_no_go.decision
go_no_go.next_round_can_be_first_real_write_attempt
go_no_go.blockers
go_no_go.warnings
```

Bloqueios tipicos:

- writer C6 sem guardrails confirmados;
- self-test do writer nao executado ou falhou;
- cleanup C8.6.1 ausente;
- `real-dry-run` privado nao confirmado;
- arquivos privados temporarios ainda presentes;
- `/data/config` ausente ou nao diretorio;
- usuario/grupo esperados ausentes;
- backup-dir nao existe e nao pode ser criado pelo writer.

Alertas tipicos:

- config ativa ausente, indicando primeira escrita sem backup previo;
- servico ativo, exigindo parada/bloqueio na rodada real;
- usuario da aplicacao nao observado.

Mesmo com `go`, C8.7 sempre marca:

```text
immediate_real_write_allowed_now: false
real_write_executed: false
```

## 8. Roteiro exato para a rodada real futura

Este roteiro nao deve ser executado em C8.7. Ele so vale para uma rodada futura
com aprovacao humana explicita.

1. Gerar candidata C8 e valores privados sob `/tmp`.

```bash
python3 /tmp/dadooh-c8/totem_setup_private_handoff_preflight.py \
  --source-candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --private-values /tmp/dadooh-c8-6-private/private-values.json \
  --out-dir /tmp/dadooh-c8-6-handoff-preflight \
  --confirm-private-values-approved
```

2. Validar contrato C5.1 em modo real-dry-run.

```bash
python3 /tmp/dadooh-c8/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c8-6-handoff-preflight/candidate-private.json \
  --real-dry-run \
  --out-dir /tmp/dadooh-c8/contract-private-handoff-real-dry-run
```

3. Parar ou bloquear o player antes da escrita real, em rodada aprovada.

```bash
systemctl stop kiosky-player.service
systemctl is-active kiosky-player.service
```

Ponto de aborto: se `is-active` nao retornar `inactive` ou equivalente
operacional aprovado, nao executar writer real.

4. Executar writer C6 real com destino e backup-dir exatos.

```bash
python3 /tmp/dadooh-c8/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c8-6-handoff-preflight/candidate-private.json \
  --dest /data/config/config.json \
  --backup-dir /data/config/backups \
  --out-dir /tmp/dadooh-c6-real-write \
  --enable-real-write \
  --confirm-service-stopped \
  --confirm-human-approved-real-write
```

5. Coletar somente evidencia sanitizada.

```bash
cat /tmp/dadooh-c6-real-write/summary.txt
```

6. Limpar temporarios privados.

```bash
python3 /tmp/dadooh-c8/totem_setup_private_handoff_preflight.py \
  --private-values /tmp/dadooh-c8-6-private/private-values.json \
  --out-dir /tmp/dadooh-c8-6-handoff-preflight \
  --cleanup-private-artifacts \
  --confirm-cleanup-private-artifacts
```

## 9. Pontos de aborto

Abortar antes de escrita real se:

- valores privados aparecerem em chat, docs, comando, log ou evidencia;
- C5.1 `real-dry-run` falhar;
- C8.6.1 cleanup nao estiver testado;
- `/data/config` estiver ausente;
- `/data/config` for symlink ou nao diretorio;
- backup-dir estiver indisponivel e nao puder ser criado pelo writer;
- servico/player nao puder ser parado ou bloqueado;
- humano nao aprovar explicitamente a escrita real;
- writer C6 nao passar self-test;
- qualquer path real divergir de `/data/config/config.json` e
  `/data/config/backups`.

## 10. Evidencia sanitizada

Coletar apenas:

- status/summary C8.6.1;
- status/summary C8.7;
- status/summary C6 real futuro;
- categorias de servico e processo;
- contadores e decisoes go/no-go.

Nao coletar:

- `candidate-private.json`;
- `private-values.json`;
- conteudo de `/data/config/config.json`;
- conteudo de backups;
- endpoint;
- credencial;
- identificador bruto de ambiente;
- logs brutos com linha de comando.

## 11. Guardrails

C8.7:

- escreve somente em `/tmp`;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao le config real;
- nao le backup real;
- nao chama writer real;
- nao usa `--enable-real-write`;
- nao para/inicia/reinicia servico;
- nao inicia player;
- nao chama MPV;
- nao altera NetworkManager;
- nao chama backend;
- nao usa Wi-Fi;
- nao publica valores privados.

## 12. Testes locais

Self-tests:

```bash
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_setup_writer_preflight.py --self-test
python3 scripts/board/totem_setup_real_synthetic_candidate.py --self-test
python3 scripts/board/totem_setup_private_handoff_preflight.py --self-test
python3 scripts/board/totem_config_writer_real.py --self-test
python3 scripts/board/totem_c8_7_operational_gate.py --self-test
```

Smoke local:

- gerar candidata C8 em `/tmp`;
- gerar candidata privada com valores sinteticos sob `/tmp`;
- validar C5.1 `real-dry-run`;
- executar cleanup C8.6.1;
- rodar C8.7;
- validar permissoes `0700`/`0600`;
- confirmar status/summary sanitizados;
- confirmar `immediate_real_write_allowed_now=false`.

## 13. Teste remoto

Smoke seguro:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O smoke remoto deve provar:

- self-tests passam na placa;
- setup C8 ainda gera candidata;
- C8.6 gera candidata privada temporaria em `/tmp`;
- C5.1 `real-dry-run` passa na candidata privada;
- C8.6.1 remove temporarios privados;
- C8.7 inspeciona placa em modo read-only;
- status/summary C8.7 sao gerados com `0600`;
- out-dir C8.7 fica com `0700`;
- nenhum valor privado aparece em status/summary;
- nenhum servico, player, MPV, rede, `/data` ou `/opt` e alterado;
- servidor e encerrado ao final.

## 14. Proximos passos

Se C8.7 retornar `go_for_next_real_write_round`, a proxima rodada pode ser a
primeira escrita real integrada, ainda com autorizacao humana explicita e
parada/bloqueio do player antes do writer.

Se C8.7 retornar `no_go_until_blockers_resolved`, corrigir os blockers
operacionais e repetir C8.7 antes de tentar escrita real.
