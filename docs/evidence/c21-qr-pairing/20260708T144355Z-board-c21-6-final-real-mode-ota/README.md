# C21.6 Board OTA Evidence - Final QR Auth Real Mode

Date: 2026-07-08T14:43:55Z.

Scope: apply the final homologation `totem-core` package for C21 QR
authentication. The wizard contains the real backend mode behind
`TOTEM_VISUAL_WIZARD_PAIRING_MODE=real`; default behavior remains compatible
with mock/manual paths.

Package:

- Version: `c21.6-qr-auth-real-wizard-final-20260708T144044Z-e97db68`
- Component: `totem-core`
- Channel: `homologation`
- Payload SHA256:
  `fd71a62cd340dcda75bc74f15100e7f80fb76735ba78c11c7bcdb6924d16765e`
- Manifest:
  `releases/core-updates/c21.6-qr-auth-real-wizard-final-20260708T144044Z-e97db68/dadooh-totem-core-c21.6-qr-auth-real-wizard-final-20260708T144044Z-e97db68.manifest.json`

Offline gate:

- `scripts/qa/c18_ota_release_gate.py --package-manifest ... --package-payload ... --json`
- Result: `passed True`, `package_passed True`, `errors []`,
  `totem_core_sandbox True`, `repo_dirty False`.

Board apply:

- Method: governed local OTA, `totem_updatectl.py apply-local --component totem-core`.
- Result: `apply_success`.
- Current after apply:
  `c21.6-qr-auth-real-wizard-final-20260708T144044Z-e97db68`.
- Previous after apply:
  `c21.5-qr-auth-real-wizard-20260708T142824Z-25d2183`.
- Player service after apply: active.
- Settings lock after apply: absent.
- Board wizard self-test after apply: `self-test: ok`.

Non-claims:

- The real QR flow was not exercised against live deployed backend/front in this
  evidence.
- No final production/stable claim is made here.
- No player-runtime thaw claim is made here.
- Publishing/deploying `Habitat/functions` and `homeHabitat` remains the next
  external step before a live end-to-end QR run.
