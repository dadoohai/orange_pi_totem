# 156 - C16.1 - UX QA Harness Architecture

## Modules

- Gallery generator:
  - Location: `scripts/qa/`.
  - Purpose: Produce synthetic screens and optional rendered images.

- Journey catalog:
  - Location: `scripts/qa/` and docs.
  - Purpose: Keep personas, journeys and screen intent versioned.

- Scenario runner:
  - Location: future `scripts/qa/`.
  - Purpose: Simulate journeys without real config.

- Input stress:
  - Location: existing wizard self-tests.
  - Purpose: Validate fast typing, Backspace, Esc, Ctrl+B, Ctrl+U and F2/Ctrl+P.

- Visual metrics:
  - Location: `scripts/qa/`.
  - Purpose: Score text density, action clarity and feedback coverage.

- Timeline collector:
  - Location: `scripts/remote/`.
  - Purpose: Collect public runtime state from board when authorized.

- Status observer:
  - Location: `scripts/board/` and `scripts/remote/`.
  - Purpose: Aggregate safe status categories.

- Framebuffer capture:
  - Location: future optional remote probe.
  - Purpose: Capture limited visual states when safe.

- Report generator:
  - Location: `scripts/qa/`.
  - Purpose: Write evidence artifacts and summaries.

- Backlog classifier:
  - Location: `scripts/qa/`.
  - Purpose: Split P0/P1/P2/P3 and recommend next front.

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
