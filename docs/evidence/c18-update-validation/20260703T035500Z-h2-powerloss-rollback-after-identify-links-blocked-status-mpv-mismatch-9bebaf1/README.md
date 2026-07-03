# C18 H2 Power-Loss Blocker: rollback identify-links status/MPV mismatch

Checkpoint `rollback_after_identify_links` reached the intended physical cut point on the board. The target runtime `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1` was current, the previous runtime was `c18.player-runtime-m6-a-20260610T0501Z-29ff33b`, and the target was quarantined for the rollback trial before power was cut.

After power returned, the board selected the previous runtime from `/data`, which is the expected safe rollback direction for this observed boot behavior. The checkpoint is still blocked because playback health failed: public player status advanced through multiple media aliases while MPV stayed on one media alias.

This evidence is not counted as a passing H2 checkpoint. It records a real blocker and the controlled recovery that followed.

Key facts:
- checkpoint: `rollback_after_identify_links`
- cut point: `2026-07-03T03:36:26Z`
- resume health: failed `status_mpv_path_aligned`
- failed resume counters: `status_unique_aliases=7`, `mpv_unique_aliases=1`, `status_mpv_max_consecutive_mismatches=53`
- live pre-restart counters: `status_unique_aliases=4`, `mpv_unique_aliases=1`, `status_mpv_max_consecutive_mismatches=24`
- recovery: controlled `kiosky-player.service` restart
- post-restart health: passed with `status_advanced_without_mpv=false`

Source archives captured from the board:
- blocked evidence archive sha256: `044bc6b122756996c706a9b19bf0c96b53f634c82ae48a5d2a0bb4da1bf45f72`
- recovery evidence archive sha256: `c59ffefee55ed67a02ddc253f7f4d2384cf612c19da3846e2a23e47f838615cc`

Non-claims:
- no stable or production readiness
- no public player-runtime thaw
- no H2 power-loss pass for this checkpoint
- no proof that restart recovery is equivalent to surviving the power-loss checkpoint
