# C18 target-current startup-status diagnostic - 9bebaf1

Sanitized diagnostic evidence from a service-stopped lab apply retry of
`c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Result:

- `lab-apply.json`: `passed=false`, `rc=10`;
- the target was not promoted;
- candidate health failed only `status_no_failures`;
- the only failing status sample was the first startup sample with
  `playback_state=player_starting` and `black_screen_risk_reason=present`;
- MPV playback itself was healthy: one MPV process, no media load failures,
  no MPV restart, hwdecode present, VO configured and playback progressed.
- `candidate-health/reevaluated-health-summary.json` replays the same samples
  with the corrected candidate-mode rule and passes with no failure reasons.

Interpretation: this is a governed false-positive diagnostic for candidate
startup status, not a target package defect. The follow-up patch makes
candidate mode tolerate this specific startup-only marker while still rejecting
black-screen markers after startup and all real status failures.

Non-claims:

- does not validate the target package as current;
- does not authorize pilot execution by itself;
- does not authorize production, `stable`, auto-pull or public thaw;
- does not satisfy power-loss 17/17 or 24h soak.
