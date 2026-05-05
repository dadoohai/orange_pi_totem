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
CONFIRMO APPLY REFRESH INSTALLER C10.8.1 NA PLACA DEV
```

Em C10.8 esse apply nao foi executado. Em C10.8.1 ele foi executado de forma
controlada para alinhar apenas deltas de reprodutibilidade.

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

## Atualizacao C10.8.1

C10.8.1 resolveu os deltas de reprodutibilidade deixados pelo C10.8:

- pin do `kiosky-player` definido como repo `dadoohai/kiosky-player`, ref
  `appliance-v0.1`, commit
  `c71318a64c08e47b8426f1388b95f21364d57123`;
- `/opt/totem/bin/kiosky_service_launcher.sh` classificado como
  `REPO_AHEAD_REFRESH_BOARD` e atualizado na placa por apply refresh;
- `/opt/totem/bin/totem_wifi_local_credentials_tty.py` mantido como fallback
  seguro e instalado por apply refresh;
- `/data/state/totem-appliance` criado para o manifest instalado sanitizado;
- diretorios `/data/state/totem-display`, `/data/state/totem-boot-visual` e
  `/data/state/totem-settings` reclassificados como runtime state, sem hash de
  conteudo e com metadata restrita `0700 root:root`.

Apply refresh C10.8.1 executado:

- instalacao de pacotes: nao;
- upgrade: nao;
- reboot: nao;
- writer: nao;
- Wi-Fi/NetworkManager: nao;
- config real: conteudo nao lido e nao alterado;
- `kiosky-player`: nao alterado;
- restart de servicos de produto: nao.

Resultado final:

- `verify-dev`: `overall_status=ok`;
- `ready_for_second_board=true`;
- `blockers: none`;
- `idempotence-dev-dry-run`: `stable=true`;
- primeira execucao dry-run pos-apply: `action_count=0`;
- segunda execucao dry-run pos-apply: `action_count=0`;
- estado operacional final: `player_running`, playback `playing`,
  `NRestarts=0`, sem lock/request e sem processo de setup remanescente.

Aviso esperado: a arvore instalada do `kiosky-player` na placa dev nao tem
metadados Git, entao o commit atual da arvore nao e verificavel por Git sem
alterar o app. Isso nao bloqueia C10.9 porque a segunda placa deve instalar o
app a partir do pin fixado no manifest.

Conclusao: C10.8.1 deixa o instalador/verificador acionavel para iniciar C10.9
na segunda placa/cartao.

## Atualizacao C10.9

C10.9 usou o instalador C10.8.1 em uma segunda placa/cartao com Armbian base
limpo e validou a reproducao por script:

- bootstrap manual previo restrito a senha root e rede/SSH de bancada;
- `--prepare-only`, `--inspect-base` e `--install-dry-run` executados;
- apply com confirmacao humana explicita;
- runtime minimo instalado por `apt-get install --no-install-recommends` para
  `mpv`, `ffmpeg` e `python3-requests`, sem upgrade amplo;
- `kiosky-player` instalado do pin
  `c71318a64c08e47b8426f1388b95f21364d57123`;
- reboot controlado com confirmacao humana explicita;
- verify pos-boot: `overall_status=ok`;
- idempotencia final: `stable=true`, `first_action_count=0`,
  `second_action_count=0`;
- config real ausente, `public_state=config_missing`,
  `config_missing_safe=true`;
- F10 assistido abriu Configuracoes e cancelou limpo.

Durante C10.9 foi corrigido um caso de placa limpa: quando nao existe
`/data/config/config.json`, `totem_open_settings_session.sh` degrada o fluxo F10
de `real-write` com fonte `active-config` para `candidate-only`, evitando falha
antes de abrir a tela de Configuracoes. Essa correcao nao chama writer e nao le
config privada.

Observacao posterior a C10.9 detectou duas pendencias antes de C11.0:

- o manifest/installer precisava incluir `totem_status_render_preview.py`, usado
  por `totem_status_aggregate.py` para gerar o SVG publico de status;
- placa limpa sem `/data/config/config.json` fica em `candidate-only` e nao
  escreve config real sem um provisionamento privado explicito.

Conclusao atualizada C10.9: instalacao limpa em segunda placa validada para a
camada appliance, mas ainda nao pronta para C11.0 read-only readiness audit sem
C10.9.1.

## Atualizacao C10.9.1

C10.9.1 aplicou o refresh da segunda placa e concluiu o provisionamento real
controlado:

- `totem_status_render_preview.py` instalado pelo manifest;
- feedback visual de `config_missing` validado como `config_pending`, sem ficar
  preso em "Iniciando player";
- fluxo `candidate-only` sem config ativa validado sem writer e sem config real;
- arquivo privado temporario em `/tmp` validado com diretorio `0700`, arquivo
  `0600`, sem symlink e sem imprimir valores;
- `environment_id` veio do wizard visual;
- C5.1 real-dry-run passou;
- writer real escreveu `/data/config/config.json`;
- permissoes finais `root:totem 0640`;
- temporarios privados removidos;
- player final `public_state=player_running`, `playback=playing`,
  `NRestarts=0`, `systemctl_failed_count=0`.
- reboot controlado pos-provisionamento manteve config presente,
  `public_state=player_running`, `playback=playing`,
  `systemctl_failed_count=0` e `kernel_critical_filter_count=0`.

Com C10.9.1, a segunda placa fica pronta para C11.0 read-only readiness audit.
C10.9.1 ainda nao gera imagem final, nao habilita root read-only e nao substitui
o backend/login final de ativacao.

## Atualizacao C10.10

C10.10 empacota o instalador/verificador como RC de bancada instalavel:

- runbook unico: `docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`;
- manifest RC: `releases/installable-rc/manifest.md`;
- helper seguro de private-values:
  `scripts/board/totem_private_values_prepare.py`;
- runner C10.9.1 atualizado com `--validate-private-values`.

O instalador C10.8 continua sendo a base operacional. O pacote C10.10 nao muda
player, writer, Wi-Fi, config real, read-only ou imagem final; apenas consolida
o caminho reproduzivel e reduz erro humano no provisionamento privado de
bancada.
