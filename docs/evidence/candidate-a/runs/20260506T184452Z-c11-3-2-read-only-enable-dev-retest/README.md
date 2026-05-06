# C11.3.2 - Read-only Enable Dev Retest

Data: 2026-05-06

## Escopo

Reteste controlado na placa dev depois da recuperacao offline. A placa foi
alimentada por fonte dedicada; a placa teste nao foi tocada.

## Resultado

- previous_failure_confounded_by_power_source=true
- power_source_for_retest=dedicated_psu
- tv_usb_power=false
- rollback_after_offline_recovery=true
- enable_executed=true
- reboot_executed=true
- ssh_returned=true
- read_only_enabled=false
- overlay_active=false
- root_write_blocked=false
- writable_paths_ok=true
- rollback_after_retest=true
- f10_cancel_result=not_run_overlay_not_enabled
- service_final=active/enabled
- public_state=player_running
- playback=playing
- NRestarts=0
- systemctl_failed_count=0
- kernel_critical_filter_count=not_published_raw_logs

## Classificacao

A falha anterior fica classificada como `POWER_SUPPLY_CONFOUNDED`, porque a
placa estava alimentada pela USB da TV e a TV desligou.

O reteste com fonte dedicada separou esse fator: o SSH voltou e o player ficou
operacional, mas o mecanismo `overlayroot` nao ativou. Classificacao do reteste:
`OVERLAYROOT_ENABLE_DID_NOT_ACTIVATE`.

## Guardrails

- poweroff_executed=false
- power_cut_tested=false
- test_board_touched=false
- writer_called=false
- real_config_read=false
- real_config_written=false
- wifi_changed=false
- networkmanager_profiles_changed=false
- packages_installed=false
- raw_logs_published=false
- secrets_published=false

## Decisao

C11.3.2 permanece bloqueado. Nao iniciar C11.4. O enablement de read-only deve
migrar para uma abordagem nova: imagem/base C12, teste em cartao separado ou
mecanismo oficial validado fora da placa de produto.
