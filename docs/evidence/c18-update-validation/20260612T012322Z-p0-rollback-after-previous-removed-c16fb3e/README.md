# C18 P0 rollback_after_previous_removed power-loss evidence

Physical power-loss checkpoint evidence for the C18 player-runtime homologation
pilot P0 matrix.

Scope:

- checkpoint: `rollback_after_previous_removed`
- target candidate: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- expected active runtime after reboot: `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b`
- checkpoint boot id: `e29cfb55-a1d3-460b-8605-561c51359a9d`
- resume boot id: `41baeb86-6ee7-4a71-9ae0-d52752025858`

Outcome:

- assisted apply of the target candidate passed
- service adoption and short playback health passed before arming rollback
- physical power-loss was performed after `previous` was removed
- resume playback health passed before and after reconcile
- public player-runtime apply, rollback, and reconcile remained frozen

Non-claims:

- no production readiness
- no stable promotion
- no auto-pull
- no public thaw
- no 24h soak
- no full 17/17 power-loss matrix
