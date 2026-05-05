# C10.8.1 Reproducibility Delta Resolution

Data: 2026-05-05

## Escopo

Resolver deltas C10.8 na placa dev e atualizar a reproducibilidade antes de
iniciar C10.9 na segunda placa. A segunda placa/cartao nao foi usada.

## Garantias

- secrets publicados: `false`;
- config real lida: `false`;
- writer chamado: `false`;
- Wi-Fi/NetworkManager alterado: `false`;
- pacotes instalados: `false`;
- upgrade executado: `false`;
- reboot executado: `false`;
- `kiosky-player` alterado: `false`;
- servicos de produto reiniciados pelo installer: `false`;
- logs brutos coletados: `false`;
- host real, IP, MAC, DNS, gateway, SSID e senha publicados: `false`.

## Comandos

```bash
git status --short
git log --oneline -20
git diff --check
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
bash -n scripts/remote/run_c10_8_installer_idempotent.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json
scripts/board/verify_totem_appliance.sh --self-test
scripts/board/install_totem_appliance.sh --dry-run --out-dir /tmp/dadooh-c10-8-1-local-dry-run
scripts/board/install_totem_appliance.sh --idempotence-check --out-dir /tmp/dadooh-c10-8-1-local-idempotence
scripts/remote/run_c10_8_installer_idempotent.sh <host> --dry-run-dev --local-out-dir /tmp/dadooh-c10-8-1-dry-run-dev-2
scripts/remote/run_c10_8_installer_idempotent.sh <host> --verify-dev --local-out-dir /tmp/dadooh-c10-8-1-verify-dev-before-apply
scripts/remote/run_c10_8_installer_idempotent.sh <host> --idempotence-dev-dry-run --local-out-dir /tmp/dadooh-c10-8-1-idempotence-dev-before-apply
scripts/remote/run_c10_8_installer_idempotent.sh <host> --apply-dev-refresh --local-out-dir /tmp/dadooh-c10-8-1-apply-dev-refresh
scripts/remote/run_c10_8_installer_idempotent.sh <host> --verify-dev --local-out-dir /tmp/dadooh-c10-8-1-verify-dev-final
scripts/remote/run_c10_8_installer_idempotent.sh <host> --idempotence-dev-dry-run --local-out-dir /tmp/dadooh-c10-8-1-idempotence-dev-final
ssh <host> '<operational state sanitized read-only>'
```

## Diferencas Iniciais

| Item | Classificacao | Resultado |
| --- | --- | --- |
| `kiosky_player_PIN_MISSING` | `PINNED_WITH_DOC_SOURCE` | Resolvido no manifest com repo/ref/commit. |
| Launcher divergente | `REPO_AHEAD_REFRESH_BOARD` | Resolvido por apply refresh. |
| Script Wi-Fi TTY ausente | `REPO_AHEAD_REFRESH_BOARD` | Resolvido por apply refresh. |
| `/data/state/totem-appliance` ausente | `MISSING_INSTALLER_STATE` | Resolvido por apply refresh. |
| Diretórios de runtime state | `RUNTIME_STATE_OK` | Manifest/verifier ajustados para metadata real e sem hash de conteudo. |

## Pin do kiosky-player

- repo: `dadoohai/kiosky-player`;
- ref: `appliance-v0.1`;
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`;
- install path: `/opt/totem/kiosky-player`;
- estado na placa dev: sem `.git`, commit instalado nao verificavel por Git;
- politica C10.9: instalar/exportar a partir do commit fixado.

## Apply Refresh

Executado apos confirmacao humana explicita.

Acoes aplicadas:

- criou `/data/state/totem-appliance`;
- instalou `/opt/totem/bin/kiosky_service_launcher.sh`;
- instalou `/opt/totem/bin/totem_wifi_local_credentials_tty.py`;
- escreveu manifest instalado sanitizado.

## Verify Final

- `overall_status=ok`;
- `ready_for_second_board=true`;
- `blockers: none`;
- `systemctl_failed_count=0`;
- `runtime_ok=true`;
- `user_ok=true`;
- `boot_guardrails_ok=true`;
- `orientation_ok=true`;
- `private_config_present_on_dev=true`;
- `private_config_content_read=false`;
- `kiosky_player_pin_status=PINNED`;
- `kiosky_player_verification_level=documented_pin_installed_tree_without_git_metadata`.

Warning esperado:

- `kiosky_player_installed_tree_commit_not_machine_verifiable_without_git_metadata`.

## Idempotencia Final

- `stable=true`;
- `first_action_count=0`;
- `second_action_count=0`;
- `board_changed=false`;
- `ready_for_second_board=true`;
- `blockers: none`.

## Estado Operacional Final

- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `NRestarts=0`;
- `systemctl_failed_count=0`;
- `session_lock_present=false`;
- `request_json_present=false`;
- `setup_process_count=0`;
- `kiosk_process_count=1`;
- `mpv_process_count=1`;
- `public_state=player_running`;
- `player_state=running`;
- `playback_state=playing`;
- `mpv_running=true`.

## Conclusao

`ready_for_second_board=true`.

C10.9 pode iniciar na segunda placa/cartao, desde que o instalador use o pin do
`kiosky-player` registrado no manifest e continue sem embutir secrets, config
real, SSID/senha, midias, logs, backups ou arquivos privados.
