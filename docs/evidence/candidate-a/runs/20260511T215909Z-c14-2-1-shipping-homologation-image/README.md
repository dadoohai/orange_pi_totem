# C14.2.1 - Shipping Homologation Image (pull updater embedded + timer enabled)

Data: 2026-05-11

## Resultado

```text
c14_2_1_status=passed
image_built=true
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c14-2-1-shipping-homolog_minimal.img
image_bytes=1971322880
image_sha256=4bf59cb3fa7ea4391625cd3f459927162d5ded3ce48e66610f8cb1f8b9e7481a
image_name_contains_c14_2_1=true
docker_run_seconds=1168
build_runtime_min=19.3
artifact_private=true
final_image=false
homologation_shipping_image=true
not_for_production=true
not_for_distribution=true
pull_updater_embedded=true
pull_update_timer_enabled=true
update_timer_interval=6h
update_timer_on_boot=10min
update_timer_randomized_delay=10min
update_timer_persistent=true
github_repo=dadoohai/kiosky-player
update_channel=homologation
git_pull_used_on_device=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
os_update_executed=false
kernel_update_executed=false
kernel_config_changed=false
kernel_recompiled=false
kernel_cache_reused=true
seed_present=true
seed_permissions_ok=true
seed_mode=0600
seed_parent_mode=0700
seed_marker_present=true
seed_content_published=false
card_written=true
card_writer=armbian_imager_on_windows_operator_driven
writer_called_from_builder=false
single_board_validated=true
timer_enabled_runtime=true
timer_active_runtime=true
service_unit_known_runtime=true
updatectl_self_test_runtime=true
manual_apply_latest_tested=true
manual_apply_release_tag=totem-app-homolog-20260511-202109-c71318a
manual_apply_payload_sha256=0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
payload_downloaded=true
payload_sha256_verified=true
app_extracted_to_data=true
current_symlink_updated=true
current_resolves_under_releases=true
kiosky_player_active=true
kiosky_player_enabled=true
health_check_passed=true
agent_journal_apt_invocations=0
agent_journal_pip_invocations=0
agent_journal_git_pull_invocations=0
rollback_previously_tested_in_c14_1_1=true
rollback_retested_in_c14_2_1=false
rollback_retested_reason=already_proven_in_c14_1_1
ready_for_batch_flash=true
ready_for_dispatch=true
c12_readonly_blocked=true
c12_4_blocked=true
poweroff_executed=false
power_cut_tested=false
secrets_published=false
```

## Build

Imagem gerada a partir do runner C14.2.1
(`scripts/build/run_c14_2_1_build_shipping_homolog_image.sh`), que é um
*wrapper thin* sobre o runner já validado C12.1
(`scripts/build/run_c12_1_build_image_lab_readonly.sh`). O wrapper apenas:

- exporta `C13_IMAGE_TAG=c14-2-1-shipping-homolog`;
- exporta `C13_IMAGE_VERSION=c14.2.1`;
- exporta `C12_IMAGE_SUFFIX_MARKER=c12-ro-lab-c14-2-1-shipping-homolog`;
- mantém `C13_EMBED_HOMOLOG_PRIVATE_VALUES=1`;
- mantém `C13_LAB_FIRSTBOOT_CONF_KIND=private`;
- mantém `C13_KERNEL_OVERLAYFS_BUILTIN=1`;
- preserva `ARM_BUILD_DIR` e `KIOSKY_PLAYER_DIR`.

Sequência executada: `check-build-env` → `clone-or-check-armbian-build` →
`prepare-userpatches` → `build-image` → `collect-artifacts` → `summary`.
Tempo de docker run: 1168s (19:18 min). Build reaproveitou cache do Armbian
Build — kernel, BSP, U-Boot, DTB e firmware vieram dos `.deb` pré-buildados
do C13.1.3, sem recompilação.

Arquivos privados ficaram fora do repo em `/home/builder/totem-os/private/`
(diretório 0700, arquivos 0600):

- `/home/builder/totem-os/private/homologation-v0.1-config.json` — seed totem-settings;
- `/home/builder/totem-os/private/firstboot.conf` — Armbian first-login preset.

## C14.1.1 dentro da imagem

Diff de imagem em relação a C13.1.3 (`ad4f58b`):

```
+ /opt/totem/bin/totem-updatectl                                  (Python stdlib only)
+ /opt/totem/bin/totem-kiosky-launcher.sh
~ /opt/totem/bin/kiosky_service_launcher.sh                       (KIOSKY_APP_DIR aware)
+ /etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf
+ /etc/systemd/system/totem-update-agent.service                  (static)
+ /etc/systemd/system/totem-update-agent.timer                    (enabled)
+ /etc/systemd/system/timers.target.wants/totem-update-agent.timer  (symlink — enabled)
+ /data/apps/
+ /data/apps/kiosky-player/
+ /data/apps/kiosky-player/releases/
+ /data/updates/
+ /data/updates/incoming/
```

A integração com o pipeline existente foi feita via `totem_appliance_manifest.json`
(o `customize-image.sh` já chamava `install_totem_appliance.sh --apply`). Não foi
preciso tocar em `customize-image.sh`.

Timer:

```ini
[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
RandomizedDelaySec=10min
Persistent=true
Unit=totem-update-agent.service
```

Service (oneshot static):

```
ExecStart=/opt/totem/bin/totem-updatectl apply-github-latest --repo dadoohai/kiosky-player
```

## Validação offline (snapshot completo)

`scripts/build/inspect_c14_2_1_image_rootfs.py` lê a partição rootfs ext4
da imagem via `debugfs` (sem mount/sudo) e checa 31 invariantes. Todos
passaram:

```text
ok=true
```

Detalhe em `offline-validation.json`:

| check | result |
|---|---|
| `totem_updatectl_present` | true |
| `totem_updatectl_exec` | true |
| `totem_kiosky_launcher_present` | true |
| `totem_kiosky_launcher_exec` | true |
| `kiosky_service_launcher_present` | true |
| `kiosky_service_launcher_exec` | true |
| `kiosky_service_launcher_supports_app_dir` | true |
| `dropin_present` | true |
| `dropin_overrides_execstart` | true |
| `update_agent_service_present` | true |
| `update_agent_timer_present` | true |
| `timer_enabled_on_image` | true |
| `timer_on_boot_10min` | true |
| `timer_interval_6h` | true |
| `timer_randomized_delay_10min` | true |
| `timer_persistent_true` | true |
| `service_targets_kiosky_repo` | true |
| `service_uses_updatectl` | true |
| `seed_present` | true |
| `seed_mode_0600` | true |
| `seed_owner_uid_0` | true |
| `seed_group_gid_0` | true |
| `seed_parent_mode_0700` | true |
| `seed_marker_present` | true |
| `data_apps_dir` | true |
| `data_apps_kiosky_player_dir` | true |
| `data_apps_kiosky_player_releases_dir` | true |
| `data_updates_dir` | true |
| `data_updates_incoming_dir` | true |
| `data_logs_dir` | true |
| `no_real_config_in_data_config` | true |
| `image_name_contains_c14_2_1` | true |

Validação inner-c12-1 (`rootfs-validation.env`) também passou em todas as
gates herdadas de C13.1.3 — destaques:

```text
homologation_seed_present=true
homologation_seed_mode_0600=true
homologation_seed_parent_private=true
homologation_seed_marker_present=true
homologation_seed_required_categories_present=true
homologation_seed_content_published=false
kernel_config_overlayfs_builtin=true
uinitrd_nonempty=true
ready_for_c12_3_boot_ssh_validation=true
```

## Validação on-device

Operador gravou um SD com a `.img` C14.2.1 via Armbian Imager no Windows,
inseriu na placa lab e religou. SSH único na placa booted; senha digitada
uma vez pelo operador (não persistida em script, log ou evidência).

`scripts/remote/validate_c14_2_1_clean_board.sh` validou, em uma sessão:

### 1. Identidade da imagem

```text
lab_firstboot_mode=private_disposable_lab
artifact_private=true
final_image=false
homologation_private_values_embedded=true
homologation_private_seed_enabled=true
homologation_seed_permissions_ok=true
homologation_seed_content_published=false
c12_readonly_blocked=true
c12_4_blocked=true
```

### 2. Binários C14.1.1 instalados via image

```text
updatectl=present
launcher=present
dropin=present
agent_svc=present
agent_timer=present
```

### 3. Seed (sem ler conteúdo)

```text
/data/state/totem-settings/private-values.seed.json  mode=600  owner=root:root
seed_marker=present
```

### 4. /data layout

```text
/data/apps=present
/data/apps/kiosky-player=present
/data/apps/kiosky-player/releases=present
/data/updates=present
/data/updates/incoming=present
/data/logs=present
```

### 5. systemd (diferença chave vs C14.1.1: timer ENABLED na imagem)

```text
systemctl is-active   kiosky-player.service       = active
systemctl is-enabled  kiosky-player.service       = enabled
systemctl is-enabled  totem-update-agent.timer    = enabled
systemctl is-active   totem-update-agent.timer    = active
ExecStart drop-in effective: /opt/totem/bin/totem-kiosky-launcher.sh
```

### 6. Updater self-test e estado inicial

```text
self_test=true
checks.service_unit_known=true        ← agora carregado (no offline tinha false)
checks.app_base_exists=true
checks.data_root_writable=true
checks.log_dir_writable=true
checks.python_stdlib_only=true
checks.systemctl_present=true
checks.updates_dir_exists=true

status (pre-apply):
  current_symlink_target=null         ← prova que é imagem fresca, não C14.1.1 SSH-bootstrap
  previous_symlink_target=null
  state.last_operation=null
  service_active=true
  token_file_present=false
```

### 7. journal do update-agent (zero apt/pip/git pull)

```text
no apt/pip/git pull lines found in agent journal
```

### 8. apply-github-latest manual (smoke)

```text
release_tag=totem-app-homolog-20260511-202109-c71318a
INFO downloading_manifest url=https://github.com/dadoohai/kiosky-player/releases/download/.../*.manifest.json
INFO apply_start source=github:dadoohai/kiosky-player:totem-app-homolog-20260511-202109-c71318a
INFO downloading_payload version=homolog-20260511-202109-c71318a
INFO payload_downloaded bytes=43455 sha256=0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
INFO restarting_service service=kiosky-player.service
INFO health_check_starting
INFO apply_success version=homolog-20260511-202109-c71318a
apply_exit=0
```

### 9. Estado pós-apply

```text
current_symlink_target=releases/homolog-20260511-202109-c71318a
readlink -f /data/apps/kiosky-player/current
  -> /data/apps/kiosky-player/releases/homolog-20260511-202109-c71318a
service_active=true
state.last_operation.status=success
state.last_operation.version=homolog-20260511-202109-c71318a
token_file_present=false
```

Janela end-to-end: ~16 segundos do `downloading_manifest` ao `apply_success`
(incluindo health-check grace de 12s).

## Rollback

Não retestado nesta rodada — vide C14.1.1 (commit `30aaf36`, evidência
`docs/evidence/candidate-a/runs/20260511T203006Z-c14-1-1-github-releases-pull-deploy-mvp/README.md`).
O caminho de código não mudou entre C14.1.1 e C14.2.1; apenas o ponto de
distribuição (bootstrap SSH → embedded image).

```text
rollback_previously_tested_in_c14_1_1=true
rollback_retested_in_c14_2_1=false
rollback_retested_reason=already_proven_in_c14_1_1
```

## Restrições mantidas

- Não rodou `apt update` / `apt upgrade` / `full-upgrade` / `dist-upgrade` /
  `armbian-upgrade` (o `apt` durante o build do rootfs Armbian é pipeline
  base, não OTA do app).
- Não rodou `pip install`.
- Não mudou kernel config; cache de kernel reaproveitado (build emitiu
  `Installing: ...linux-image-current-sunxi64...deb` em vez de
  "Compiling kernel").
- Não mudou board / release / branch (`orangepizero3` / `bookworm` /
  `current`).
- Não mudou U-Boot / DTB / BSP — instalou os `.deb` cached.
- Não tocou Wi-Fi / NetworkManager (Armbian setup default).
- Não publicou conteúdo da seed, config real, api_key, api_url,
  environment_id, SSID, senha SSH ou token GitHub.
- Não executou `poweroff` / corte seco.
- C12 read-only permanece bloqueado.
- C12.4 permanece bloqueado.

## Como gravar e bootar

1. Pelo Windows, com **Armbian Imager**, gravar o arquivo `.img` acima em
   um SD card limpo. Conferir SHA256 antes:

   ```
   4bf59cb3fa7ea4391625cd3f459927162d5ded3ce48e66610f8cb1f8b9e7481a
   ```

2. Inserir SD na placa, ligar.
3. Esperar firstboot Armbian (configura usuário/senha/Wi-Fi a partir do
   `firstboot.conf` privado embutido).
4. Anotar IP da placa.
5. Rodar `validate_c14_2_1_clean_board.sh root@<ip>`.

C12 read-only permanece bloqueado; C12.4 continua bloqueado.
