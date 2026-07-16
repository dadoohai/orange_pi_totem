# Independent focused code audit

Initial verdict: **BLOCKER**, subject to full execution-path review.

## Finding

The wizard uses a fixed temporary Wi-Fi secrets path:
`/tmp/dadooh-c9-9-visual-wifi-secrets/secrets.json`. If two privileged callers
launch the Python wizard directly at the same time, they could overwrite or
remove each other's temporary credentials.

## Positive checks

- Connection choices are derived from current runtime probes.
- Protected Wi-Fi follows list, password/apply, then success or recoverable
  failure.
- Retry retains the selected network and password in process memory.
- Open networks do not enter an impossible password path.
- Password reveal is limited to the real framebuffer; saved visual artifacts
  remain masked.
- Public Wi-Fi metadata excludes SSID and password.
- The transactional C21.19 snapshot and rollback behavior is preserved.

## Scope requiring tie-break

This audit intentionally reviewed the wizard files in isolation. It did not
include the production launcher, systemd service and outer settings-session
lock. The finding must therefore be classified against the complete supported
execution path before it can block the product closure.
