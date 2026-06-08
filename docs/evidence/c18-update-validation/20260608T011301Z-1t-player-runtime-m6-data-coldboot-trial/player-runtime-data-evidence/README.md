{
  "artifact_id": "c18-player-runtime-m6-coldboot-c18.player-runtime-m6-b-20260608T011301Z-m6-ac59f7f-retry1",
  "claims": [
    "local_package_apply",
    "verified_marker_adoption",
    "service_deep_health_after_restart",
    "rollback_to_data_previous",
    "service_deep_health_after_rollback"
  ],
  "component": "player-runtime",
  "non_claims": [
    "public_thaw",
    "github_publish",
    "auto_pull",
    "stable_or_production",
    "power_loss_safety",
    "cold_boot_adoption",
    "server_side_gate",
    "soak_endurance"
  ],
  "scope_note": "This sub-gate covers the player-runtime data segment. Cold-boot adoption is proven by the companion coldboot-data-evidence directory and by the aggregate M6 release gate.",
  "rollback_expectation": "data-previous",
  "schema": "dadooh.c18.player_runtime.trial_readme.v1",
  "scope": "lab-only persistent /data coldboot trial",
  "version": "c18.player-runtime-m6-b-20260608T011301Z-m6-ac59f7f-retry1"
}
