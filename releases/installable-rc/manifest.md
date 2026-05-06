# Installable Bench RC Manifest

Data: 2026-05-05

Status:

- `installable_bench_rc=true`
- `final_image=false`
- `read_only=false`
- `power_cut_tested=false`
- `long_test=false`
- `ready_for_c11_readiness=false`
- `c10_10_1_power_state_audit=POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`
- `shutdown_ux_followup_required=true`
- `ready_for_c12_image=false`

## Orange Pi Totem

- repository: `dadoohai/orange_pi_totem`
- branch: `foundation-v0.1`
- validated_base_commit: `2b8c620eb7827bc286e08d6c8d4e9df63a593801`
- c10_10_package_commit: `pending_until_committed`
- release_policy: record the final C10.10 commit before using this manifest as
  a frozen handoff artifact.

## Kiosky-player Pin

- repository: `dadoohai/kiosky-player`
- ref: `appliance-v0.1`
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`
- install_path: `/opt/totem/kiosky-player`
- policy: install/export this exact tree, excluding `.git`, private config,
  environment files, media cache and secrets.

## Principal Scripts

- `scripts/board/totem_appliance_manifest.json`
- `scripts/board/install_totem_appliance.sh`
- `scripts/board/verify_totem_appliance.sh`
- `scripts/board/totem_private_values_prepare.py`
- `scripts/board/totem_open_settings_session.sh`
- `scripts/board/totem_setup_visual_wizard.py`
- `scripts/board/totem_visual_setup_writer_handoff.py`
- `scripts/board/totem_visual_splash.py`
- `scripts/board/totem_status_aggregate.py`
- `scripts/board/totem_status_render_preview.py`
- `scripts/board/totem_config_contract_validate.py`
- `scripts/board/totem_config_writer_real.py`
- `scripts/remote/run_c10_9_second_board_clean_install.sh`
- `scripts/remote/run_c10_9_1_second_board_provision.sh`

## Units

- `scripts/board/kiosky-player.service`
- `scripts/board/totem-settings-trigger.service`
- `scripts/board/totem-open-settings.service`
- `scripts/board/dadooh-visual-splash.service`

## Runtime Minimo

- `python3`
- `mpv`
- `ffmpeg`
- `python3-requests`
- `NetworkManager`

Runtime install policy:

- explicit packages only;
- `apt-get install --no-install-recommends` when authorized;
- no `apt upgrade`;
- no `apt full-upgrade`;
- no `apt dist-upgrade`;
- no `armbian-upgrade`;
- no desktop, Chromium, Xorg, Wayland or compositor.

## Dados Que Entram

- appliance scripts versionados;
- systemd units versionadas;
- manifest appliance;
- boot visual guardrails;
- public `orientation.json` contract/default;
- sanitized installed manifest;
- pinned `kiosky-player` tree.

## Dados Que Nao Entram

- `/data/config/config.json`;
- API key;
- real API URL;
- real environment identifier;
- station identifier;
- Wi-Fi SSID/password;
- IP, MAC, DNS, gateway or hostname;
- backups;
- raw logs;
- media cache;
- private candidate files;
- private-values files.

## Handoff

Runbook:

- `docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`

Evidence:

- `docs/evidence/candidate-a/runs/20260505T205432Z-c10-10-installable-rc-package/README.md`

Next gate:

- C10.10.2 Shutdown UX.

Not next:

- C11.0 read-only readiness audit before shutdown UX follow-up;
- final image generation;
- root read-only enablement;
- power-cut testing;
- long-run homologation.
