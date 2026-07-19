# C26 reset preservation audit

Independent read-only audit, 2026-07-19.

## Verdict

GO without another destructive board reset. No functional defect was found in
the reset write boundary.

The physical prod19 campaign did not itself exercise a saved Wi-Fi profile or
a non-default orientation. Those two cases remain explicit physical
non-claims. The supported claim is compositional: `Restaurar` cannot reach the
NetworkManager profile directory and preserves the public orientation file.

## Verified boundary

- production reset accepts only `/data` as its data root;
- the fixed mutation allowlist is limited to config, player media, player
  state, player spool and player logs;
- `/etc/NetworkManager/system-connections` is outside that root;
- `/data/state/totem-display/orientation.json` is outside every reset domain;
- the reset flow does not invoke a NetworkManager mutation;
- after private settings are removed, the wizard recovers its initial rotation
  from the preserved public orientation contract.

## Coverage finding

The existing embedded writer self-test used a generic Wi-Fi sentinel and an
obsolete orientation path, and checked only existence. This was a low-severity
test gap, not a production boundary defect.

The follow-up regression test now exercises the real orientation path at 270
degrees and an external NetworkManager-profile boundary. It requires exact
bytes, SHA-256 and modes to survive the normal reset and every interruption
phase through resume, finalization, onboarding completion and bounded GC. It
also verifies that the wizard reads 270 degrees from the preserved public
contract.

Evidence: `gates/reset-preservation-regression.log`.

## Claim limit

Do not state that prod19 physically proved reset while associated through
Wi-Fi or with a non-default orientation. A future physical run may add that
stronger claim, but it is not required to close the deterministic C26 reset
boundary.
