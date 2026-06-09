# C18 1v player-runtime teardown failure evidence

This directory preserves the negative 1v milestone that blocked player-runtime thaw.
It is not a passing M6 authorization and must not be used as readiness evidence.

## Scope

- Image under test: `c18-hwdecode-lab-1v`.
- Component under test: `player-runtime` lab A/B path.
- Failure class: MPV/GPU teardown fault on the live-update path.
- Public freeze remained in force; this evidence was produced through lab-only guarded tooling.

## Artifacts

| File | SHA256 | Purpose |
| --- | --- | --- |
| `c18-m6-1v-20260609T014031Z.partial.tar.gz` | `f81dd69fa1d3ee19b33a6a2db76e7e56d7b9c0a44529775cd12229c2dddd9370` | Partial M6 run that failed before a decisive cold boot. Candidate playback health was green before teardown; the following service health observed prior panfrost contamination. |
| `c18-kiosk-sigterm-20260609T020032Z.tgz` | `0f780c33bfe3b866a44233960ec3b0623ed04867bc5115606a54d982d8927dde` | Kiosk parent SIGTERM teardown probe showing panfrost fault deltas while preserving service restoration. |
| `c18-mpv-relaunch-20260609T020433Z.tgz` | `126306c3bc25d63a3ed311785842bdda169f56636ddbd2e4e2b574aa38bc05dc` | Direct MPV relaunch/teardown probe showing that `ipc_quit` alone is not yet sufficient proof of clean teardown in every sequence. |

## Decision

The 1v run reinforced the no-thaw decision. The next acceptable milestone must prove, on hardware, that repeated MPV teardown/relaunch and the production service restart path complete with `panfrost_faults_delta == 0`.

The candidate-health teardown gate introduced after this run is the detector for this class. The runtime fix must still be proven by a new image and M6 run.
