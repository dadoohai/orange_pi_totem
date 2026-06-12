# C18 P0 rollback_current_to_previous power-loss evidence

Physical power-loss checkpoint evidence for the C18 player-runtime homologation
pilot P0 matrix.

Scope:

- checkpoint: `rollback_after_current_to_previous`
- target candidate: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- expected active runtime after reboot: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`
- checkpoint boot id: `21333b78-0137-43b5-b2a8-464466555e37`
- resume boot id: `e29cfb55-a1d3-460b-8605-561c51359a9d`

Outcome:

- assisted apply of the target candidate passed
- service adoption and short playback health passed before arming rollback
- physical power-loss was performed after `rollback_after_current_to_previous`
- resume playback health passed before and after reconcile
- public player-runtime apply, rollback, and reconcile remained frozen

Non-claims:

- no production readiness
- no stable promotion
- no auto-pull
- no public thaw
- no 24h soak
- no full 17/17 power-loss matrix
