# C8.1 - setup minimo funcional sem Wi-Fi real

Status: fatia vertical funcional/mock local. Nao e producao, nao implementa
Wi-Fi real e nao substitui homologacao.

Data: 2026-05-03

## 1. Objetivo

C8.1 cria a primeira fatia vertical funcional do setup do Produto V1 para o
estado `config_missing`.

O objetivo e provar rapidamente que uma pessoa nao tecnica consegue seguir um
fluxo simples na tela, informar um `environment_id`, escolher rotacao, revisar
e gerar uma candidata local de configuracao em `/tmp`.

Esta etapa continua separada da homologacao `v0.1-rc1`, do writer real, do
Wi-Fi real, do portal/hotspot e do backend.

## 2. Usuario

Usuario alvo: operador de instalacao sem perfil tecnico.

O operador nao deve ver terminal, SSH, JSON, logs, comandos, paths internos,
token, endpoint privado ou diagnostico bruto. A UI pode mostrar o
`environment_id` digitado durante a sessao para revisao local, mas esse valor
nao deve entrar em `summary.txt`, `status.json`, evidencias ou docs.

## 3. Cenario

O cenario coberto e o boot ou execucao em que o appliance esta em
`config_missing`:

```text
Configuracao pendente
-> Iniciar configuracao
-> Informar environment_id
-> Escolher rotacao
-> Revisar
-> Salvar simulado
-> Gerar candidata em /tmp
-> Configuracao candidata pronta
```

## 4. Fluxo minimo

1. A tela mostra "Configuracao pendente".
2. O operador seleciona "Iniciar configuracao".
3. O operador informa um `environment_id` de teste.
4. O operador escolhe uma rotacao entre `0`, `90`, `180` e `270`.
5. A tela mostra uma revisao sem segredo.
6. O operador confirma "Salvar simulado".
7. O servidor gera:
   - `/tmp/dadooh-c8-1-setup-minimo/candidate-config.json`;
   - `/tmp/dadooh-c8-1-setup-minimo/status.json`;
   - `/tmp/dadooh-c8-1-setup-minimo/summary.txt`.
8. A tela mostra "Configuracao candidata pronta".

## 5. O que funciona agora

- Servidor HTTP local em Python, sem dependencia externa, usando biblioteca
  padrao e import local do validador C5.1.
- Bind padrao em `127.0.0.1`.
- Porta padrao `8766`.
- Flags `--bind`, `--port` e `--out-dir`.
- UI local simples para o fluxo C8.1.
- Validacao de `environment_id`.
- Validacao de rotacao.
- Geracao de candidata mock/local em `/tmp`.
- Geracao de status e resumo sanitizados.
- Diretorio de saida com permissao `0700`.
- Arquivos gerados com permissao `0600`.
- Self-test local com guardrails de validacao, privacidade e paths.
- Prototipo estatico versionado em
  `docs/product/prototypes/c8-1-setup-minimo/`.
- Script remoto opcional para executar self-test, validacao C5.1 e smoke na
  placa usando apenas `/tmp`.

## 6. O que e mock

- Wi-Fi e tratado como fora de escopo.
- Backend nao e chamado.
- Ativacao/login/codigo nao existem.
- Lista de ambientes nao e buscada.
- `api_url` e credencial de runtime na candidata usam placeholders seguros.
- `station_id` pode aparecer como placeholder opcional/futuro, sem bloquear a
  config minima a partir de C8.5.2.
- A rotacao e salva como campo de candidata, mas ainda nao e aplicada ao
  renderer, MPV, sistema ou player.
- A candidata nao vira config ativa.
- O player nao e iniciado.

## 7. O que fica fora

C8.1 nao:

- implementa Wi-Fi real;
- altera NetworkManager;
- executa `nmcli`;
- cria hotspot;
- cria portal Wi-Fi real;
- cria QR funcional;
- integra backend;
- implementa login ou codigo de ativacao;
- escreve em `/data`;
- escreve em `/opt`;
- le `/data/config/config.json`;
- inicia ou para `systemd`;
- inicia ou para `kiosky-player.service`;
- inicia MPV;
- altera `kiosky-player`;
- altera a homologacao `v0.1-rc1`;
- usa secrets, endpoints reais ou IDs reais.

## 8. Regras de privacidade

Regras aplicadas:

- `summary.txt` e `status.json` nao copiam o `environment_id` bruto.
- `summary.txt` e `status.json` nao copiam credencial, endpoint privado,
  token, senha, SSID, IP, MAC, hostname, gateway, DNS, payload, path privado ou
  log bruto.
- A UI pode mostrar o `environment_id` digitado durante a sessao para revisao
  local.
- A candidata contem o `environment_id` porque ela representa o arquivo local
  que uma fase futura entregaria ao writer.
- A candidata fica restrita em `/tmp` com permissao `0600`.
- Os testes e docs usam somente valores mock.

## 9. Validacao de environment_id

O `environment_id` e aceito somente quando:

- e obrigatorio;
- tem no minimo 3 caracteres;
- tem no maximo 128 caracteres;
- nao contem espaco;
- nao contem barra;
- nao parece URL;
- nao contem `api_key`, `token`, `secret`, `password` ou `senha`;
- usa apenas letras, numeros, underline, hifen, ponto e dois-pontos.

O servidor rejeita entradas fora dessa allowlist antes de gerar qualquer
candidata.

## 10. Tratamento de rotacao

A rotacao aceita somente:

- `0`;
- `90`;
- `180`;
- `270`.

C8.1.1 consolidou o handoff com o contrato de config e passou a gravar a
escolha na candidata como `rotation_deg`, campo alinhado ao config
appliance/player. Nenhuma
rotacao real e aplicada ao display, renderer, MPV, sistema ou player nesta
fase.

## 11. Relacao futura com writer real

C8.1 gera uma candidata mock/local. A fase futura C8.5 deve decidir como essa
candidata sera convertida para a entrada aprovada do writer real.

Antes de qualquer escrita real, o fluxo futuro deve preservar os guardrails ja
validados em C6:

- validacao de contrato;
- escrita atomica;
- backup restrito quando aplicavel;
- rollback;
- servico parado ou bloqueio equivalente;
- nenhum segredo em status, summary ou evidencia;
- nenhuma config parcial iniciando player.

C8.1 nao chama `totem_config_writer_real.py` e nao escreve
`/data/config/config.json`.

## 12. Relacao futura com Wi-Fi, portal e hotspot

C8.1 evita Wi-Fi real de proposito. O objetivo e validar o esqueleto do setup
sem risco para rede, SSH de bancada, NetworkManager ou player.

Wi-Fi, portal local, hotspot, QR funcional, teste de internet e backend ficam
para C9 ou tarefa propria com adapter estreito, rollback e evidencia
sanitizada.

## 13. Criterios de aceite

C8.1 e aceito quando:

- setup minimo roda localmente;
- self-test local passa;
- smoke local retorna HTML e gera candidata;
- smoke na placa roda usando apenas `/tmp`;
- `environment_id` e rotacao sao capturados;
- candidata e criada em `/tmp`;
- status e summary sao sanitizados;
- diretorio gerado usa `0700`;
- arquivos gerados usam `0600`;
- nenhum dado sensivel aparece em summary/status/docs;
- nenhuma escrita ocorre em `/data` ou `/opt`;
- nenhum comando operacional e executado;
- Wi-Fi, hotspot, backend e writer real continuam fora do escopo;
- `git diff --check` passa.

## 14. Como testar localmente

Self-test:

```bash
python3 scripts/board/totem_setup_minimal_server.py --self-test
```

Servidor local:

```bash
python3 scripts/board/totem_setup_minimal_server.py \
  --bind 127.0.0.1 \
  --port 8766 \
  --out-dir /tmp/dadooh-c8-1-setup-minimo
```

Abrir no navegador:

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
assert "Configuracao pendente" in html

payload = json.dumps({
    "environment_id": "ENV-C8-1-LOCAL-MOCK",
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

Artefatos esperados:

```text
/tmp/dadooh-c8-1-setup-minimo/candidate-config.json
/tmp/dadooh-c8-1-setup-minimo/status.json
/tmp/dadooh-c8-1-setup-minimo/summary.txt
```

## 15. Como testar na placa em /tmp

O script remoto opcional copia o servidor C8.1 e o validador C5.1 para `/tmp`,
executa self-test, sobe o servidor em `127.0.0.1`, faz requisicoes locais com
Python stdlib, valida contrato/permissoes e encerra o processo.

```bash
scripts/remote/run_c8_1_setup_tmp_on_dev_board.sh root@192.168.18.115
```

Notas:

- a senha e digitada interativamente pelo humano;
- o script nao contem senha;
- o script nao usa `sshpass`;
- os artefatos ficam somente em `/tmp/dadooh-c8-1` e
  `/tmp/dadooh-c8-1-setup-minimo`;
- o roteiro nao toca `/data`, `/opt`, `systemd`, NetworkManager, MPV ou
  player.

## 16. Proximos passos

- C8.2: selecao de ambiente mock/local com nomes publicos ou lista local
  controlada.
- C8.3: refinar rotacao mock/local e decidir aplicacao tecnica futura.
- C8.4: reset leve e reiniciar player como comandos limitados, ainda com
  guardrails.
- C8.5: integrar setup com writer/config sem expor segredo e sem player/setup
  disputarem tela.
- C9: retomar Wi-Fi/portal/hotspot somente com adapter seguro e rollback.
