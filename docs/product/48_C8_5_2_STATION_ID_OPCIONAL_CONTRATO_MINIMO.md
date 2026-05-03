# C8.5.2 - station_id opcional no contrato minimo

Status: funcional/local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.5.2 revisa o contrato minimo entre setup C8 e writer/config C6 para
reclassificar `station_id` como campo opcional, nao operacional e futuro.

O criterio principal e:

- `api_url` continua valor privado importante;
- `api_key` continua valor privado importante;
- `environment_id` continua necessario;
- `station_id` nao bloqueia a configuracao minima nem C5.1 `real-dry-run`.

## 2. Por que C8.5.2 existe

C8.5.1 provou corretamente que uma candidata real-sintetica pode passar
`real-dry-run` em `/tmp`, mas ainda tratava `station_id` como valor privado
obrigatorio. A auditoria mostrou que isso estava forte demais para o produto
neste estagio.

No player atual, `station_id` e usado como dado opcional de telemetria quando
presente. Ele nao e usado para escolher ambiente, baixar playlist, iniciar MPV
ou executar playback minimo. Portanto ele nao deve impedir a configuracao
minima.

## 3. Auditoria

### Setup C8

O setup ainda gera `station_id` mock na candidata por compatibilidade com as
etapas anteriores. Esse valor permanece em `/tmp` e nao e mostrado no
status/summary.

Decisao: manter o campo na candidata quando existir, mas tratar como opcional.

### Validator C5.1

Antes, `station_id` fazia parte dos campos obrigatorios e `STATION_ID_MOCK`
bloqueava `real-dry-run`.

Agora:

- `station_id` saiu de `REQUIRED_CONFIG_FIELDS`;
- `station_id` entrou em `OPTIONAL_CONFIG_FIELDS`;
- ausencia de `station_id` e valida;
- `station_id` vazio e tratado como ausente;
- `STATION_ID_MOCK` e permitido como valor opcional/futuro;
- `station_id` invalido ainda falha quando presente, para evitar URL, path ou
  segredo no campo.

### Preflight C8.5.0

O relatorio deixou de publicar a categoria
`station_identity_private_value_required`.

Agora ele registra apenas que a identidade de estacao e opcional/futura. A
falha esperada de `real-dry-run` da candidata mock continua vindo de
endpoint/credencial e, no produto, do ambiente ainda mock/local.

### Candidata real-sintetica C8.5.1

C8.5.1 deixou de substituir `station_id`. A candidata real-sintetica substitui
somente:

- `api_url`;
- `api_key`;
- `environment_id`.

Se `station_id` existir na candidata fonte, ele e preservado como opcional. Se
nao existir, a candidata real-sintetica tambem passa `real-dry-run`.

### Writer C6

O writer real usa o validator C5.1 para decidir `real-dry-run`. Com C8.5.2, um
writer futuro nao deve bloquear uma candidata minima apenas pela ausencia ou
pelo mock de `station_id`.

C8.5.2 nao chama writer real, nao usa `--enable-real-write` e nao escreve config
ativa.

### Player

A leitura do repo do player mostrou `station_id` como campo opcional de
config/telemetria. O envio de telemetria inclui `stationId` apenas quando o
valor existe. Playback/setup minimo nao dependem dele.

## 4. Contrato minimo revisado

Campos bloqueantes para a candidata minima:

- `api_url`;
- `api_key`;
- `environment_id`;
- paths e flags operacionais ja definidos em C5.1.

Campo opcional/futuro:

- `station_id`.

`station_id` pode ser usado futuramente para inventario, telemetria,
rastreabilidade ou suporte, mas nao deve ser prerequisito de configuracao
minima enquanto esses fluxos nao forem produto.

## 5. Guardrails

C8.5.2:

- roda somente local/offline;
- usa somente `/tmp`;
- nao usa valores reais;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao le `/data/config/config.json`;
- nao chama writer real;
- nao usa `--enable-real-write`;
- nao chama `systemctl`;
- nao inicia ou para player;
- nao chama MPV;
- nao altera NetworkManager;
- nao chama backend;
- nao registra valor privado em docs, status, summary ou evidencia.

## 6. Criterios de aceite

- C8.1-C8.5.1 nao regridem.
- `station_id` ausente passa C5.1 `real-dry-run` quando os demais campos estao
  reais/sinteticos.
- `STATION_ID_MOCK` nao bloqueia C5.1 `real-dry-run`.
- `station_id` invalido ainda falha quando presente.
- C8.5.0 ainda bloqueia candidata mock.
- C8.5.1 ainda gera candidata real-sintetica em `/tmp`.
- C8.5.1 passa `real-dry-run` substituindo `api_url`, `api_key` e
  `environment_id`, sem exigir troca de `station_id`.
- Status/summary continuam sanitizados.
- Nada toca `/data`, `/opt`, servico, player, MPV, rede ou backend.
- Smoke remoto em `/tmp` passa.
- `git diff --check` passa.

## 7. Testes locais

Self-tests:

```bash
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_setup_writer_preflight.py --self-test
python3 scripts/board/totem_setup_real_synthetic_candidate.py --self-test
```

Smoke local:

- gerar candidata C8 em `/tmp`;
- rodar C8.5.0 preflight e confirmar falha esperada de `real-dry-run`;
- rodar C8.5.1 real-sintetico;
- validar C5.1 `real-dry-run` sobre a candidata real-sintetica;
- confirmar permissoes `0700`/`0600`;
- confirmar que status/summary nao vazam valores.

## 8. Teste remoto

Smoke seguro:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O teste remoto deve provar:

- self-tests passam na placa;
- setup C8 ainda gera candidata;
- C8.5.0 ainda bloqueia candidata mock;
- C8.5.1 gera candidata real-sintetica;
- C5.1 `real-dry-run` passa mesmo preservando `station_id` opcional;
- artefatos ficam em `/tmp`;
- permissao `0700` no diretorio e `0600` nos arquivos;
- nenhum servico, player, MPV, rede, `/data` ou `/opt` e alterado;
- servidor e encerrado ao final.

## 9. Proximos passos

- C8.6 pode preparar o proximo gate de integracao sem reabrir `station_id` como
  requisito bloqueante.
- Uma fase futura de telemetria/inventario pode definir `station_id` por canal
  aprovado, com sanitizacao propria, sem bloquear playback minimo.
