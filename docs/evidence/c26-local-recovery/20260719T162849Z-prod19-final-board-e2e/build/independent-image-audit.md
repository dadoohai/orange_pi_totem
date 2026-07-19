# Independent prod19 image audit

## Verdict

Three independent read-only audits converged on GO for manual bench flash and
NO-GO for baseline promotion until the physical campaign completes.

## Direct findings

- image SHA256, sidecar, build log and manifest agree;
- MBR and the single Linux partition are structurally valid;
- copied ext4 filesystem is clean under `e2fsck -fn`;
- direct validation of the copied filesystem passed all `220/220` checks;
- `current` is C26.16 and `previous` is C26.15, with exact state, symlinks,
  manifests, payload hashes, source commits and capabilities;
- each embedded slot matches its tracked payload and source commit;
- C26.15/C26.16 pass the current semantic gate; C26.13/C26.14 fail;
- removing the current writer from a copied filesystem makes validation fail;
- governed rollback C26.16 -> C26.15 and return C26.15 -> C26.16 update links
  and state; a tampered previous slot is rejected before mutation;
- C25B player bytes and authorization are preserved;
- no real config, machine identity or SSH host keys are pre-embedded;
- production policy and exact-target timers are present as designed.

## Bounded risks

- C26.15 and C26.16 are mechanically distinct slots with identical executable
  content. This protects slot integrity and enables the initial recovery UI;
  it does not undo a logical defect shared by both packages. A later OTA makes
  the former current package the functionally older rollback target.
- The shared support credential, exact C25B auto-pull, homologation identity of
  embedded packages and missing device-side signature enforcement remain
  explicit first-scale risk acceptances. They do not block the controlled
  board test and remain roadmap hardening for broader scale.
- Hardware behavior has not yet been proved for this exact image.

## Decision boundary

Only the image with SHA256
`991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`
is approved for the next manual bench flash. No distribution or baseline
promotion is inferred from this audit.
