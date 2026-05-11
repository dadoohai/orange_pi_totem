# C14.1.1 - GitHub Releases Pull Deploy MVP

Data: 2026-05-11

## Resultado

```text
c14_1_1_status=passed
github_release_created=true
release_tag=totem-app-homolog-20260511-201301-c71318a
release_assets_manifest_present=true
release_assets_payload_present=true
package_sha256=0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
release_v2_tag=totem-app-homolog-20260511-202109-c71318a
release_v2_assets_manifest_present=true
release_v2_assets_payload_present=true
release_v2_payload_sha256=0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
device_bootstrapped=true
ssh_used=true
updatectl_installed=true
launcher_installed=true
service_dropin_installed=true
service_dropin_path=/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf
update_agent_service_installed=true
update_agent_timer_installed=true
update_agent_timer_enabled=false
git_pull_used_on_device=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
os_update_executed=false
kernel_update_executed=false
payload_downloaded=true
payload_sha256_verified=true
app_extracted_to_data=true
app_extracted_path_prefix=/data/apps/kiosky-player/releases/
current_symlink_updated=true
previous_symlink_present_after_v2=true
kiosky_player_restarted=true
service_active_post_apply=true
health_check_passed=true
rollback_available=true
rollback_tested=true
rollback_tested_outcome=success
rollback_swap_observed=true
secrets_published=false
poweroff_executed=false
power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true
mender_used=false
rauc_used=false
swupdate_used=false
device_token_required=false
private_release_blocker_raised=false
```

## Topologia entregue

Builder host (não placa):
- `scripts/deploy/build_kiosky_player_release_package.sh`
- `scripts/deploy/publish_kiosky_player_github_release.sh`
- `scripts/remote/run_c14_1_1_github_releases_pull_deploy_mvp.sh`
- `scripts/remote/apply_c14_1_1_release_on_board.sh`
- `scripts/remote/rollback_c14_1_1_on_board.sh`
- `scripts/remote/test_rollback_c14_1_1_on_board.sh`

Placa (instalado em `/opt/totem/bin/`):
- `totem-updatectl` (Python stdlib only; nenhuma dependência nova)
- `totem-kiosky-launcher.sh`
- `kiosky_service_launcher.sh` (modificado para usar `KIOSKY_APP_DIR` env)

Placa (systemd):
- `/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf` (drop-in)
- `/etc/systemd/system/totem-update-agent.service` (instalado, disabled)
- `/etc/systemd/system/totem-update-agent.timer` (instalado, disabled)

Placa (`/data` layout):
- `/data/apps/kiosky-player/releases/<version>/`
- `/data/apps/kiosky-player/current  -> releases/<version>`
- `/data/apps/kiosky-player/previous -> releases/<prev-version>` (após segundo apply)
- `/data/updates/incoming/<version>/`
- `/data/updates/state.json`
- `/data/logs/totem-update.log`

Backup do binário original mantido em `/opt/totem/.dadooh-c14-1-1-backup/kiosky_service_launcher.sh.orig`.

## Fluxo executado

### Build local (1ª versão)
```
[build_kiosky_player_release_package] version         = homolog-20260511-201301-c71318a
[build_kiosky_player_release_package] source_branch   = appliance-v0.1
[build_kiosky_player_release_package] source_commit   = c71318a64c08e47b8426f1388b95f21364d57123
[build_kiosky_player_release_package] payload_bytes   = 43455
[build_kiosky_player_release_package] payload_sha256  = 0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
```

### Publicação GitHub Release (1ª versão)
```
release_tag=totem-app-homolog-20260511-201301-c71318a
release_url=https://github.com/dadoohai/kiosky-player/releases/tag/totem-app-homolog-20260511-201301-c71318a
prerelease=true
```

Assets na release:
- `dadooh-kiosky-player-homolog-20260511-201301-c71318a.manifest.json` (664 bytes)
- `dadooh-kiosky-player-homolog-20260511-201301-c71318a.tar.gz` (43455 bytes)

### Bootstrap na placa
Trecho relevante do log sanitizado:
```
[c14_1_1_bootstrap] current ExecStart: ExecStart=/usr/bin/env bash /opt/totem/bin/kiosky_service_launcher.sh
[c14_1_1_bootstrap] creating /data layout
[c14_1_1_bootstrap] backed up original launcher to /opt/totem/.dadooh-c14-1-1-backup/...
[c14_1_1_bootstrap] installing /opt/totem/bin/totem-updatectl
[c14_1_1_bootstrap] installing /opt/totem/bin/totem-kiosky-launcher.sh
[c14_1_1_bootstrap] installed drop-in: /etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf
[c14_1_1_bootstrap] installed totem-update-agent.{service,timer} (disabled)
[c14_1_1_bootstrap] systemctl daemon-reload
[c14_1_1_bootstrap] restarting kiosky-player.service
[c14_1_1_bootstrap] post-restart is-active=active
[c14_1_1_bootstrap] self-test passed
```

### Apply (1ª versão) via pull do GitHub
```
INFO downloading_manifest url=https://github.com/dadoohai/kiosky-player/releases/download/totem-app-homolog-20260511-201301-c71318a/...manifest.json
INFO apply_start source=github:dadoohai/kiosky-player:totem-app-homolog-20260511-201301-c71318a
INFO downloading_payload version=homolog-20260511-201301-c71318a
INFO payload_downloaded bytes=43455 sha256=0e4c3bbd5a90fcb8dda3672149da9f1dca26e447a67bc32e311d76f6ec83aa5f
INFO restarting_service service=kiosky-player.service
INFO health_check_starting
INFO apply_success version=homolog-20260511-201301-c71318a
```

`status` pós-apply:
```
current_symlink_target=releases/homolog-20260511-201301-c71318a
previous_symlink_target=null
service_active=true
```

### Apply (2ª versão) — gera previous
```
INFO apply_success version=homolog-20260511-202109-c71318a
```
`status`:
```
current_symlink_target=releases/homolog-20260511-202109-c71318a
previous_symlink_target=releases/homolog-20260511-201301-c71318a
service_active=true
```

### Rollback manual
```
INFO manual_rollback_ok rolled_to=homolog-20260511-201301-c71318a
```
`status` pós-rollback:
```
current_symlink_target=releases/homolog-20260511-201301-c71318a
previous_symlink_target=releases/homolog-20260511-202109-c71318a
service_active=true
```

## Validações principais

1. Pacote `.tar.gz` gerado a partir do repo `kiosky-player` via `git archive` (somente arquivos versionados, exclui `.git`, `__pycache__`, etc.).
2. Manifest `dadooh.totem.update.v1` gerado com `payload_sha256` calculado deterministicamente.
3. Release GitHub criada (pública, prerelease) com manifest + tar.gz como assets.
4. Placa **não** usou `git pull`; somente `urllib.request` sobre HTTPS para `api.github.com` e `releases/download/...`.
5. SHA256 verificado na placa antes da extração; mismatch teria bloqueado a extração.
6. Symlink `current` trocado atomicamente via `os.rename` de um symlink temporário.
7. `kiosky-player.service` reiniciado via `systemctl restart`; health check (`is-active` + grace + `NRestarts` estável) passou.
8. Após segundo apply, `previous` aponta para a release anterior.
9. Rollback manual fez swap (`current ↔ previous`) e reiniciou serviço com sucesso.
10. Nenhum `apt`/`pip`/kernel/u-boot/dtb/bsp foi tocado.
11. Nenhum secret embarcado no pacote (scan regex falha-pra-fora antes de empacotar).
12. `token_file_present=false` em todos os status — release é pública.

## Restrições mantidas

- Não atualizou kernel.
- Não atualizou U-Boot.
- Não atualizou DTB.
- Não atualizou BSP.
- Não atualizou rootfs.
- Não rodou apt update / apt upgrade / armbian-upgrade.
- Não rodou pip install na placa.
- Não alterou Wi-Fi / NetworkManager.
- Não tocou na seed privada de homologação.
- Não imprimiu / persistiu tokens ou senhas.
- Não usou Mender/RAUC/SWUpdate.
- C12 read-only continua bloqueado.
- C12.4 continua bloqueado.

## Observações

- Build determinístico: rodar `build_kiosky_player_release_package.sh` duas vezes para o mesmo HEAD gera tar.gz com o mesmo SHA256 (verificado: ambas versões publicadas têm `payload_sha256=0e4c3bbd...`).
- O drop-in systemd preserva `User=totem`, `WorkingDirectory=/opt/totem/kiosky-player`, `Environment=...`, `ExecStartPre=...`, `ReadOnlyPaths`, `ReadWritePaths`, `Restart`, etc. Apenas `ExecStart` é redefinido.
- O launcher novo delega ao launcher original (`/opt/totem/bin/kiosky_service_launcher.sh`) via `exec`, preservando todo o watchdog/status writer/setup-trigger plumbing.
- `totem-update-agent.timer` foi instalado mas **não habilitado** — apply automático fica pendente de decisão explícita.
- `previous` continua presente após rollback, permitindo re-rollback para a v2 se desejado.

C12 read-only permanece bloqueado; C12.4 continua bloqueado.
