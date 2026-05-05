# C10.8 - Instalador Idempotente do Appliance

Data: 2026-05-05

Status: implementado e validado em modos seguros na placa dev. Nao foi usado
segundo cartao, nao foi gerada imagem, nao houve apply na placa dev, nao houve
writer, reboot, alteracao de Wi-Fi, alteracao de config real, instalacao de
pacotes ou restart do player.

## Entregas

- `scripts/board/totem_appliance_manifest.json`
- `scripts/board/install_totem_appliance.sh`
- `scripts/board/verify_totem_appliance.sh`
- `scripts/board/dadooh-visual-splash.service`
- `scripts/remote/run_c10_8_installer_idempotent.sh`

O manifest declara scripts esperados em `/opt/totem/bin`, units systemd,
layout `/data`, runtime minimo, guardrails visuais de boot, contrato publico
`orientation.json`, arquivos privados que nao entram na imagem e o estado do
pin do `kiosky-player`.

## O Instalador Reproduz

- usuario/grupo `totem`;
- grupos opcionais `audio`, `video` e `render`, se existirem;
- layout `/opt/totem`, `/opt/totem/bin` e `/data`;
- scripts board do produto em `/opt/totem/bin`;
- `kiosky-player.service`;
- `totem-settings-trigger.service`;
- `totem-open-settings.service`;
- `dadooh-visual-splash.service`;
- script de splash em `/usr/local/sbin/dadooh-visual-splash.py`;
- habilitacao das units necessarias;
- guardrails allowlisted de `/boot/armbianEnv.txt`;
- desabilitacao persistente dos gettys de produto;
- `orientation.json` publico seguro, sem ler config real;
- manifest instalado sanitizado em `/data/state/totem-appliance`.

Por padrao, `--apply` nao reinicia servicos de produto. Parada de getty ativo
exige `--manage-running-services`. Instalacao de runtime minimo exige
`--install-runtime` e usa somente `apt-get install --no-install-recommends`,
sem `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`.

## O Instalador Nao Instala

- desktop;
- Chromium;
- Xorg;
- Wayland;
- compositor;
- secrets;
- config real privada;
- SSID/senha;
- IP/MAC/DNS/gateway;
- midias/cache;
- logs brutos;
- backups;
- arquivos candidatos privados;
- read-only/root overlay;
- imagem final.

Tambem nao chama writer, nao altera NetworkManager/Wi-Fi e nao provisiona a
segunda placa nesta rodada.

## Kiosky-player

O estado atual seguro e:

- `/opt/totem/kiosky-player` existe na placa dev;
- nao ha metadados Git no diretorio;
- docs historicos citam commit `c71318a`, mas C10.8 nao assume esse valor como
  pin atual validado;
- manifest registra `PIN_MISSING`.

Bloqueio: antes de preparar segunda placa/cartao, definir repositorio, ref e
commit exatos do `kiosky-player`, ou ajustar o processo para instalar um
artefato versionado com checksum.

## Como Rodar

Somente preparar workspace remoto e self-tests:

```bash
scripts/remote/run_c10_8_installer_idempotent.sh <host> --prepare-only
```

Dry-run na placa dev:

```bash
scripts/remote/run_c10_8_installer_idempotent.sh <host> --dry-run-dev
```

Verify read-only na placa dev:

```bash
scripts/remote/run_c10_8_installer_idempotent.sh <host> --verify-dev
```

Idempotencia dry-run:

```bash
scripts/remote/run_c10_8_installer_idempotent.sh <host> --idempotence-dev-dry-run
```

Apply refresh na placa dev continua bloqueado por confirmacao humana explicita:

```bash
scripts/remote/run_c10_8_installer_idempotent.sh <host> --apply-dev-refresh
```

Frase exigida pelo runner:

```text
CONFIRMO APPLY REFRESH INSTALLER C10.8 NA PLACA DEV
```

Esse apply nao foi executado nesta rodada.

## Validacao C10.8

Rodadas seguras executadas:

- `--prepare-only`: passou;
- `--dry-run-dev`: passou sem alterar a placa;
- `--verify-dev`: executou e listou diferencas claras;
- `--idempotence-dev-dry-run`: passou com `stable=true`.

Resultado dry-run final:

- `status=planned`;
- `action_count=7`;
- `changed_count=0`;
- `ready_for_second_board=false`;
- blocker: `kiosky_player_PIN_MISSING`.

Acoes que o instalador aplicaria hoje na placa dev:

- criar `/data/state/totem-appliance`;
- ajustar metadata dos diretorios publicos/estado de display, boot visual e
  settings;
- reinstalar `/opt/totem/bin/kiosky_service_launcher.sh`;
- instalar `/opt/totem/bin/totem_wifi_local_credentials_tty.py`;
- escrever manifest instalado sanitizado.

Resultado verify final:

- runtime minimo: ok;
- usuario/grupo: ok;
- boot guardrails: ok;
- orientation.json publico: ok;
- `systemctl --failed`: `0`;
- config real presente, sem leitura de conteudo;
- units versionadas: ok;
- diferencas: diretorios de estado, dois scripts em `/opt/totem/bin` e
  `PIN_MISSING`.

Resultado idempotencia dry-run:

- `stable=true`;
- primeira execucao: `action_count=7`;
- segunda execucao: `action_count=7`;
- placa nao alterada.

## Preparar Segunda Placa

Ainda nao iniciar C10.9/segunda placa.

Antes disso:

1. Definir pin/ref/commit ou artefato versionado do `kiosky-player`.
2. Decidir se a placa dev deve receber `--apply-dev-refresh` para alinhar
   `/opt/totem/bin` e metadata de `/data/state`.
3. Reexecutar `--verify-dev` ate restar somente estado privado/provisionado em
   campo.
4. Rodar o instalador em uma placa/cartao novo apenas depois do pin resolvido.
5. Validar idempotencia rodando o instalador duas vezes na segunda placa.

## Pendencias Para C10.9

- `kiosky-player` com pin ausente;
- `/opt/totem/bin/kiosky_service_launcher.sh` diverge da versao do repo;
- `/opt/totem/bin/totem_wifi_local_credentials_tty.py` ausente na placa dev;
- `/data/state/totem-appliance` ainda nao existe na placa dev;
- metadata de diretorios de estado diverge do manifest desejado;
- apply refresh C10.8 nao foi autorizado/executado.

Conclusao: C10.8 criou a base do instalador idempotente, mas C10.9 com segunda
placa ainda nao deve comecar.
