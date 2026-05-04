# C9.4 - Setup Produto Local V0

Status: implementado como evolucao do experimento C9.3. Nao e producao.

Data: 2026-05-04

## 1. O que foi implementado

C9.4 transforma o wizard local de C9.3 em um fluxo mais proximo de produto,
ainda em TTY/curses e ainda desligado por padrao no launcher.

O wizard agora cobre o trio minimo:

- conexao segura: usar conexao atual em leitura agregada, Wi-Fi futuro ou modo
  bancada/mock;
- ambiente: entrada manual de `environment_id` com validacao de formato C5.1;
- tela: selecao amigavel de orientacao, gravando apenas `rotation_deg` na
  candidata.

Artefatos gerados somente em `/tmp`:

```text
/tmp/dadooh-c9-4-setup-product-v0/config.candidate.json
/tmp/dadooh-c9-4-setup-product-v0/setup-status.json
/tmp/dadooh-c9-4-setup-product-v0/summary.txt
```

O launcher continua chamando o setup somente com
`TOTEM_SETUP_LOCAL_ENABLED=1` e autorun/gatilho explicito. A integracao segue
experimental.

## 2. Como aparece para operador

A tela local tem cabecalho Dadooh, titulo "Configuracao do Totem" e passos
visiveis:

```text
1. Conexao
2. Ambiente
3. Tela
4. Revisao
5. Concluir
```

O operador navega por teclado, com textos curtos, retorno/cancelamento antes de
gerar artefatos e sem shell livre. Falhas esperadas aparecem como mensagem
publica simples; traceback nao e apresentado ao operador.

## 3. O que e real

- validacao local de `environment_id` por formato;
- candidata C5.1 em `/tmp`;
- validacao `allow-mock` da candidata;
- falha esperada em `real-dry-run` enquanto `api_url` e `api_key` sao mock;
- integracao launcher/openvt herdada de C9.3, ainda atras de flag.

## 4. O que e mock ou read-only

- conexao atual usa apenas leitura agregada local, sem SSID, IP, MAC, gateway
  ou DNS em status/summary;
- Wi-Fi real permanece "em breve";
- modo bancada/mock nao verifica internet;
- orientacao grava `rotation_deg`, mas nao aplica rotacao real;
- `api_url` e `api_key` continuam placeholders de contrato.

## 5. O que continua bloqueado

- writer real;
- leitura ou escrita de `/data/config/config.json`;
- alteracao de NetworkManager;
- comandos `nmcli connection up/down/delete/modify`;
- senha Wi-Fi;
- backend/ativacao real;
- alteracao de flags MPV, renderer real, EDID, framebuffer, resolucao ou
  rotacao real;
- alteracao do repositorio `kiosky-player`;
- habilitar setup automatico por padrao.

## 6. Validacao

Local:

```text
bash -n scripts/board/kiosky_service_launcher.sh
bash -n scripts/remote/run_c9_4_setup_product_v0_experiment.sh
python3 scripts/board/totem_setup_local_wizard.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
git diff --check
```

Smoke local da candidata:

```text
python3 scripts/board/totem_setup_local_wizard.py \
  --scripted \
  --environment-id ENV-PRODUTO-LOCAL-01 \
  --rotation-key portrait_right \
  --network-step mock \
  --out-dir /tmp/dadooh-c9-4-setup-product-v0-test

python3 scripts/board/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c9-4-setup-product-v0-test/config.candidate.json \
  --allow-mock \
  --out-dir /tmp/dadooh-c9-4-validate-allow

python3 scripts/board/totem_config_contract_validate.py \
  --candidate /tmp/dadooh-c9-4-setup-product-v0-test/config.candidate.json \
  --real-dry-run \
  --out-dir /tmp/dadooh-c9-4-validate-real
```

Resultado esperado:

- `allow-mock` passa;
- `real-dry-run` falha por mock/placeholder;
- `setup-status.json` e `summary.txt` nao publicam `environment_id`, SSID,
  IP, MAC, gateway, DNS, URL privada, chave ou payload.

Runner remoto:

```text
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --prepare-only
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --run-cancel
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --run-complete
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --run-complete-scripted
```

Os modos `--run-cancel`, `--run-complete` e `--run-complete-scripted` exigem
autorizacao humana textual antes de parar/iniciar o servico real.

## 7. C9.4.1 - validacao HDMI

C9.4.1 validou o caminho de cancelamento com humano no HDMI/teclado e o caminho
de conclusao por `--run-complete-scripted`.

Resultado:

- cancelamento: passou apos marcador sanitizado de cancelamento em `/tmp`;
- conclusao scripted: passou, gerando candidata e artefatos C9.4 em `/tmp`;
- C5.1 `allow-mock`: passou;
- C5.1 `real-dry-run`: falhou como esperado por placeholders;
- servico final: `active/enabled`;
- `NRestarts=0`;
- player final `playing`, MPV ativo, renderer/setup ausentes;
- rede, config real, writer, display real e `kiosky-player` nao foram
  alterados.

Nao foi testado nesta etapa:

- preenchimento manual completo por teclado ate Concluir;
- Wi-Fi real;
- display/rotacao real;
- writer/config real.

## 8. O que nao foi alterado

- config real;
- writer real;
- rede real;
- NetworkManager;
- player principal;
- MPV principal;
- renderer real;
- display/EDID/framebuffer;
- repo `dadoohai/kiosky-player`;
- setup automatico por padrao.

## 9. Risco de display

C9.1.2 e C9.1.3 registraram risco visual de proporcao/escala na placa:
framebuffer/DRM/MPV e modo da tela podem nao preservar proporcao ideal. C9.4
nao tenta corrigir isso. Aplicacao real de display, resolucao e rotacao deve
vir em frente separada, com contrato visual proprio.

## 10. Proximos passos

- abrir C9.5 para Wi-Fi real controlado com adapter estreito, rollback,
  preservacao de Ethernet, timeout e diagnostico sanitizado;
- manter hotspot, portal, backend, writer/config real e producao fora de C9.5
  inicial.
