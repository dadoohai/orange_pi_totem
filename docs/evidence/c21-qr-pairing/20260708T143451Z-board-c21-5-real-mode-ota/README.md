# C21.5 Board OTA Evidence - QR Auth Real Mode

Date: 2026-07-08T14:34:51Z.

Scope: apply the homologation `totem-core` package with the C21 wizard real
pairing mode available behind `TOTEM_VISUAL_WIZARD_PAIRING_MODE=real`.

Package:

- Version: `c21.5-qr-auth-real-wizard-20260708T142824Z-25d2183`
- Component: `totem-core`
- Channel: `homologation`
- Payload SHA256:
  `59b0190a982acffd60e8cdccf5003a125b5b53de332905ef90c0c9d2a5b95eb6`
- Manifest:
  `releases/core-updates/c21.5-qr-auth-real-wizard-20260708T142824Z-25d2183/dadooh-totem-core-c21.5-qr-auth-real-wizard-20260708T142824Z-25d2183.manifest.json`

Offline gate:

- `scripts/qa/c18_ota_release_gate.py --package-manifest ... --package-payload ... --json`
- Result: passed=true on clean repo at HEAD `4719246`.

Board apply:

- Method: governed local OTA, `totem_updatectl.py apply-local --component totem-core`.
- Result: `apply_success`.
- Current after apply:
  `c21.5-qr-auth-real-wizard-20260708T142824Z-25d2183`.
- Previous after apply:
  `c21.2-qr-pairing-wizard-ota-compatible-20260708T134735Z-20f7b20`.
- Player service after apply: active.
- Settings lock after apply: absent.
- Board wizard self-test after apply: `self-test: ok`.

Non-claims:

- The real QR flow was not exercised against the live backend in this evidence.
- No final production/stable claim is made here.
- No player-runtime thaw claim is made here.
- The mode remains opt-in by environment flag; default wizard behavior remains
  mock/manual compatible.
