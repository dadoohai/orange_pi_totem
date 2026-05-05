# C10.8.1 - Resolucao de Deltas de Reprodutibilidade

Data: 2026-05-05

Status: concluido na placa dev. Segunda placa ainda nao foi usada.

## Objetivo

Resolver ou classificar os deltas que o C10.8 deixou antes de iniciar C10.9 na
segunda placa/cartao.

## Pin do kiosky-player

O pin deixou de ser `PIN_MISSING` e passou a ser:

- repositorio: `dadoohai/kiosky-player`;
- ref: `appliance-v0.1`;
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`;
- titulo documentado: `Add configurable MPV output flags`;
- install path: `/opt/totem/kiosky-player`.

Fonte: release `v0.1-rc1` e checkout local do app. A placa dev nao tem
metadados Git em `/opt/totem/kiosky-player`, portanto o verificador classifica
o estado como `documented_pin_installed_tree_without_git_metadata`: existe pin
reprodutivel para C10.9, mas o commit exato da arvore instalada atual nao e
verificavel por Git sem alterar o app.

## Deltas Classificados

| Delta C10.8 | Classificacao C10.8.1 | Resolucao |
| --- | --- | --- |
| `kiosky_player_PIN_MISSING` | `PINNED_WITH_DOC_SOURCE` | Manifest registra repo/ref/commit exatos. |
| `/opt/totem/bin/kiosky_service_launcher.sh` diverge | `REPO_AHEAD_REFRESH_BOARD` | Apply refresh instalou a versao versionada. |
| `/opt/totem/bin/totem_wifi_local_credentials_tty.py` ausente | `REPO_AHEAD_REFRESH_BOARD` | Mantido como fallback local seguro e instalado via apply refresh. |
| `/data/state/totem-appliance` ausente | `MISSING_INSTALLER_STATE` | Criado pelo apply refresh para manifest instalado sanitizado. |
| Metadata de `/data/state/totem-display` | `RUNTIME_STATE_OK` | Manifest ajustado para `0700 root:root`; conteudo nao e hashado. |
| Metadata de `/data/state/totem-boot-visual` | `RUNTIME_STATE_OK` | Manifest ajustado para `0700 root:root`; rollback state nao e hashado. |
| Metadata de `/data/state/totem-settings` | `RUNTIME_STATE_OK` | Manifest ajustado para `0700 root:root`; conteudo privado nao e lido. |

## Apply Refresh Executado

Com confirmacao humana explicita, o runner executou somente:

- criar `/data/state/totem-appliance`;
- instalar `/opt/totem/bin/kiosky_service_launcher.sh`;
- instalar `/opt/totem/bin/totem_wifi_local_credentials_tty.py`;
- escrever `/data/state/totem-appliance/manifest-installed.json`.

Nao houve instalacao de pacotes, upgrade, reboot, writer, alteracao de config
real, alteracao de Wi-Fi/NetworkManager, alteracao do `kiosky-player` ou
restart de servicos de produto.

## Resultado Final

- `verify-dev`: `overall_status=ok`;
- `ready_for_second_board=true`;
- `blockers: none`;
- `idempotence-dev-dry-run`: `stable=true`;
- primeira execucao dry-run pos-apply: `action_count=0`;
- segunda execucao dry-run pos-apply: `action_count=0`;
- `systemctl_failed_count=0`;
- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `NRestarts=0`;
- `session.lock=false`;
- `request.json=false`;
- `setup_process_count=0`;
- `public_state=player_running`;
- `playback_state=playing`.

Aviso remanescente esperado:

- `kiosky_player_installed_tree_commit_not_machine_verifiable_without_git_metadata`.

Esse aviso nao bloqueia C10.9 porque C10.9 deve instalar o app a partir do pin
do manifest, nao clonar o estado atual da placa dev.

## C10.9

C10.9 pode comecar na segunda placa/cartao com o instalador C10.8.1, mantendo:

- sem secrets na imagem;
- sem config real privada;
- sem SSID/senha;
- sem midias/cache/logs/backups;
- sem writer durante instalacao base;
- sem `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`;
- deploy do `kiosky-player` no commit fixado antes do verify final.
