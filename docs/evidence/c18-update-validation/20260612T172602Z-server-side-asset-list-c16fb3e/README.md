# C18 player-runtime server-side asset list - c16fb3e

Generated at UTC: `2026-06-12T17:26:02Z`.

This directory materializes the publish-asset inventory for the C18
`player-runtime` homologation release:

- release: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`;
- component: `player-runtime`;
- channel: `homologation`;
- source commit: `c16fb3ed01f0ce25c8203e5fe1d60baf60a75749`.

The asset list was generated offline with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_server_side_publish_asset_collect.py \
  --server-side-evidence releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/c18-server-side-publish-governance.json \
  --trust-anchor-evidence docs/evidence/c18-update-validation/20260612T125127Z-server-side-governance-c16fb3e/c18-server-side-trust-anchor.json \
  --expected-release-gate-sha256 c315841cb517c544a454475e841ce56048d5211dbe1b310733fd0840f72fffc3 \
  --relative-to . \
  --json
```

Files:

- `server-side-asset-list.json`: `dadooh.c18.server_side_publish_asset_list.v1`;
  repo-relative asset paths, byte sizes and SHA256 hashes for the release
  governance JSON, manifest, payload, release gate, audit log, signatures and
  trust-anchor evidence.

Non-claims:

- this evidence does not publish releases;
- this evidence does not enable auto-pull;
- this evidence does not promote `stable`;
- this evidence does not thaw `player-runtime`;
- this evidence does not complete H2;
- this evidence does not replace power-loss 17/17, soak 24h, stable promotion
  or formal thaw decision.
