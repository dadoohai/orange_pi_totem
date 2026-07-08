# C17.8.1 wizard input replay

implemented=true
scenario_count=1
assertions_passed=true
operator_confusion_risk=low

| scenario | assertion | result | detail |
| --- | --- | --- | --- |
| step_menu_pending_review | partial_state_cannot_commit | pass |  |
| step_menu_pending_review | first_pending_is_connection | pass |  |
| step_menu_pending_review | review_status_blocked | pass |  |
| step_menu_pending_review | candidate_not_generated_for_partial_state | pass |  |
