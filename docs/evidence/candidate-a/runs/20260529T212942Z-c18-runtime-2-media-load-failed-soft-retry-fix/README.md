# C18.RUNTIME.2 — media_load_failed Soft-Retry Fix

Correcao em repo do `kiosky-player` para a causa raiz de C18.RUNTIME.1.
Doc tecnico: `docs/product/180_C18_RUNTIME_MEDIA_LOAD_FAILED_SOFT_RETRY_FIX.md`.
Diagnostico de origem: doc 179 + run `20260529T200805Z-c18-runtime-...`.

## Status

c18_runtime_2_status=fixed_in_repo_sim_validated
fix_repo=kiosky-player
fix_commit=7ca6691
fix_branch=appliance-v0.1
root_cause=media_load_failed_ack_timeout_triggers_unneeded_mpv_restart
fix_summary=soft_retry_loadfile_before_mpv_restart

player_code_changed=true
scheduler_changed=false
sync_changed=false
duration_changed=false
watchdog_ping_path_changed=false
new_config_keys=mpv_load_soft_retries(2),mpv_load_soft_retry_delay_sec(0.3)

tests_total=101
tests_passed=101
tests_added=2
regression_media_load_failure_test=passed

board_touched=false
release_published=false
update_pushed_to_client=false
image_built=false
hardware_validation_required=true
ready_for_c18_3_release_package=true

## Pendencias

board_ssh_reachable_during_fix_round=false (porta 22 caiu; confirmacao live adiada)
duration_sec_of_loadfile_errors_captured=false (a confirmar em hardware)
fix_robust_regardless_of_timeout_vs_error=true

## Guardrails

secrets_published=false
api_key_published=false
api_url_published=false
environment_id_published=false
ssid_published=false
wifi_password_published=false
media_urls_published=false
apt_update_executed=false
apt_upgrade_executed=false
pip_install_executed=false
image_built=false
card_written=false
kernel_touched=false
read_only_touched=false
writer_called=false
real_config_written=false
poweroff_executed=false
power_cut_tested=false
c12_readonly_blocked=true
c12_4_blocked=true

## Test commands

- `python3 -m py_compile kiosk.py tests/fakes/player_simulation.py tests/test_player_timing_simulation.py`
- `python3 -m unittest tests.test_player_timing_simulation` (inclui os 2 novos cenarios)
- `python3 -m unittest discover -s tests`  => 101 OK

## Decision

A correcao reduz restarts desnecessarios do MPV (causa provavel da repeticao/
percepcao de tempo incorreto) reenviando `loadfile` antes do restart completo. E
estritamente mais segura e validada em simulacao (101 testes). Permanece em repo:
sem deploy, sem release, sem update remoto. Proximo passo C18.3: empacotar como RC
(junto com C18.2) e **validar em hardware** Orange Pi, capturando `duration_sec`
dos eventos de falha e a queda na taxa de `media_load_failed`. C12/read-only fora
de escopo.
