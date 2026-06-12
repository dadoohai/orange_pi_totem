# C18 player-runtime server-side governance evidence - c16fb3e

This directory records the external trust material and gate outputs for the
server-side publish governance family attached to the homologation
`player-runtime` release:

- release: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`
- component: `player-runtime`
- channel: `homologation`
- source commit: `c16fb3ed01f0ce25c8203e5fe1d60baf60a75749`
- selected at UTC: `2026-06-12T12:51:27Z`

The signing private key was generated outside the repository and was not
committed. The committed trust inputs are only the public key and trust-anchor
evidence.

Release-attached server-side assets:

- `releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/c18-server-side-publish-governance.json`
- `releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/audit-log.ndjson`
- `releases/player-runtime/c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e/signatures/`

Gate results:

- `server-side-governance-gate.json`: `passed=true`.
- `h2-readiness-with-server-side-governance.json`: `passed=false`.
- H2 server-side check: `passed=true`.
- Remaining H2 blockers:
  - full physical power-loss matrix 17/17;
  - 24h soak;
  - stable promotion authorization;
  - explicit operator thaw decision.

Non-claims:

- this evidence does not publish releases;
- this evidence does not enable auto-pull;
- this evidence does not promote stable;
- this evidence does not thaw `player-runtime`;
- this evidence does not complete H2.

Artifact hashes:

- `c18-server-side-release-signing-key.pub.pem`:
  `b822b99d622ad5e2d01f4884db62d4c3c5788381069ecfc93d7d409d9d39402e`
- `c18-server-side-trust-anchor.json`:
  `c1d36a808dd6b77cd7c9dc01606d2188c3c81273effb9940f0e514da24f95c85`
- `server-side-governance-gate.json`:
  `43cdc8e802ca7f0556e448f3bc18fb982c6512ce5859670c0707116dccf7a68d`
- `h2-readiness-with-server-side-governance.json`:
  `a4f767fcc5737e584bb97d68167697cb85736dd3db21658a9f82988e2b709cf6`
- release `c18-server-side-publish-governance.json`:
  `e5fd6ce2965e9b946bbd0f750420448d96fc894b700c98d99e9e40fe46113a92`
- release `audit-log.ndjson`:
  `6ff729caf695fb2a5f523d162fbf8b18c831d6aa9f81f346927abb1037a6bd64`
