# Transition inventory

| transition_id | feedback | dead_moment_risk | preview | future_test |
| --- | --- | --- | --- | --- |
| transition.power_on_to_first_feedback | splash.boot | medium | yes | hdmi_capture_or_camera |
| transition.boot_preparing_to_player | splash.player | low | yes | hdmi_capture_or_camera_for_final_perception |
| transition.no_config_to_config_pending | splash.config_pending | low | yes | none |
| transition.f10_to_setup_splash | splash.setup | low | yes | hdmi_capture_or_camera_for_flicker |
| transition.setup_splash_to_wizard | wizard.orientation.landscape | low | yes | hdmi_capture_or_camera_for_flicker |
| transition.wizard_to_saving | splash.saving | low | yes | none |
| transition.saving_to_player | splash.player | medium | yes | hdmi_capture_or_camera |
| transition.player_waiting_for_media_cache_api | status_renderer_or_player_state | medium | no | runtime_or_hdmi_capture |
| transition.player_failure_fallback | future_error_state | medium | no | future_player_error_fixture |
