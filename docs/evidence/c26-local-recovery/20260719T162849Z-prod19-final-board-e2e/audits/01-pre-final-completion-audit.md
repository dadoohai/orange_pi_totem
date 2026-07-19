# Pre-final independent completion audit

Date: 2026-07-19

Agent: `019f7b74-ef19-7fd1-935b-f5be21ce03b0` (`gpt-5.6-sol`, ultra)

Initial verdict: **NO-GO pending evidence closure; no functional defect or
image rebuild identified.**

The auditor independently confirmed the exact prod19 image, C26.16/C26.15
slots, semantic/release gates, real restart, interrupted restore and same-op
resume, exact backend revocation, old/new token behavior, governed roundtrip,
real poweroff and final 60/60 hardware-decode health.

It requested the following missing closure evidence:

1. real Enter-on-Cancel, Escape and repeated-key behavior;
2. causal F10 input-to-service evidence;
3. live firstboot marker, ordering and image-contract proof;
4. live updater guard while an F10 session is active;
5. stronger Wi-Fi/orientation preservation evidence;
6. raw backend tests and deployed-source-to-commit provenance;
7. preservation of the initial non-canonical negative health result;
8. a machine-readable record that supersedes the immutable pre-flash
   `artifact-ready=false` sidecar;
9. sanitized evidence, global hashes, commit and remote traceability.

## Central disposition before final audit

- Items 1-4 were re-exercised read-only or through safe cancellation and are
  recorded in `board/closeout/`.
- Item 5 is bounded honestly: the reset engine cannot target paths outside
  `/data`; Wi-Fi is under `/etc`, and public orientation is outside every
  reset domain. Static and installed tests pass. The clean prod19 campaign had
  no Wi-Fi profile and did not record byte identity for orientation across the
  restore, so those two physical claims remain explicit non-claims rather than
  being silently upgraded.
- Item 6 is closed by `backend/self-revocation-unit-test.log` and
  `backend/deployed-source-provenance.json`.
- Item 7 is retained as `board/initial/deep-health-initial-negative.json`. It
  failed only `service_process_unfiltered`; all canonical reruns are green.
- Items 8-9 remain part of final evidence freeze, independent audit, commit and
  publication. The backend commit is already present on its remote branch.

The auditor did not inspect the subsequently observed core timer `rc=45` state;
that observation is submitted independently to the final reviews.
