# C12.3.1 Firstboot + Open Settings Session Reliability

Data: 2026-05-07

## Escopo

- Placa dev tocada: `false`.
- Placa teste tocada nesta rodada: `false`.
- Reboot/poweroff executado: `false`.
- Writer chamado: `false`.
- Config real lida/escrita: `false`.
- Wi-Fi/NetworkManager alterado: `false`.
- Secrets publicados: `false`.

## Classificacao do bloqueio C12.3

- primary_classification: `open_settings_session_stale`
- secondary_classification: `firstboot_interference`
- possible_classification: `tty_input_device_issue`
- human_observed: `wizard_input_freeze`
- framebuffer_render_freeze_confirmed: `false`
- image_lab_read_only_validated: `false`
- image_lab_read_only_state_observed: `IMAGE_LAB_READ_ONLY_NOT_ACTIVE`

## Correcoes aplicadas no repo

- open_settings_exec_stop_post_cleanup: `true`
- open_settings_timeout_for_interactive_session: `7200s`
- stale_session_lock_auto_cleanup_in_trigger: `true`
- cleanup_restores_player_or_config_pending_visual: `true`
- firstboot_gate_added: `true`
- firstboot_autoconfig_private_template_added: `true`
- read_only_assertion_required_for_next_validation: `true`

## Politica de firstboot

A proxima imagem-lab nao deve iniciar validacao F10/wizard enquanto
`/root/.not_logged_in_yet` existir. O gate `totem-firstboot-gate.service`
bloqueia os servicos de produto ate o first-login tecnico terminar. Para bancada,
o build pode receber um `firstboot.conf` privado via `C12_LAB_FIRSTBOOT_CONF`;
esse arquivo deve ficar fora do Git e nao pode conter placeholders.

## Proximo passo

- rebuild_image_lab: `C12.1.2`
- reflash_card: `C12.2.1`
- revalidate_boot: `C12.3.2`
- ready_for_c12_4: `false`
