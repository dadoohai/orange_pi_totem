# C18 playback soak exception - 9bebaf1

Status: formal business exception for production release consideration.

This evidence does not convert the HDMI-event soak into a clean H2 soak. The
24h run remains failed because HDMI was disconnected for most of the run. This
artifact records the explicit business decision to accept that specific failed
soak as sufficient for release planning, while preserving the non-claims below.

Target:

- component: `player-runtime`
- package: `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`
- source commit: `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`
- payload sha256: `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`

Bound inputs:

- soak summary: `../20260704T195822Z-soak-24h-hdmi-event-9bebaf1/soak-summary.json`
- operator HDMI event: `../20260704T195822Z-soak-24h-hdmi-event-9bebaf1/operator-hdmi-event.json`

Non-claims:

- this exception does not make the soak clean;
- this exception is not a generic soak bypass;
- this exception does not publish releases;
- this exception does not enable auto-pull;
- this exception does not execute public thaw;
- this exception is bound to one target and one soak.
