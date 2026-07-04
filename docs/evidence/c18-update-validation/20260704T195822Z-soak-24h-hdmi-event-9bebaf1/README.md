# C18 playback soak 24h HDMI-event evidence

Status: negative for clean H2 soak, useful for runtime resilience evidence.

Target:
- component: `player-runtime`
- version: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- board source path: `/data/evidence/c18-playback-soak-24h-20260703T195556Z-9bebaf1`

Run window:
- started UTC: `2026-07-03T19:55:57Z`
- ended UTC: `2026-07-04T19:58:22Z`
- started local BRT: `2026-07-03 16:55:57-03:00`
- ended local BRT: `2026-07-04 16:58:22-03:00`

Operator HDMI event:
- HDMI last confirmed healthy by playback samples: `2026-07-03 20:19:58-03:00`
- HDMI first sustained video/HW decode loss by playback samples:
  `2026-07-03 20:20:00-03:00`
- HDMI physical disconnect inferred window: between `2026-07-03 20:19:58-03:00`
  and `2026-07-03 20:20:00-03:00`
- HDMI reconnect kernel event: `2026-07-04 16:29:54-03:00`
- first healthy playback sample after reconnect: `2026-07-04 16:29:58-03:00`
- operator estimate before log/sample analysis was approximately
  `2026-07-03 20:30:00-03:00`.

Result:
- `soak-summary.json` reports `passed=false`.
- failure reasons: `cycle_failed`, `hwdec_expected_ratio_below_min`.
- 24 cycles were collected.
- 24 cycles failed the strict cycle gate.
- minimum HW decode expected ratio was `0.0`, matching the long HDMI-disconnected interval.

Useful observations:
- the player service stayed up for the whole run;
- MPV restart count delta stayed zero;
- systemd restart delta stayed zero;
- panfrost fault delta stayed zero;
- MMC timeout/reset delta stayed zero;
- ext4 error delta stayed zero;
- media load failure count stayed zero;
- IPC sampling stayed mostly available across the run.

Non-claims:
- this is not a clean constant-HDMI 24h soak;
- this is not H2 green evidence;
- this is not stable promotion evidence;
- this is not a public thaw decision;
- this is not production authorization.

The raw TSV/NDJSON samples remain on the board. This repository stores the
public summary and per-cycle public JSON evidence needed to preserve the
decision trail without committing large raw sample streams.
