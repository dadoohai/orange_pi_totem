# C18 production image prod5 build - 20260710T151018Z

Negative build evidence for the M5 exact-target `player-runtime` auto-pull
candidate. The builder reported green, but independent inspection of the final
image found inherited lab state. This artifact is blocked and must not be
distributed or flashed as production.

## Result

- round: `C18.IMAGE-PROD.5`
- image tag: `c18-hwdecode-prod-5`
- image version: `c18.image-prod.5`
- repo commit: `21bd422fcb4f6c93cbe102dc3202c31565b695f7`
- image sha256:
  `23233238dd23c1c5b51090674275a0710519a55742181c339fe042087a52848f`
- image bytes: `1971322880`
- builder offline validation: passed
- independent artifact audit: **blocked**

## Blockers

- private lab firstboot file with Wi-Fi/password values remained embedded;
- lab firstboot service and conditions remained enabled;
- historical markers still claimed private/not-for-production;
- SSH host keys were inherited and would be reused across devices.

Values are intentionally omitted from this public evidence. `prod6` supersedes
this artifact and adds fail-closed checks for all four conditions.

## Scope

- production marker, policy and both update timers were embedded;
- `totem-core` remains the independent common OTA path;
- `player-runtime` is authorized only for the exact C22 repo/tag/hashes;
- `latest`, prerelease and downgrade are disabled;
- the player factory seed had no API key, station/environment identity or token;
- no real config, `player-runtime` current/previous or verified marker is
  pre-seeded.

## Non-Claims

- the image must not be flashed or distributed;
- the real timer auto-pull, no-op and two rollback swaps still require the
  board run;
- this evidence does not provide device attestation or authorize future
  `player-runtime` targets.
