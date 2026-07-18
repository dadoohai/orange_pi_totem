# Prod17 C26 build evidence

Date: 2026-07-18

Artifact:

- tag: `c18-hwdecode-prod-17-c26`;
- version: `c18.image-prod.17-c26`;
- image SHA256:
  `696bd671cfc819c51c8dcc977633d0a803fb2c986d09c3b21a2c6d099d27d00b`;
- build commit: `bd119ba8fcb5721ce6a6275e1f23615c20022905`;
- predecessor: `c18-hwdecode-prod-16-c26-candidate`, SHA256
  `18c1b42c57809b704820f5dfa383fb05a3d254d50745cb217440f241c75e1168`.

The image embeds the exact governed package
`c26.5-local-recovery-20260718-f1d0da9-actions` from source commit
`f1d0da92eff5f0aa94036b0ae5a8a85e632450dc`, payload SHA256
`b8864cc913f6e7ca4562a0e3edfe9eb0ba55a6aef5019a47a0535397ba26f4df`.

Offline validation passed, including clean filesystem check, production
credential provenance, absence of embedded config/identity/secrets, exact
C26.5 payload, production policy/timer and preserved C25B player target.
Independent source review found no functional image blocker; the identity
test was then strengthened to reject the prod16 predecessor explicitly.

Non-claim: the sidecar intentionally keeps `ready_for_manual_card_flash=false`
and `hardware_validation_required=true`. This build has not yet been written
to a card or validated live, so it is not the active distribution baseline.

