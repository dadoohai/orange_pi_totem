# C18 H2 power-loss board preflight after topology reset - mpv stuck fix 9bebaf1

Result: `passed=true`, `result_claim=h2_powerloss_board_preflight_accepted`.

This is a read-only board preflight after the governed topology reset in
`20260617T201430Z-h2-powerloss-topology-reset-mpv-stuck-fix-9bebaf1`.

The gate accepted the board/package/image/session topology for starting the
physical H2/P0 power-loss session:

- target package `c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`;
- target source `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`;
- target payload sha256 `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`;
- `current -> releases/c18.player-runtime-m6-a-20260610T0501Z-29ff33b`;
- `previous` absent;
- target not current, not previous, not quarantined;
- target release dir absent;
- policy `device_channel=homologation`, `allowed_components=["totem-core"]`;
- update timer disabled/inactive;
- image marker `c18-hwdecode-lab-1x`.

Non-claims:

- not power-loss evidence;
- not 17/17;
- not H2 green;
- not stable or production;
- not public thaw.

