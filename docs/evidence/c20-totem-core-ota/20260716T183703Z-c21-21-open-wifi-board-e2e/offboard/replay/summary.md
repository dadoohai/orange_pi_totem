# C17.8.1 wizard input replay

implemented=true
scenario_count=11
assertions_passed=true
operator_confusion_risk=low

| scenario | assertion | result | detail |
| --- | --- | --- | --- |
| happy_path_synthetic | valid_uuid_passes_local_validation | pass |  |
| happy_path_synthetic | writer_not_called | pass |  |
| back_navigation | esc_returns_to_previous_screen | pass |  |
| back_navigation | no_save_on_back | pass |  |
| step_focus_pending_review | partial_state_cannot_commit | pass |  |
| step_focus_pending_review | first_pending_is_connection | pass |  |
| step_focus_pending_review | review_status_blocked | pass |  |
| step_focus_pending_review | candidate_not_generated_for_partial_state | pass |  |
| environment_invalid_uuid | invalid_uuid_blocks_advance | pass |  |
| environment_invalid_uuid | writer_not_called | pass |  |
| environment_edit_middle | middle_edit_reaches_valid_uuid | pass |  |
| environment_edit_middle | cursor_editing_supported | pass |  |
| wifi_success_fake | password_value_not_rendered | pass |  |
| wifi_success_fake | progress_is_visible | pass |  |
| wifi_success_fake | success_is_visible | pass |  |
| wifi_success_fake | wifi_result_reaches_environment | pass |  |
| wifi_success_fake | wifi_result_reaches_review | pass |  |
| wifi_success_fake | wifi_result_reaches_completion | pass |  |
| wifi_success_fake | networkmanager_not_called_by_replay | pass |  |
| wifi_wrong_password_fake | password_value_not_rendered | pass |  |
| wifi_wrong_password_fake | retry_path_available | pass |  |
| wifi_open_retry_fake | open_network_is_selectable | pass |  |
| wifi_open_retry_fake | open_network_skips_password | pass |  |
| wifi_open_retry_fake | open_progress_is_truthful | pass |  |
| wifi_open_retry_fake | open_failure_retries_directly | pass |  |
| wifi_open_retry_fake | open_success_claims_link_not_internet | pass |  |
| wifi_open_retry_fake | open_result_reaches_completion | pass |  |
| wifi_open_retry_fake | networkmanager_not_called_by_replay | pass |  |
| api_unavailable_fake | api_unavailable_requires_confirmation | pass |  |
| api_unavailable_fake | operator_confirmation_recorded | pass |  |
| reopen_configured | reopens_directly_on_review | pass |  |
| reopen_configured | existing_configuration_can_commit | pass |  |
| reopen_configured | environment_is_retained_without_remote_preflight | pass |  |
| reopen_configured | backend_not_called_for_retained_environment | pass |  |
| reopen_configured | network_not_changed | pass |  |
| reopen_configured | wifi_probe_is_reported | pass |  |
| cancel_flow | esc_cancels_without_writer | pass |  |
| cancel_flow | real_config_not_written | pass |  |
