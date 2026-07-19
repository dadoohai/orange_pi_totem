# C26 prod19 final board E2E

Date: 2026-07-19

Scope: physical acceptance campaign of the exact `prod19` image on the real
Orange Pi board. The campaign covers clean boot, onboarding, playback, the
single `F10` flow, restart, interrupted restore, exact activation revocation,
reactivation, governed `totem-core` roundtrip and safe poweroff.

Target:

- image: `c18-hwdecode-prod-19-c26` / `c18.image-prod.19-c26`;
- image SHA256:
  `991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`;
- embedded current: `c26.16-local-recovery-20260719-5df9521-final-guarded-actions`;
- embedded previous: `c26.15-local-recovery-20260719-a09bf39-guarded-transaction-actions`;
- state after public auto-pull: C26.17 current, C26.16 previous;
- repo HEAD used by the image composition: `5838983`.

## Observed results

1. A clean image boot exposed both compatible C26 slots, no product config,
   the production policies and both timers. All 14 installed self-test groups
   passed.
2. The kernel input path for a held `F10` opened the installed wizard. The
   same flow exposed `Reiniciar`, `Desligar` and `Restaurar para configuracao
   inicial`; every destructive confirmation started on `Cancelar`.
3. `Reiniciar` produced a new boot and preserved config, settings context,
   display orientation and update policy. The post-restart deep-health run
   passed with 38 samples, no restart and no media-load failure.
4. Restore was started with the API routes blackholed. Before the physical
   cut, operation `9766fc98-346e-460b-bf1d-0ecc4751391e` was
   `local_complete`, the old config was unavailable, the old credential was
   retained only for retry and a real rollback was deferred with `rc=40`.
5. Power returned with a different boot ID. Firstboot resumed the same
   operation, obtained a `revoked` receipt and returned to onboarding. The
   authoritative backend has exactly one row linked to token and activation,
   with HTTP 200. The old token changed from HTTP 200 to 403.
6. A new activation returned HTTP 200. The old token remained 403 after the
   new activation and after the final boot. The post-reactivation deep-health
   run passed with 58 samples, six aliases, expected hardware decode and zero
   restart/load failure.
7. Governed rollback changed C26.16 to C26.15 and a second governed rollback
   returned to C26.16. Config, settings, orientation, policy and playback were
   preserved. Both commands returned zero.
8. `Desligar` first proved the default cancel path without state mutation.
   The confirmed action then took the board offline and it stayed offline
   until power was restored manually. The next boot had a new boot ID, no
   stale terminal-action unit or reset state, and exact pre-poweroff hashes.
9. Final deep health passed with 60/60 expected `v4l2request-copy` samples,
   four content aliases, advancing playback, zero media-load failures, zero
   MPV/service restarts and no kernel/storage fault.
10. The final repository release gate passed 85/85. The C26 contract suite
    passed 19/19 at that checkpoint and 20/20 after the preservation assertion
    was added.
11. A separate closeout replay bound held `F10` to the real kernel input
    trigger, proved Enter-on-Cancel for restart and restore, Escape from the
    restore confirmation, repeated Enter safety and updater denial with
    `rc=40` throughout the active settings session.
12. The deployed Firebase source generation was downloaded without exposing
    credentials. Its 296 deployable source files match backend commit
    `cd131f00` exactly, except the explicitly ignored local test server; all 448
    generated `lib/` files match a fresh SWC build. The focused backend suite
    passed 48/48.
13. A stable-only source branch generated C26.17 from commit `0e02019a` without
    changing the executable C26.16 payload tree. The publisher reran the full
    release gate (84/84), validated six bound assets and published the exact
    tag as public stable/latest.
14. Before publication, the exact C26.17 package completed local apply,
    rollback to C26.16 and reapply on this board. Config, display orientation
    and update policy hashes remained unchanged; every phase kept the player
    active with zero service restart.
15. All six public GitHub assets were downloaded and matched local SHA256
    values. The public tag targets `0e02019a` exactly. The old prod15 selector
    rejected C26.17 as unsupported without mutation and selected retained
    C21.24 instead.
16. The production service selected C26.17 from GitHub, downloaded payload
    SHA256 `0bbd935f...`, applied it after a governed rollback to C26.16 and
    then completed a second public lookup as `apply_noop_already_current`.
    The production auto-pull evidence gate passed.
17. Post-public-apply deep health passed with 25 samples, three content
    transitions, expected `v4l2request-copy`, advancing playback, zero restart,
    zero load failure and no kernel/storage fault.
18. After a clean reboot, the production timer fired naturally at
    `2026-07-19T21:01:09Z`. Its service selected the exact public C26.17 tag,
    completed `apply_noop_already_current` three seconds later and left C26.17
    current, C26.16 previous, the player active and the system healthy. The
    hardened evidence gate correlated the timer and service timestamps and
    passed.
19. With that hardening committed, the full release gate passed 85/85 again
    on clean HEAD `f4e5233`, with no failed step.
20. Two independent read-only closeout reviews returned GO on clean
    `ea235fe`; one of them independently reran the full gate at 85/85 on that
    exact HEAD. No technical or documentary blocker remained.

## Evidence layout

- `build/`: immutable offline build, image identity, semantic gates and the
  pre-flash image audit;
- `gates/`: final repository release gate and C26 contract run;
- `board/initial/`: clean image identity and initial runtime state;
- `board/self-tests/`: installed test groups executed on the board;
- `board/ui/`: real framebuffer captures without pairing credentials;
- `board/restart/`: restart state and playback health;
- `board/reset/`: offline pre-cut state, resumed state, reactivation and
  playback health;
- `board/roundtrip/`: C26.16 -> C26.15 -> C26.16 governed updater evidence;
- `board/poweroff/`: cancel path, physical shutdown and final boot health;
- `board/closeout/`: real F10 trigger, cancellation/repeated-input proofs,
  live firstboot contract, active-session updater guard and timer observation;
- `board/stable-alignment-final/`: exact stable apply/rollback/reapply, public
  release verification, production-service remote apply/no-op, operational gate
  and final playback health, followed by a naturally fired timer and its
  timestamp-correlated gate;
- `compatibility/`: old-updater fail-closed rejection and retained C21.24
  selection;
- `backend/` and `token-liveness/`: sanitized revocation and HTTP-status-only
  evidence, backend unit tests and deployed-source provenance;
- `audits/`: independent completion reviews added after evidence freeze.

## Boundaries

- The temporary QA keyboard was enumerated by the real input trigger and held
  `F10`; it is not represented as a human keypress.
- Framebuffer captures prove wizard/status surfaces. MPV uses a DRM plane, so
  actual media playback is proved by the public deep-health samples rather
  than by a framebuffer image.
- C26.15, C26.16 and C26.17 have distinct package identities but identical
  executable payloads. Their roundtrips prove updater/publication mechanics and
  a compatible recovery slot, not behaviorally different application versions.
- `build/artifact-ready.json` remains the immutable pre-flash production
  sidecar and therefore says `ready_for_manual_card_flash=false`. Physical
  acceptance is recorded here; the build record is not rewritten after use.
- The initial deep-health invocation is retained as a negative. It failed only
  `service_process_unfiltered`; its 40 playback samples otherwise used expected
  hardware decode with zero restart, load, kernel or storage error. Canonical
  post-restart, post-reactivation and final invocations passed.
- A later 60-second health window is also retained as negative. Five complete
  episodes progressed, but two one-sample transition-boundary episodes made the
  strict summary fail. The immediate retry and post-public-apply health passed;
  the raw negative is not rewritten or discarded.
- The first post-publication timer harness is retained as a negative tooling
  result: it parsed the boot ID before it was available and was interrupted
  after reboot. The subsequent collection used the actual systemd trigger and
  passed. The earlier uncorrelated green timer artifact is preserved but
  superseded by the explicit rejection in `12b` and the correlated pass in
  `16`.
- This campaign publishes only C26.17 for prod19-capable `totem-core` clients.
  It does not change `player-runtime`, add full-system reinstall/A-B recovery or
  authorize future releases by inference.

## Final disposition

The original timer run found public C21.24 older than embedded C26.16 and
rejected it without mutation (`rc=45`). C26.17 resolves that alignment. The
same production unit subsequently downloaded/applied C26.17 and completed a
public no-op; system state returned to `running`, the operational gate passed
and playback remained healthy. A later clean reboot let the enabled production
timer fire naturally. Its exact C26.17 selection and no-op occurred within
three seconds of `LastTriggerUSec`; the hardened gate rejects an old timer
combined with a later manual service and accepted this correlated run.

Repository freeze and both independent re-audits are complete. The campaign
is closed for the claims and boundaries stated here; no further board or HDMI
work is required for C26.

No API key, token value, password, SSID, pairing code, QR payload or customer
identifier is included.
