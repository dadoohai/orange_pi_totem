# 155 - C16.1 - AI Assisted UX QA Architecture

## Decision

Do not run a full Codex/AI agent on the Orange Pi. The board is an appliance
target, not the analysis environment. AI-assisted UX QA runs on the builder and
uses:

- offline synthetic artifacts;
- sanitized public status;
- small temporary probes over SSH only when a runtime card allows it;
- optional HDMI/camera evidence for final perception.

## Levels

### Level 1 - SVG/offline

Best for:

- copy;
- density;
- layout structure;
- screen intent.

It does not require the board and should be the default for design review.

### Level 2 - PNG/screenshot render

Best when a vision-capable model should inspect pixels.

Use only converters already available in the environment. Do not install
packages without explicit authorization.

### Level 3 - Runtime status/timeline

Runs over SSH with sanitized probes.

It cannot see HDMI completely, but it can prove whether services, public state,
player status and network category are healthy during a journey.

### Level 4 - Framebuffer

Useful only for selected states and only when safe.

MPV/DRM/KMS can bypass what simple framebuffer capture sees, so evidence must
state the limitation.

### Level 5 - HDMI capture/camera

Best for perception:

- flicker;
- black frames;
- orientation;
- transition smoothness;
- real user trust.

It requires hardware and is not mandatory in C16.1, but it is the final
authority for visual perception before scaling deployment.

### Level 6 - Synthetic user

Combines journey, screen map, status and rubric.

The agent evaluates what a specific persona would infer and produces a
prioritized backlog. This is where product and QA converge.

## Security Model

AI-assisted QA must never ingest:

- real config;
- private seed;
- API key or real API URL;
- environment id;
- SSID or Wi-Fi password;
- IP/MAC/DNS;
- NetworkManager profiles;
- raw logs with private values;
- media/cache URLs when sensitive.

The safe inputs are synthetic screens, public-safe status categories, booleans,
counts and sanitized timelines.

## Operating Rule

If a UX finding cannot be validated without HDMI/camera, it is recorded as
`hdmi_capture_required_for_final_perception=true`. The agent must not pretend a
SSH timeline is visual proof.
