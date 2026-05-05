# C10.10 - Pacote Instalavel RC de Bancada

Data: 2026-05-05

Status: pacote/runbook RC de bancada consolidado a partir de C10.8, C10.9 e
C10.9.1. Nao e imagem final, nao habilita root read-only e nao substitui o
bootstrap tecnico inicial do Armbian.

## Objetivo

Definir o caminho operacional unico para transformar uma placa com Armbian base
em appliance Dadooh usando o repositorio, o manifest, o instalador idempotente,
o verificador e o provisionamento privado controlado de bancada.

O pacote nao depende de memoria da placa dev e nao copia estado da placa dev.

## O Que Ja E Instalavel

A camada appliance ja e instalavel por script:

- usuario/grupo `totem`;
- layout `/opt/totem`, `/opt/totem/bin` e `/data`;
- scripts board versionados;
- units systemd do produto;
- guardrails visuais de boot;
- `orientation.json` publico seguro;
- manifest instalado sanitizado;
- runtime minimo explicito, quando autorizado;
- `kiosky-player` pelo pin fixado;
- verificador de estado instalado;
- fluxo F10 persistente;
- feedback visual `config_missing`/`config_pending`;
- provisionamento privado de bancada por arquivo restrito em `/tmp`.

## Bootstrap Tecnico Temporario

Antes de rodar o pacote ainda existe bootstrap tecnico manual:

- criar senha inicial de `root`;
- configurar rede/SSH de bancada;
- obter acesso remoto para operar o runner;
- informar o alvo ao operador.

Isso nao e experiencia final de produto. C12.0 deve entregar imagem customizada
que elimina o first-login tecnico do Armbian.

## Etapa Reprodutivel

A parte reprodutivel comeca depois que existe SSH de bancada:

```bash
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --prepare-only
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --inspect-base
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --install-dry-run
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --install-apply
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --verify
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --idempotence-check
```

`--install-apply` exige confirmacao humana explicita. Ele nao cria config real,
nao chama writer, nao embute secrets e nao clona a placa dev.

## Verificacao do Appliance

Depois do apply:

```bash
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --verify
scripts/remote/run_c10_9_second_board_clean_install.sh <root@host> --config-missing-check
```

Resultado esperado antes da config real:

- `overall_status=ok`;
- manifest instalado;
- scripts e units presentes;
- services esperados enabled;
- `config_real_present=false`;
- `public_state=config_missing`;
- status visual seguro, sem shell exposto.

## Private-values de Bancada

C10.10 adiciona o helper:

```bash
scripts/board/totem_private_values_prepare.py
```

Uso no board ou via runner:

```bash
python3 scripts/board/totem_private_values_prepare.py --write-template \
  --path /tmp/dadooh-c10-9-1-private/private-values.json \
  --out-dir /tmp/dadooh-private-values-summary \
  --require-api-url

python3 scripts/board/totem_private_values_prepare.py --validate \
  --path /tmp/dadooh-c10-9-1-private/private-values.json \
  --out-dir /tmp/dadooh-private-values-summary \
  --require-api-url
```

Politica:

- diretorio `0700`;
- arquivo `0600`;
- recusa symlink;
- recusa path fora de `/tmp`;
- nunca imprime `api_key`;
- nao imprime `api_url` literal;
- `environment_id` vem do wizard visual;
- summary contem apenas booleans sanitizados.

Enquanto nao houver fonte real versionada/default de `api_url`, o RC de bancada
exige `api_url` e `api_key` no arquivo privado temporario. A imagem final nao
deve conter nenhum desses valores.

O runner C10.9.1 referencia esse helper:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --prepare-private-template
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --validate-private-values
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --provision-real-config
```

## Provisionamento Real de Bancada

Com private-values validado e confirmacao humana explicita:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --provision-real-config \
  --private-values /tmp/dadooh-c10-9-1-private/private-values.json
```

O fluxo:

- abre wizard visual;
- usa `environment_id` do wizard;
- monta candidata privada temporaria;
- roda C5.1 `real-dry-run`;
- chama writer real somente no modo confirmado;
- escreve `/data/config/config.json`;
- aplica permissoes `root:totem 0640`;
- valida leitura sem escrita pelo usuario `totem`;
- remove temporarios privados;
- aguarda `player_running`.

## Player e Reboot

Verificacao curta:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --verify-player
```

Reboot controlado, somente com confirmacao humana:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh <root@host> --reboot-check
```

Resultado esperado pos-provisionamento:

- config real presente sem publicar conteudo;
- `public_state=player_running`;
- `playback=playing`;
- services active/enabled conforme manifest;
- `NRestarts=0`;
- `systemctl_failed_count=0`;
- `kernel_critical_filter_count=0`.

## O Que Nao Fazer Manualmente

Nao fazer no RC de bancada:

- copiar `/data/config/config.json` da placa dev;
- copiar secrets, backups, logs brutos ou cache de midia;
- editar Wi-Fi/NetworkManager fora do fluxo autorizado;
- rodar writer fora do runner confirmado;
- rodar `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`;
- instalar desktop, Chromium, Xorg, Wayland ou compositor;
- habilitar root read-only;
- fazer corte seco;
- gerar ou clonar imagem final.

## Etapa Futura

C11.0 deve auditar readiness de root read-only sem ainda habilitar read-only em
producao. C12.0 deve gerar a imagem/release customizada, eliminando o bootstrap
tecnico manual do Armbian e mantendo secrets/config real fora da imagem.
