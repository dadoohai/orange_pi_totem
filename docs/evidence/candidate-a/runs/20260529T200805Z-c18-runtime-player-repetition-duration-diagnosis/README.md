# C18.RUNTIME.1 — Player Repetition & Duration Diagnosis (C17.4.2 board)

Diagnostico orientado a evidencia, sanitizado. Sem release, sem update remoto,
sem imagem, sem writer, sem alteracao de config real, sem poweroff/corte seco.
Doc tecnico: `docs/product/179_C18_RUNTIME_PLAYER_REPETITION_DURATION_DIAGNOSIS.md`.
Artefatos: `board_audit_summary.md`, `api_probe_summary.md`,
`runtime_monitor_summary.md`.

## Status

c18_runtime_status=diagnostic_only
board_accessed_via_ssh=true
board_image_version=c17.4.2
board_host=redacted
board_player_source=/opt
board_player_version=307d986 (C18.1; /opt baked, mtime 2026-05-14)
board_player_staged_inactive=c71318a (/data/apps/.../current, nao executa)
board_player_matches_local_head=false
board_has_c18_2_duration_fix=false

## API probe

api_probe_executed=true
api_payload_raw_published=false
api_duration_fields_mapped=true
media_urls_published=false
api_endpoint_kind=search
api_method=POST
api_units_count=1
api_campaigns_active=7
api_media_items_count=7
api_duplicates=false
api_single_item_playlist=false

api_returns_exposure_time_ms_count=7
api_returns_exposureTimeMs_count=0
api_returns_exposureTimeSeconds_count=0
api_returns_duration_count=0
missing_duration_count=0
api_duration_min_ms=3900
api_duration_max_ms=28100

## Duration verdict

duration_issue_cause=api_returns_only_exposure_time_ms_and_player_uses_it_correctly
player_uses_api_duration=true
player_uses_default_duration=false
default_duration_overrides_api=false
duration_source_available_on_board=false (pre-C18.2; campo unico torna a fonte inequivoca)
c18_2_would_change_current_behavior=false

## Repeat verdict

repeat_issue_cause=media_load_failure_retries_previous
repeat_secondary_contributor=mpv_loop_file_inf_repeats_short_video (politica documentada; pouco ativa no conteudo atual)
mpv_loop_policy_status=loop_file_inf_present
mpv_loop_file_inf=true
mpv_loop_playlist=false
short_video_repeat_policy_relevant=true
short_video_actually_looping_now=false (clip_s ~= exposure_time_ms; loops=0)

mpv_restarts_since_service_start=11
mpv_restart_reason=media_load_failed (100%)
mpv_restart_assets=all_7_intermittent (nao asset unico)
mpv_block_cooldown_events=0
mpv_orphan_processes=0

## Sync

sync_status=enabled_stable
sync_enabled=true
sync_tick_seen=false (checkpoint 3600s; nenhum na janela)
resync_seen=false
resync_reloaded_same_item=false
sync_related_to_repeat=false
chrony_offset=sub_ms (drift < threshold 300ms => acao none)

## Runtime monitor

runtime_monitor_executed=true
runtime_monitor_duration_sec=900
runtime_monitor_samples=450
items_seen_count=88 (journal play events; ~11 ciclos)
unique_items_seen_count=7
repeated_same_item_sequences=0
expected_vs_observed_mismatches=0
index_monotonic_wrap=true
max_gap_between_plays_sec=29 (== item de 28,1s; sem stall)
monitor_tail_artifact=stale_ipc_socket_after_mpv_restart (falso loop; refutado pelo journal)

## Next

ready_for_c18_runtime_fix=true (alvo: media_load_failed / verificacao de carga / grace do watchdog)
ready_for_kiosky_player_release_candidate=false (fix da repeticao nao implementado; C18.2 e RC separado de forward-compat, nao resolve a repeticao)
c18_2_packageable_as_independent_rc=true
hardware_validation_required=true

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

## Guardrails (runtime extras)

kiosky_player_restarted=false
board_full_reboot=false
config_read_internally_only=true (nunca impresso)
mpv_ipc_read_only=true (somente get_property)
api_calls_made=1 (search, read-only, identico ao poll do player)
board_temp_scripts_cleaned=true (/tmp/dadooh_*, /data/state/totem-debug/c18-runtime)
ssh_password_persisted=false

## Decision

Nao ha bug de duracao neste ambiente: a API search retorna apenas
`exposure_time_ms` (canonico) e o player o honra exatamente (duracoes batem 1:1).
C18.2 nao altera o comportamento atual. A playlist avanca de forma previsivel; nao
ha sync/resync, API duplicada, playlist de 1 item, cache offline nem scheduler
travado. A repeticao/percepcao de tempo incorreto e melhor explicada por
**`media_load_failed` -> reinicio do MPV pelo watchdog -> recarga do item
corrente** (11x em ~89 min, todos os assets, sem orfaos, sem bloqueio). O proximo
passo e um **novo fix de runtime** (tolerancia de carga/grace do watchdog e/ou
retomada com offset), validado em hardware. C18.2 pode ser empacotado em paralelo
como RC de forward-compat/observabilidade, mas nao como "fix da repeticao".
C12/read-only permanece bloqueado e fora de escopo.

## Test/probe commands (locais e na placa)

- local: `python3 -m py_compile kiosk.py` ; `python3 -m unittest discover -s tests` (99 OK)
- local: `git show c71318a:kiosk.py | sha256sum` (match board /data/apps staged)
- placa (sanitizado): board audit read-only; `/tmp/dadooh_player_api_probe.py`
  (importa `kiosk.load_config`, 1 chamada search); `/tmp/dadooh_player_runtime_monitor.py`
  (MPV IPC get_property + journalctl), 900s.
