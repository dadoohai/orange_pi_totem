# C18 H2 readiness - business exception

Status: H2 gate green by explicit business exception.

The H2 gate passed for target
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` after the failed
HDMI-event soak was accepted through the separate soak exception artifact.

This snapshot preserves the distinction between a clean endurance soak and an
accepted exception:

- `soak_endurance_24h.passed=true` because the exception gate passed;
- `soak_endurance_24h.clean_soak_passed=false`;
- `soak_endurance_24h.accepted_by_exception=true`;
- `soak_endurance_24h.original_clean_blockers=["soak_not_passed"]`.

Non-claims:

- this snapshot does not claim the HDMI-event soak was clean;
- this snapshot does not publish releases;
- this snapshot does not enable auto-pull;
- this snapshot does not execute public thaw;
- this snapshot does not mutate board state.
