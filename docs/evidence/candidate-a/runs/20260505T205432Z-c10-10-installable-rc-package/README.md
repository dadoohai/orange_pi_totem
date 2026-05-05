# C10.10 Installable Bench RC Package

Timestamp UTC: 2026-05-05T20:54:32Z

## Scope

C10.10 consolidated the validated C10.8/C10.9/C10.9.1 install process into a
bench RC package and runbook. This run did not alter the dev board or the
second board.

## Repository

- branch: `foundation-v0.1`
- head_at_start: `2b8c620eb7827bc286e08d6c8d4e9df63a593801`
- head_title: `Add C10.9.1 second board provisioning`
- working_tree_used_for_c10_10: `uncommitted until human authorizes commit`

## Created

- runbook: `docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`
- private-values helper: `scripts/board/totem_private_values_prepare.py`
- installable RC manifest: `releases/installable-rc/manifest.md`

## Updated

- `scripts/remote/run_c10_9_1_second_board_provision.sh`
- `docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md`
- `docs/product/86_C10_8_INSTALADOR_IDEMPOTENTE_APPLIANCE.md`
- `docs/product/88_C10_9_SEGUNDA_PLACA_INSTALACAO_LIMPA.md`
- `docs/product/89_C10_9_1_SEGUNDA_PLACA_PROVISIONAMENTO_REAL.md`

## Commands

Initial audit:

- `git status --short`
- `git log --oneline -25`
- `git diff --check`
- `bash -n scripts/board/install_totem_appliance.sh`
- `bash -n scripts/board/verify_totem_appliance.sh`
- `bash -n scripts/remote/run_c10_9_second_board_clean_install.sh`
- `bash -n scripts/remote/run_c10_9_1_second_board_provision.sh`
- `python3 -m json.tool scripts/board/totem_appliance_manifest.json`
- `python3 scripts/board/totem_config_contract_validate.py --self-test`

C10.10 local validation:

- `python3 scripts/board/totem_private_values_prepare.py --self-test`
- `bash -n scripts/remote/run_c10_9_1_second_board_provision.sh`
- `python3 scripts/board/totem_visual_setup_writer_handoff.py --self-test`
- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`
- `python3 scripts/board/totem_visual_splash.py --self-test`
- sanitized scan for board addresses, password literals and private values in
  the new/changed C10.10 files

All listed syntax checks and self-tests passed locally.

## Sanitization

- secrets_published: `false`
- config_content_published: `false`
- private_values_published: `false`
- api_key_published: `false`
- api_url_literal_published: `false`
- environment_id_literal_published: `false`
- network_identifiers_published: `false`
- raw_logs_published: `false`
- dev_board_touched: `false`
- second_board_changed: `false`
- writer_called: `false`
- wifi_changed: `false`
- packages_installed: `false`
- broad_upgrade_called: `false`

## Result

- installable_bench_rc: `true`
- ready_for_c11_readiness: `true`
- ready_for_c12_image: `false`
- final_image: `false`
- read_only: `false`
- power_cut_tested: `false`
- long_test: `false`

## Notes

The RC package still depends on temporary Armbian bench bootstrap: initial root
access and network/SSH. C12.0 must remove that manual technical bootstrap from
the final image flow.
