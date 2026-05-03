# C8.2 - selecao de ambiente mock/local

Status: funcional/mock local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.2 evolui o setup minimo para que o caminho principal do operador seja
selecionar um ambiente em uma lista local mock, com nomes publicos, em vez de
digitar um `environment_id` tecnico.

A fase preserva o handoff C8.1.1 com o contrato C5.1:

- candidata gerada em `/tmp`;
- `environment_id` validado pelo validador C5.1;
- rotacao salva como `rotation_deg`;
- `allow-mock` deve passar;
- `real-dry-run` deve falhar enquanto houver placeholders.

## 2. Por que C8.2 existe

C8.1 provou a primeira fatia vertical: iniciar setup, informar ambiente,
escolher rotacao, revisar e gerar candidata local.

C8.1.1 alinhou a candidata ao contrato C5.1.

Mesmo assim, a experiencia ainda era tecnica demais para operador nao tecnico,
porque a tela principal pedia `environment_id`. C8.2 troca esse passo por uma
lista mock/local com nomes publicos.

## 3. Relacao com C8.1

C8.1 continua sendo a base funcional sem Wi-Fi real. C8.2 nao muda os
guardrails:

- sem Wi-Fi real;
- sem backend;
- sem login/codigo;
- sem escrita em `/data`;
- sem escrita em `/opt`;
- sem player, MPV, NetworkManager, `nmcli` ou `systemd`.

A mudanca e de UX e de payload local: o servidor passa a resolver uma selecao
de lista mock para um `environment_id` mock validado.

## 4. Relacao com C8.1.1

C8.1.1 definiu que o setup deve respeitar C5.1 em vez de criar regra paralela.
C8.2 mantem essa decisao.

O servidor continua importando `totem_config_contract_validate.py` localmente e
usa `validate_environment_like_id()` como fonte de verdade para o
`environment_id`.

## 5. Problema do campo tecnico

O operador de campo nao deve precisar saber ou digitar um identificador
interno. A lista mock/local antecipa a experiencia esperada do produto:

```text
Selecionar ambiente
-> escolher nome publico
-> revisar nome publico e rotacao
-> salvar simulado
```

O campo manual continua existindo apenas como modo avancado/de bancada, para
testes controlados sem backend.

## 6. Fluxo de selecao de ambiente

Fluxo C8.2:

```text
Configuracao pendente
-> Iniciar configuracao
-> Selecionar ambiente em lista local mock
-> opcional: inserir environment_id manual em modo avancado
-> Escolher rotacao
-> Revisar
-> Salvar simulado
-> Gerar candidata em /tmp
-> Validar C5.1 allow-mock
-> Provar bloqueio C5.1 real-dry-run
-> Configuracao candidata pronta
```

## 7. Lista mock/local

Catalogo local versionado no servidor:

| Nome publico mock | environment_id mock |
| --- | --- |
| Ambiente Loja A - MOCK | `ENV-MOCK-LOJA-A` |
| Ambiente Recepcao - MOCK | `ENV-MOCK-RECEPCAO` |
| Ambiente Vitrine - MOCK | `ENV-MOCK-VITRINE` |

Esses valores sao fixtures de desenvolvimento. Eles nao representam cliente,
unidade, campanha, local ou ambiente real.

## 8. Opcao manual avancada

O modo manual aceita um `environment_id` somente quando ele passa na validacao
C5.1. Esse modo existe para bancada e compatibilidade com o fluxo C8.1.

Regras:

- nao usar ID real;
- nao usar URL;
- nao usar token, segredo, senha ou `api_key`;
- nao usar espaco ou barra;
- manter apenas caracteres da allowlist C5.1.

## 9. Regras de privacidade

- A UI pode mostrar o nome mock e o `environment_id` mock durante a sessao.
- `candidate-config.json` contem o `environment_id`, porque e a candidata local
  restrita em `/tmp`.
- `status.json` e `summary.txt` nao copiam o `environment_id` bruto.
- `status.json` e `summary.txt` nao copiam nome publico selecionado.
- `status.json` e `summary.txt` nao copiam `api_key`, token, senha, URL
  privada, SSID, IP, MAC, hostname, gateway, DNS, payload, path privado ou log
  bruto.
- Evidencias e docs usam somente nomes e IDs mock.

## 10. Contrato da candidata

A candidata C8.2 preserva o shape minimo aceito por C5.1:

- `api_url`;
- `api_key`;
- `environment_id`;
- `cache_dir`;
- `state_dir`;
- `status_file`;
- `ipc_path`;
- `runtime_dir`;
- `strict_paths_enabled`;
- `mpv_query_uses_fresh_ipc`;
- `mpv_vo`;
- `mpv_gpu_context`;
- `mpv_ao`;
- `low_resource_mode`.

`station_id` pode existir como campo opcional/futuro, mas nao e requisito
bloqueante para a config minima a partir de C8.5.2.

Campos extras de handoff:

- `rotation_deg`;
- `setup_source`;
- `setup_environment_source`.

`rotation_deg` continua sendo o campo de rotacao compativel com o
appliance/player futuro.

## 11. Validacao C5.1

O servidor valida a candidata em memoria antes de escrever os artefatos:

- modo `allow-mock`: deve passar;
- modo `real-dry-run`: deve falhar enquanto houver placeholders.

O status registra apenas contadores e resultado agregado. A saida bruta do
validador nao e copiada para status, summary ou UI.

## 12. O que continua fora

C8.2 nao:

- implementa backend ou consulta API;
- implementa login, codigo de ativacao ou lista real;
- usa nomes, clientes, locais ou `environment_id` reais;
- implementa Wi-Fi real;
- altera NetworkManager;
- executa `nmcli`;
- cria hotspot, portal real ou QR funcional;
- escreve em `/data`;
- escreve em `/opt`;
- le `/data/config/config.json`;
- inicia ou para `systemd`;
- inicia ou para `kiosky-player.service`;
- inicia MPV;
- altera `kiosky-player`;
- altera homologacao `v0.1-rc1`;
- libera producao.

## 13. Prototipo atual

O prototipo estatico atual fica em:

```text
docs/product/prototypes/c8-2-selecao-ambiente/
```

Ele representa a experiencia principal de C8.2. O prototipo C8.1 fica
preservado como historico do setup minimo manual.

## 14. Criterios de aceite

C8.2 e aceito quando:

- C8.1 e C8.1.1 nao regridem;
- lista mock/local vira caminho principal;
- modo manual fica avancado/de bancada;
- candidata passa em C5.1 `allow-mock`;
- candidata falha em C5.1 `real-dry-run` com placeholders;
- `rotation_deg` e preservado;
- status e summary continuam sanitizados;
- nenhum dado real ou sensivel aparece;
- nada escreve em `/data` ou `/opt`;
- nada altera rede, player ou servico;
- self-test local passa;
- smoke local passa;
- smoke remoto em `/tmp` passa;
- `git diff --check` passa;
- producao continua bloqueada.

## 15. Como testar localmente

Self-tests:

```bash
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
```

Servidor local:

```bash
python3 scripts/board/totem_setup_minimal_server.py \
  --bind 127.0.0.1 \
  --port 8766 \
  --out-dir /tmp/dadooh-c8-1-setup-minimo
```

Abrir:

```text
http://127.0.0.1:8766
```

Smoke via Python stdlib:

```bash
python3 - <<'PY'
import json
import urllib.request

base = "http://127.0.0.1:8766"
html = urllib.request.urlopen(base, timeout=5).read().decode("utf-8")
assert "Selecionar ambiente" in html

payload = json.dumps({
    "environment_mode": "mock",
    "environment_key": "loja-a",
    "rotation": 90,
}).encode("utf-8")
request = urllib.request.Request(
    base + "/api/candidate",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
response = json.loads(urllib.request.urlopen(request, timeout=5).read().decode("utf-8"))
assert response["ok"] is True
print(response["state"])
PY
```

Validar contrato:

```bash
python3 scripts/board/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --allow-mock \
  --out-dir /tmp/dadooh-c8-2-contract-allow-mock

python3 scripts/board/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --real-dry-run \
  --out-dir /tmp/dadooh-c8-2-contract-real-dry-run
```

O segundo comando deve falhar enquanto a candidata usar placeholders.

## 16. Como testar na placa

O smoke remoto seguro copia somente os scripts necessarios para `/tmp`, roda
self-tests, sobe o servidor em `127.0.0.1`, submete selecao mock e modo manual,
valida contrato/permissoes e encerra o processo.

```bash
scripts/remote/run_c8_1_setup_tmp_on_dev_board.sh root@192.168.18.115
```

Notas:

- a senha e digitada interativamente pelo humano;
- o script nao contem senha;
- o script nao usa `sshpass`;
- os artefatos ficam em `/tmp/dadooh-c8-1` e
  `/tmp/dadooh-c8-1-setup-minimo`;
- o roteiro nao toca `/data`, `/opt`, NetworkManager, `systemd`, MPV ou
  player.

## 17. Proximos passos

- C8.3: refinar a experiencia de rotacao mock/local, possivelmente com
  linguagem mais visual.
- C8.5: integrar setup e writer/config em tarefa propria, ainda bloqueando
  placeholders em modo real.
- C9: retomar Wi-Fi/portal/hotspot somente com adapter seguro, rollback e
  evidencia sanitizada.
