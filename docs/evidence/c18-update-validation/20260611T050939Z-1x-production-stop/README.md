# C18 player-runtime teardown/panfrost trial evidence
Producer: scripts/board/c18_player_runtime_teardown_trial.py
Validate with: scripts/qa/c18_player_runtime_teardown_evidence_gate.py

Claim: healthy Python-kiosk stop path measured on hardware image `c18-hwdecode-lab-1x`.
The probe confirmed mpv decoding with `v4l2request-copy`, delivered SIGTERM to
`kiosk_pid`, observed IPC quit, observed no mpv SIGTERM/SIGKILL fallback, measured
`panfrost_delta=0`, confirmed mpv exited after kiosk exit, restored the service, and
validated post-restore deep-health.

Non-claims: GR4b fresh-IPC success, fallback SIGTERM to mpv, wedged/ipc_unresponsive
cleanup, full launcher/systemd cgroup cleanup, power-loss/soak, server-side publish,
stable promotion, and public thaw.
