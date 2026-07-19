# Prod19 C26 build evidence

Date: 2026-07-19

This directory records the clean offline build and independent forensic review
of the C26 prod19 bench candidate.

- image: `c18-hwdecode-prod-19-c26`;
- version: `c18.image-prod.19-c26`;
- build commit: `5838983806f953bf055734f8c413b63801a138ae`;
- image SHA256:
  `991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`;
- current: `c26.16-local-recovery-20260719-5df9521-final-guarded-actions`;
- previous: `c26.15-local-recovery-20260719-a09bf39-guarded-transaction-actions`;
- C26.15 release gate: `85/85`;
- C26.16 release gate: `85/85`;
- offline image validation: green;
- direct copied-filesystem validation: `220/220`;
- extracted ext4 filesystem check: clean.

Three independent reviews found no reproducible blocker for manual bench flash.
Direct inspection confirmed the exact two slots, C25B player baseline, image
identity, update policy, timers, credential hygiene and empty device identity.
A copied image failed closed after current-slot tampering; governed rollback
and return moved between the two exact slots, while a tampered previous slot
was rejected before link changes.

Decision: **GO for manual bench flash of this exact SHA256 only**.

Non-claim: this is not yet the public distribution baseline. Boot, first-boot
identity, onboarding, playback, F10, local actions, rollback/reapply and timers
must pass on the physical board before promotion.

The shared support credential, exact C25B player-runtime auto-pull and absence
of device-side signature enforcement are explicit accepted first-scale risks,
not newly inferred claims. Their credentials remain external and no plaintext
is stored here.
