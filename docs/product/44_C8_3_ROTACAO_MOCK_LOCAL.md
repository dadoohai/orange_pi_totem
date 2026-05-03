# C8.3 - rotacao mock/local

Status: funcional/mock local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.3 refina a experiencia de orientacao da tela no setup local. A escolha
principal deixa de ser tecnica, baseada em `0/90/180/270`, e passa a usar
opcoes compreensiveis para operador nao tecnico.

A fase nao aplica rotacao real. Ela apenas escolhe a orientacao na UI e grava
o grau correspondente em `rotation_deg` dentro da candidata local em `/tmp`.

## 2. Por que C8.3 existe

C8.2 tornou a selecao de ambiente mais proxima de produto, mas a etapa de
rotacao ainda pedia graus diretamente. Isso exigia conhecimento tecnico do
operador e podia gerar erro de campo.

C8.3 mantém o contrato tecnico e melhora a linguagem:

- operador escolhe uma orientacao amigavel;
- a tela mostra uma previa simples;
- a revisao mostra texto amigavel;
- `rotation_deg` aparece apenas como detalhe tecnico secundario.

## 3. Relacao com C8.2

C8.2 continua preservado:

- lista de ambientes de teste como caminho principal;
- modo manual avancado como recurso de suporte/bancada;
- candidata gerada somente em `/tmp`;
- validacao C5.1 `allow-mock`;
- `real-dry-run` falhando enquanto houver placeholders.

C8.3 altera apenas a etapa de orientacao da tela.

## 4. Relacao com C8.1.1 e C5.1

C8.1.1 definiu que a rotacao deve ser gravada como `rotation_deg`. C8.3 nao
muda isso.

O validador C5.1 continua sendo respeitado:

- a candidata passa em `allow-mock`;
- a candidata falha em `real-dry-run` enquanto usar placeholders;
- campos obrigatorios e paths continuam iguais.

O validador C5.1 nao valida rotacao hoje; `rotation_deg` segue como campo extra
de handoff para o appliance/player futuro.

## 5. Opcoes de orientacao

| Opcao na UI | Campo tecnico |
| --- | --- |
| Paisagem | `rotation_deg: 0` |
| Retrato - giro para direita | `rotation_deg: 90` |
| Paisagem invertida | `rotation_deg: 180` |
| Retrato - giro para esquerda | `rotation_deg: 270` |

A API local aceita `rotation_key` como caminho principal e ainda aceita
`rotation` numerico por compatibilidade com C8.1/C8.2.

## 6. Preview visual

A tela de orientacao mostra uma previa simples com:

- proporcao paisagem ou retrato;
- marca Dadooh;
- marca superior para indicar o topo da tela;
- mudanca visual conforme a opcao escolhida.

Esse preview nao consulta display real, nao usa MPV e nao aplica rotacao no
sistema.

## 7. Regras de privacidade

- A UI pode mostrar orientacao amigavel e `rotation_deg` como detalhe tecnico.
- `status.json` e `summary.txt` continuam sem `environment_id` bruto.
- `status.json` e `summary.txt` nao copiam nome publico de ambiente.
- Nenhum token, segredo, `api_key`, URL privada, payload, SSID, IP, MAC,
  hostname, gateway, DNS, path privado ou log bruto e publicado.
- Docs, testes e evidencias usam somente dados de teste.

## 8. O que continua fora

C8.3 nao:

- aplica rotacao real;
- chama MPV;
- altera player;
- altera `systemd`;
- escreve em `/data`;
- escreve em `/opt`;
- altera NetworkManager;
- executa `nmcli`;
- implementa Wi-Fi;
- implementa backend;
- implementa writer real;
- usa dados reais;
- libera producao.

## 9. Prototipo atual

O prototipo estatico C8.3 fica em:

```text
docs/product/prototypes/c8-3-rotacao/
```

O prototipo C8.2 permanece preservado como marco da selecao de ambiente.

## 10. Como testar localmente

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
assert "Retrato - giro para direita" in html

payload = json.dumps({
    "environment_mode": "mock",
    "environment_key": "loja-a",
    "rotation_key": "portrait_right",
}).encode("utf-8")
request = urllib.request.Request(
    base + "/api/candidate",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST",
)
response = json.loads(urllib.request.urlopen(request, timeout=5).read().decode("utf-8"))
assert response["ok"] is True
assert response["rotation_degrees"] == 90
print(response["state"])
PY
```

## 11. Como testar na placa

O script remoto generico copia somente o servidor e o validador para `/tmp`,
roda self-tests, sobe o servidor em `127.0.0.1`, submete selecao de ambiente,
submete orientacao amigavel, valida permissao/contrato e encerra o processo.

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O script antigo permanece como wrapper de compatibilidade:

```bash
scripts/remote/run_c8_1_setup_tmp_on_dev_board.sh root@192.168.18.115
```

## 12. Criterios de aceite

C8.3 e aceito quando:

- lista de ambiente C8.2 continua funcionando;
- manual avancado continua funcionando;
- orientacao fica compreensivel para operador nao tecnico;
- preview simples aparece na tela;
- `rotation_deg` continua correto na candidata;
- C5.1 `allow-mock` passa;
- C5.1 `real-dry-run` falha por placeholders;
- status e summary continuam sanitizados;
- nada escreve em `/data` ou `/opt`;
- nada altera servicos, rede ou player;
- self-test local passa;
- smoke local passa;
- validacao visual humana aprova a nova etapa;
- smoke remoto em `/tmp` passa;
- `git diff --check` passa.

## 13. Proximos passos

- C8.4: reset leve e reiniciar player como comandos limitados, ainda com
  guardrails e sem shell para operador.
- C8.5: integrar setup e writer/config em tarefa propria, mantendo
  placeholders bloqueados em modo real.
- C9: retomar Wi-Fi/portal/hotspot somente com adapter seguro, rollback e
  evidencia sanitizada.
