# C18 H2 Power-Loss Blocker: status/MPV mismatch

During the remaining H2 physical power-loss campaign, checkpoint `after_release_tree_fsync` returned to the verified baseline runtime, but resume health did not pass. A follow-up live probe showed MPV continuing to play one media while player status advanced through multiple media aliases.

This blocks continuing the H2 power-loss campaign. It is not a production/stable claim and it is not counted as a passing checkpoint.

Key evidence is in `blocker-summary.json` and `health-probe-public.json`. Raw live status/IPC capture was converted into sanitized aliases in the summary.
