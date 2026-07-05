# C18 totem-core stable lab apply/rollback

Evidence for a controlled lab run on 2026-07-05.

What was proven:

- the board can select the published `totem-core` stable release when policy is
  temporarily set to `device_channel=stable` and `allow_prerelease=false`;
- the board downloaded the GitHub Release
  `totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1`;
- the payload SHA256 was
  `613d9d6d1099636d7ca956c72e3927d502f1281068f8b0830b2d5f3ba2af0355`;
- apply succeeded and made
  `c18.ota-core-prod-20260705T184013Z-ccaf5a1` current;
- `totem-core` self-test passed after apply;
- `kiosky-player.service` remained active with `NRestarts=0`;
- rollback succeeded and restored
  `c17.6-environment-input-20260514T211247Z`;
- the original lab policy was restored.

Non-claims:

- this was not booted from the production image `c18-hwdecode-prod-1`;
- this did not prove the production systemd timer;
- this did not thaw `player-runtime`;
- this did not validate `media-system`.

