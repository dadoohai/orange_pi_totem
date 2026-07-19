# Post-publication independent audit - round 1

Auditor: independent `gpt-5.6-terra`, xhigh, read-only

Audited HEAD: `9ccf97841fb12e68e63d6b0f3b97920a39ffec5b`

## Decision at audit time

`NO-GO` for the specific claim that C26.17 had already been pulled by a natural
timer firing. Recovery, package integrity, public remote apply/no-op and prod15
compatibility were otherwise confirmed.

## Blockers found

1. The only recorded timer trigger predated C26.17 publication. Public apply and
   no-op were real but initiated by starting the same production service
   manually. The evidence gate did not correlate the timer event timestamp with
   the C26.17 journal event, so its green result alone could overclaim a natural
   firing.
2. The repository root `README.md` still called lab-1u the current baseline and
   described core OTA as manual, contradicting the operational source of truth.
3. Natural-timer evidence being collected during the audit was untracked and
   therefore could not be accepted.

## Facts independently confirmed

- HEAD was initially clean; `git fsck` and the committed evidence checksums
  passed.
- The six public C26.17 assets matched the committed local copies byte for byte.
- C26.15, C26.16 and C26.17 have identical executable contents with distinct
  package identities.
- Both release gates contained 85/85 green steps; the canonical sandbox replay
  used an isolated `/tmp` state.
- Prod15 rejected C26.17 before state/symlink creation and selected C21.24.
- No credential, private key or bearer token was found in evidence or payload.

## PDCA response

- `README.md` was updated to declare prod19/C26.17 and mark the 1u sections as
  historical.
- A real reboot was initiated with the production timer enabled. Its natural
  post-publication result is collected separately and must be committed before
  this blocker can close.
- The evidence gate timestamp/tag correlation remains a hardening item unless
  the natural run itself is recorded directly and independently reviewed.
