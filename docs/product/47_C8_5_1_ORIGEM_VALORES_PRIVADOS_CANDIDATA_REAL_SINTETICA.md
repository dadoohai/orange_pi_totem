# C8.5.1 - origem de valores privados e candidata real-sintetica em /tmp

Status: funcional/local sintetico. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.5.1 define a origem aprovada futura dos valores privados e prova, ainda em
`/tmp`, que uma candidata sem placeholders passa no contrato C5.1
`real-dry-run`.

Esta etapa nao escreve config real, nao chama writer em modo real, nao usa
`--enable-real-write`, nao toca `/data` ou `/opt`, nao inicia player e nao
altera rede/backend.

## 2. Por que C8.5.1 existe

C8.5.0 formalizou a fronteira entre setup C8 e writer C6, mostrando que a
candidata mock passa em `allow-mock` e falha corretamente em `real-dry-run`.

C8.5.1 avanca um passo sem operar o appliance: troca placeholders por valores
real-sinteticos gerados localmente e valida que o contrato C5.1 aceitaria o
shape resultante em `real-dry-run`.

Isso prova o caminho tecnico sem usar valor real de cliente, backend, token ou
ambiente.

## 3. Origem aprovada de valores privados

Para fase real futura, os valores privados so podem entrar por canal local
aprovado, fora de Git, docs, chat, terminal log e evidencia publica.

Valores que precisam de origem privada:

| Campo | Origem futura aprovada | C8.5.1 |
| --- | --- | --- |
| `api_url` | Provisionamento local privado ou arquivo restrito fora do repo. | Endpoint sintetico local. |
| `api_key` | Provisionamento local privado, digitacao interativa segura ou arquivo restrito fora do repo. | Credencial aleatoria sintetica. |
| `environment_id` | Seleção aprovada por backend/provisionamento ou lista confiavel. | Ambiente sintetico aprovado localmente. |

`station_id` foi reclassificado em C8.5.2 como campo opcional, nao operacional
e futuro. Ele pode vir de inventario/provisionamento se telemetria ou
rastreabilidade exigirem, mas nao e valor privado obrigatorio para a config
minima e nao bloqueia `real-dry-run`.

Se uma fase futura precisar de valor sensivel real, o valor deve ser solicitado
ao humano em canal interativo seguro e nao deve aparecer em comando, script,
doc, log, status, summary ou evidencia.

## 4. Candidata real-sintetica

Script:

```text
scripts/board/totem_setup_real_synthetic_candidate.py
```

Entrada padrao:

```text
/tmp/dadooh-c8-1-setup-minimo/candidate-config.json
```

Saida padrao:

```text
/tmp/dadooh-c8-5-1-real-synthetic/
```

Artefatos:

- `candidate-real-synthetic.json`;
- `real-synthetic-status.json`;
- `summary.txt`.

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

## 5. O que a candidata substitui

A candidata real-sintetica preserva o shape C8/C5.1 e substitui:

- endpoint placeholder por endpoint sintetico;
- credencial placeholder por credencial aleatoria sintetica;
- ambiente mock por ambiente sintetico aprovado localmente.

`station_id`, quando existe na candidata fonte, e preservado como campo
opcional/futuro. Ele pode continuar mock nesta prova sem impedir
`real-dry-run`, desde que nao carregue URL, path ou segredo.

Ela preserva campos de handoff como `rotation_deg` e registra a origem como
local/sintetica. Esses valores continuam sendo dados de teste, nao dados reais.

## 6. Validacao C5.1

C8.5.1 valida:

- a candidata fonte C8 passa `allow-mock`;
- a candidata real-sintetica passa `allow-mock`;
- a candidata real-sintetica passa `real-dry-run`;
- os achados de placeholder foram removidos;
- writer real continua bloqueado.

Passar `real-dry-run` em C8.5.1 nao autoriza escrita real. Significa apenas que
o contrato minimo aceitaria uma candidata sem placeholders.

## 7. Sanitizacao

`real-synthetic-status.json` e `summary.txt` nao copiam:

- candidata fonte completa;
- candidata real-sintetica completa;
- valor de credencial;
- endpoint;
- `environment_id`;
- paths da candidata;
- payload bruto;
- logs brutos.

O arquivo `candidate-real-synthetic.json` contem a candidata completa porque e
o artefato restrito de teste em `/tmp`, com permissao `0600`.

## 8. Guardrails

C8.5.1:

- exige candidata fonte sob `/tmp`;
- exige out-dir sob `/tmp`;
- rejeita candidata fonte invalida;
- escreve somente em `/tmp`;
- nao le `/data/config/config.json`;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao chama writer C6;
- nao usa `--enable-real-write`;
- nao chama `systemctl`;
- nao inicia ou para servico;
- nao inicia player;
- nao chama MPV;
- nao altera NetworkManager;
- nao chama backend;
- nao usa valor real.

## 9. Riscos que continuam

- Canal privado real ainda nao esta implementado.
- Autorizacao humana de escrita real ainda nao existe.
- Servico/player ainda precisam ser bloqueados antes de escrita real.
- Backup/rollback C6 ainda precisam ser preservados no acionamento real.
- Evidencia futura ainda precisa ser revisada para nao vazar valores reais.

## 10. Testes locais

Self-tests:

```bash
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_writer_preflight.py --self-test
python3 scripts/board/totem_setup_real_synthetic_candidate.py --self-test
```

Smoke local:

```bash
python3 scripts/board/totem_setup_minimal_server.py \
  --bind 127.0.0.1 \
  --port 8766 \
  --out-dir /tmp/dadooh-c8-1-setup-minimo
```

Gerar candidata C8 via `/api/candidate` e depois:

```bash
python3 scripts/board/totem_setup_real_synthetic_candidate.py \
  --source-candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --out-dir /tmp/dadooh-c8-5-1-real-synthetic

python3 scripts/board/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c8-5-1-real-synthetic/candidate-real-synthetic.json \
  --real-dry-run \
  --out-dir /tmp/dadooh-c8-5-1-contract-real-dry-run
```

Validar:

- `real-dry-run` passa;
- permissao `0700` no diretorio;
- permissao `0600` nos arquivos;
- status/summary sanitizados;
- nenhum artefato fora de `/tmp`.

## 11. Teste remoto

O smoke remoto copia somente scripts para `/tmp`, gera a candidata C8, roda
C8.5.0, gera a candidata real-sintetica C8.5.1 e valida `real-dry-run`:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O teste remoto deve provar:

- self-tests passam na placa;
- setup C8 continua gerando candidata;
- C8.5.0 continua bloqueando a candidata mock;
- C8.5.1 gera candidata real-sintetica;
- C5.1 `real-dry-run` passa na candidata real-sintetica;
- writer real continua bloqueado;
- nada e escrito em `/data` ou `/opt`;
- nenhum servico, player, MPV, rede ou backend e alterado;
- servidor e encerrado ao final.

## 12. Criterios de aceite

C8.5.1 e aceito quando:

- C8.1-C8.5.0 nao regridem;
- origem futura de valores privados fica documentada;
- candidata real-sintetica e gerada apenas em `/tmp`;
- candidata real-sintetica passa C5.1 `real-dry-run`;
- nenhum valor real e usado;
- status/summary nao vazam valores;
- writer real nao e chamado;
- `/data` e `/opt` nao sao tocados;
- servico, player, MPV, rede e backend permanecem intocados;
- smoke local passa;
- smoke remoto em `/tmp` passa;
- `git diff --check` passa.

## 13. Proximos passos

- C8.6-preflight: definir o roteiro de entrada privada real, sem registrar
  valores, ainda com escrita bloqueada.
- Fase real futura: somente depois de canal privado aprovado, revisao humana,
  servico/player bloqueado, writer C6 revalidando `real-dry-run`, backup e
  rollback confirmados.
