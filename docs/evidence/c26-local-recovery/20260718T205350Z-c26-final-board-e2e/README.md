# C26 final board E2E

Date: 2026-07-18

Scope: final functional campaign of C26.5 on the `prod16` C26 board, with the
real `totem-core` package installed by the governed updater.

Target:

- current: `c26.5-local-recovery-20260718-f1d0da9-actions`;
- previous: `c26.4-local-recovery-20260718-3351084-actions`;
- stable policy restored, timer enabled and player active at the end;
- C26.5 payload SHA256:
  `b8864cc913f6e7ca4562a0e3edfe9eb0ba55a6aef5019a47a0535397ba26f4df`.

## Decisive results

1. An offline reset was started with both IPv4 and IPv6 blackholed. Before the
   physical cut, local cleanup was complete, the old configuration was no
   longer playable, revocation was pending, the credential was retained only
   for retry, and the OTA guard denied mutation.
2. After power returned, firstboot resumed operation
   `826ead88-92c2-4485-b310-4f84acc85c10`. The authoritative backend row is
   unique, linked to both token and activation, and records `revoked` with
   HTTP 200. The old token changed from HTTP 200 to 403 and remained 403 after
   the next activation.
3. The newly activated token returned HTTP 200. The liveness probe timed out
   only because no second reset was requested; it did not persist credentials
   in the public evidence.
4. Governed rollback to C26.4 and reapply of C26.5 were executed before the
   terminal-action tests. Final updater state records C26.5 current, C26.4
   previous, stable policy and a successful apply. Config and player survived.
5. `Desligar` was selected in the real wizard UI. The board powered off and
   returned only after physical power was restored. `Reiniciar` was selected
   through the same UI and returned automatically with a new boot ID.
6. Config, settings context and update-policy hashes were identical before and
   after restart. The final 56-sample deep-health run passed with 56 expected
   HW-decode samples, zero player restarts and zero media-load failures.

## Health nuance

The first 45-second post-poweroff observation is intentionally retained as a
negative result: every sample used expected HW decode and there were no
restarts or load failures, but the terminal sample landed at
`preparing_first_frame`. The immediate repeat reached `playing` and passed
with 51 samples. This is not rewritten as a first-pass green.

## Interaction boundary

The terminal-action screens are real framebuffer captures from the installed
wizard. The settings session was started through its systemd service because
the temporary virtual F10 device was not enumerated by the already running
trigger. Navigation and confirmation were injected into `tty2`. Physical F10
hold, session opening and safe return to playback were already proven in C19;
this directory proves the C26 action screens and their effects, not a new F10
trigger test.

## Layout

- `board/offline-precut/`: reset state immediately before physical power cut;
- `backend/`: sanitized authoritative revocation row;
- `token-liveness/`: status-only old/new token probes;
- `board/poweroff-ui/`: poweroff menu and confirmation captures;
- `board/post-poweroff/`: state and health after manual power return;
- `board/restart-ui/`: restart menu and confirmation captures;
- `board/post-restart/`: state and health after automatic restart.

No API key, token value, password, SSID or customer payload is included.

## Non-claims

- this is not proof that the `prod17` image was flashed;
- it does not add a local full-system reinstall or A/B recovery;
- it does not promote the homologation package or change public rollout;
- it does not claim the temporary virtual input device as a physical F10 event.

