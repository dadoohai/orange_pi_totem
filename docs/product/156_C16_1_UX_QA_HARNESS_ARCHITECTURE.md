# 156 - C16.1 - UX QA Harness Architecture

## Modules

| Module | Location | Purpose |
| --- | --- | --- |
| Gallery generator | `scripts/qa/` | Produce synthetic screens and optional rendered images |
| Journey catalog | `scripts/qa/` and docs | Keep personas, journeys and screen intent versioned |
| Scenario runner | future `scripts/qa/` | Simulate journeys without real config |
| Input stress | existing wizard self-tests | Validate fast typing, Backspace, Esc, Ctrl+B, Ctrl+U, F2/Ctrl+P |
| Visual metrics | `scripts/qa/` | Score text density, action clarity and feedback coverage |
| Timeline collector | `scripts/remote/` | Collect public runtime state from board when authorized |
| Status observer | `scripts/board/` and `scripts/remote/` | Aggregate safe status categories |
| Framebuffer capture | future optional remote probe | Capture limited visual states when safe |
| Report generator | `scripts/qa/` | Write evidence artifacts and summaries |
| Backlog classifier | `scripts/qa/` | Split P0/P1/P2/P3 and recommend next front |

## File Boundaries

- Offline QA scripts live in `scripts/qa/`.
- Remote probes live in `scripts/remote/`.
- Board debug runs write to `/data/state/totem-debug/<run-id>/` only when a
  runtime card explicitly allows it.
- Sanitized evidence is copied to `docs/evidence/...`.
- QA scripts and galleries are not installed in the appliance image by default.

## Probe Rules

Remote probes must:

- avoid reading real config and private seed;
- avoid NetworkManager profiles;
- avoid IP/MAC/DNS/SSID/password output;
- avoid raw logs unless sanitized;
- avoid writer, Wi-Fi changes, reboot, poweroff and power cut;
- sync small public evidence only;
- be temporary unless the image manifest explicitly says otherwise.

## Initial Harness

C16.1 adds:

```text
scripts/qa/c16_ux_operating_model_audit.py
```

It generates personas, journeys, screen map, heuristic rubric scores, backlog
and QA architecture summary without touching the board or runtime.
