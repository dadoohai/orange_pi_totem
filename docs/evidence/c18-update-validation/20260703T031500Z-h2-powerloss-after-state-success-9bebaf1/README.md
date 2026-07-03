# C18 H2 power-loss checkpoint: after_state_success

Physical power was cut after the player-runtime apply operation wrote successful state for `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.

Scope: this evidence covers only the named H2 power-loss checkpoint. It is not a stable, production, public thaw, or 24h soak claim.

Expected recovery: the board boots with the target player-runtime active from `/data`, keeps `m6-a` as previous rollback, passes playback deep-health before and after reconcile, and public apply/reconcile/rollback stay frozen with `rc=44`.
