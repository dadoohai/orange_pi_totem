# C17.8.1 wizard input replay

implemented=true
scenario_count=7
assertions_passed=true
operator_confusion_risk=low

| scenario | assertion | result | detail |
| --- | --- | --- | --- |
| happy_path_synthetic | valid_uuid_passes_local_validation | pass |  |
| happy_path_synthetic | writer_not_called | pass |  |
| back_navigation | esc_returns_to_previous_screen | pass |  |
| back_navigation | no_save_on_back | pass |  |
| environment_invalid_uuid | invalid_uuid_blocks_advance | pass |  |
| environment_invalid_uuid | writer_not_called | pass |  |
| environment_edit_middle | middle_edit_reaches_valid_uuid | pass |  |
| environment_edit_middle | cursor_editing_supported | pass |  |
| wifi_wrong_password_fake | password_value_not_rendered | pass |  |
| wifi_wrong_password_fake | retry_path_available | pass |  |
| api_unavailable_fake | api_unavailable_requires_confirmation | pass |  |
| api_unavailable_fake | operator_confirmation_recorded | pass |  |
| cancel_flow | esc_cancels_without_writer | pass |  |
| cancel_flow | real_config_not_written | pass |  |
