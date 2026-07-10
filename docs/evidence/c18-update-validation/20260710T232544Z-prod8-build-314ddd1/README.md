# C18 production image prod8 build

Offline build and independent artifact review for the production image that
embeds the C21.9 core and the exact C23 player-runtime authorization.

## Result

- image: `c18-hwdecode-prod-8` / `c18.image-prod.8`
- repo commit: `314ddd18201aa21f3cc2722ff0d668566831e015`
- image SHA256: `6c3801d970d7bc5248f4c8fc5838b4233ea2e9e1f2120de4bffd7bea07f063ee`
- image bytes: `1971322880`
- offline validation: passed
- source release gate: `78/78`
- independent artifact reviews: two approvals, zero blockers for board flash

The real image filesystem was checked read-only. Its marker, C21.9 files,
fallback files, C23 authorization, timers, freeze, empty production seed and
filesystem state matched the intended production profile. The embedded health
and updater both execute the status-render-preview self-test.

## Scope

This evidence approves one controlled board flash. It does not claim a
successful prod8 first boot, QR onboarding, remote C23 auto-pull, fleet rollout
or broad production distribution. Shared root-password SSH remains the
explicitly accepted first-scale risk; per-device credentials remain M6.
