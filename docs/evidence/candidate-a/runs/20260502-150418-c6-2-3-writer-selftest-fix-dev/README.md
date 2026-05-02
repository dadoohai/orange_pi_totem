# C6.2.3 writer self-test fix - desenvolvimento

Data: 2026-05-02

## Objetivo

Diagnosticar e corrigir a falha de compatibilidade do self-test do writer na
placa de desenvolvimento, sem repetir C6.3A, sem parar servico e sem escrever
em `/data`.

## Referencia

C6.3A foi abortada corretamente na Fase 1 porque
`python3 /tmp/totem_config_writer_real.py --self-test` falhou na placa. A
evidencia da tentativa abortada esta em:

```text
docs/evidence/candidate-a/runs/20260502-143325-c6-3a-config-real-write-service-stopped-dev/README.md
```

## Escopo

- Placa: desenvolvimento, sem publicar IP ou hostname.
- Placa de homologacao: nao usada.
- SSH: usado somente para a placa de desenvolvimento.
- Dados usados: sinteticos e nao-secret.
- Candidata real privada: nao usada e nao lida.
- `/data`: nao escrito.
- Servico: nao parado, nao iniciado e nao reiniciado.
- Modo real: nao executado.

## Reproducao sanitizada

Scripts copiados para `/tmp` na placa:

```sh
scp scripts/board/totem_config_contract_validate.py scripts/board/totem_config_writer_real.py <dev-board>:/tmp/
```

Comandos:

```sh
cd /tmp
python3 --version
python3 /tmp/totem_config_contract_validate.py --self-test
python3 /tmp/totem_config_writer_real.py --self-test
```

Resultado antes da correcao:

```text
python_version: 3.11.2
contract_validator_self_test: ok
writer_self_test: failed
```

Traceback sanitizado coletado sem candidata real:

```text
writer_self_test_error_type: AssertionError
writer_self_test_error_message: real candidate in repository should fail
```

O traceback continha apenas paths sob `/tmp` e nomes de funcoes do self-test.
Nao continha secrets.

## Causa

A falha era um bug de compatibilidade do self-test:

- o teste de "candidate in repo" usava o proprio arquivo
  `totem_config_writer_real.py` como candidata esperada dentro do repositorio;
- no checkout local, o script esta sob um diretorio Git e o teste passa;
- na placa, o script e copiado para `/tmp`, fora de qualquer `.git`;
- com isso, o teste deixava de representar uma candidata em repo e falhava.

Tambem foi identificado que a deteccao de repositorio olhava apenas raizes
derivadas de `__file__` e do diretorio atual, em vez de inspecionar os pais do
path da candidata.

## Correcao feita

Arquivo alterado:

```text
scripts/board/totem_config_writer_real.py
```

Mudancas:

- `path_is_in_repository()` agora inspeciona os pais do proprio path da
  candidata em busca de `.git`;
- o self-test cria um repositorio fake temporario em `/tmp`;
- a candidata sintetica usada para testar o guardrail de repo fica dentro desse
  repo fake;
- os guardrails reais permanecem inalterados;
- o self-test continua sem executar modo real e sem escrever em `/data`.

## Validacao local

Comandos:

```sh
python3 scripts/board/totem_config_writer_real.py --help
python3 scripts/board/totem_config_writer_real.py --self-test
```

Resultado:

```text
self-test: ok
```

Escrita simulada local:

```sh
python3 scripts/board/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c6-2-3-private/candidate.synthetic.json \
  --dest /tmp/dadooh-c6-2-3-writer-simulated/data/config/config.json \
  --backup-dir /tmp/dadooh-c6-2-3-writer-simulated/backups \
  --out-dir /tmp/dadooh-c6-2-3-writer-simulated/out
```

Resultado:

```text
write: passed
backup_created: false
rollback_attempted: false
api-key-scan: ok
```

Permissoes observadas:

```text
700 /tmp/dadooh-c6-2-3-writer-simulated/out
600 /tmp/dadooh-c6-2-3-writer-simulated/out/summary.txt
600 /tmp/dadooh-c6-2-3-writer-simulated/out/writer-status.json
600 /tmp/dadooh-c6-2-3-writer-simulated/data/config/config.json
```

## Validacao na placa

Scripts corrigidos copiados para `/tmp`.

Comandos:

```sh
cd /tmp
python3 --version
python3 /tmp/totem_config_contract_validate.py --self-test
python3 /tmp/totem_config_writer_real.py --self-test
```

Resultado:

```text
python_version: 3.11.2
contract_validator_self_test: ok
writer_self_test: ok
```

Escrita simulada na placa:

```sh
python3 /tmp/totem_config_writer_real.py \
  --candidate /tmp/dadooh-c6-2-3-dev-private/candidate.synthetic.json \
  --dest /tmp/dadooh-c6-2-3-writer-simulated-dev/data/config/config.json \
  --backup-dir /tmp/dadooh-c6-2-3-writer-simulated-dev/backups \
  --out-dir /tmp/dadooh-c6-2-3-writer-simulated-dev/out
```

Resultado:

```text
write: passed
backup_created: false
rollback_attempted: false
api-key-scan: ok
```

Permissoes observadas:

```text
700 /tmp/dadooh-c6-2-3-writer-simulated-dev/out
600 /tmp/dadooh-c6-2-3-writer-simulated-dev/out/summary.txt
600 /tmp/dadooh-c6-2-3-writer-simulated-dev/out/writer-status.json
600 /tmp/dadooh-c6-2-3-writer-simulated-dev/data/config/config.json
```

Estado read-only do servico apos a validacao:

```text
service_is_active: active
```

O servico nao foi alterado.

## Confirmacoes

- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi lido.
- `/data/config/config.json` nao foi escrito.
- `/data/config` nao foi criado.
- Config real nao foi alterada.
- Candidata real privada nao foi usada.
- Candidata real privada nao foi lida.
- Modo real nao foi executado.
- `kiosky-player.service` nao foi parado.
- `kiosky-player.service` nao foi iniciado.
- `kiosky-player.service` nao foi reiniciado.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- `systemd` nao foi alterado.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- `journalctl` nao foi executado.
- Nenhum pacote foi instalado.
- Nenhum secret foi usado ou publicado.

## Conclusao

C6.2.3 corrigiu a compatibilidade do self-test do writer na placa de
desenvolvimento. O writer foi revalidado localmente e na placa com dados
sinteticos e escrita simulada apenas em `/tmp`.

## Recomendacao

Repetir C6.3A desde a Fase 0 apos revisao humana desta correcao e desta
evidencia. A primeira escrita real em `/data/config/config.json` continua
pendente.
