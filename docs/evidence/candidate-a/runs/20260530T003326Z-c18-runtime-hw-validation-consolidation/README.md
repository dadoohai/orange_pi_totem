# C18.RUNTIME — Hardware Validation Consolidation

Campanha de validacao em hardware (Orange Pi Zero 3 / H618, imagem C17.4.2) dos
fixes de runtime do `kiosky-player`. Sanitizado. Doc tecnico: `docs/product/182_*`.

## Status

c18_runtime_consolidation_status=paused_for_team_decision
board_accessed_via_ssh=true
board_image_version=c17.4.2
board_host=redacted
board_left_clean=true
board_restored_to_original=true (running /opt 307d986)

## Root cause (confirmed on hardware)

root_cause=software_decode_loadfile_init_blocks_mpv_ipc
hwdec_current=no
video=h264_576x1024_30fps_~892kbps
mpv_steady_cpu_pct=~54 (1 of 4 A53 cores) ; frame_drop_count=0
mechanism=fresh_loadfile_init_pegs_mpv_main_thread_>8s -> ipc_unread -> sendall_timeout -> media_load_failed -> restart
failing_op=sendall (MPV IPC command send failed command=loadfile error=timed out)
restart_reload_offset=0 (target item; NOT a playlist-level repeat)
visible_effect=current_item_lingers_2_to_8s + brief_flash_on_restart (~1-2 per ~17min)

## Fixes attempted (all refuted on hardware)

soft_retry_resend_loadfile=refuted (0 recoveries; restart fired; +~4.6s linger)
loadfile_recv_timeout_8s=refuted (failure is on SEND not recv; duration stayed 2.0s)
loadfile_send_timeout_8s=refuted (sendall blocked full 8.0s and still failed; stall > 8s)
conclusion=player_ipc_timeout_layer_cannot_fix_software_decode_init_cost

## Per-round evidence

R3_softretry_hw=media_load_failed_restarts=1 slow_ack_recovered=0 (negative)
R5_stall_probe=not_io (io_max_kbps=0, no D-state); main thread busy
R7_thread_probe=mpv_main_thread_99pct_cpu_during_stall
R8_sendtimeout_hw=send_failed_durations=[2.001,2.002,8.007,8.008] restarts=1 (>8s stall confirmed)
decode_query=hwdec-current=no (software h264)

## Disposition

kiosky_player_soft_retry_reverted=true (commit e76204a; back to C18.2 baseline d4e4c4e)
kiosky_player_runtime_fix_shipped=false
correct_fix_direction=enable_hw_decode (kernel V4L2/cedrus + mpv hwdec) OR accept_restart
correct_fix_layer=image_bsp_decode (NOT kiosky-player)
next_decision=team

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
ssh_password_persisted=false
board_temp_instrumentation_cleaned=true

## Decision

A duracao esta OK (179). A causa raiz da percepcao de "repeticao/loop" e o custo
de init do **software decode** do MPV no H618, que bloqueia o IPC por >8s e gera
`media_load_failed`/restart — nao corrigivel por timeout/retry no player (3
tentativas refutadas). Soft-retry revertido. O fix correto (habilitar HW decode,
nivel imagem/BSP, ou aceitar o restart) e decisao de equipe. Rodada pausada.
C12/read-only intocado.
