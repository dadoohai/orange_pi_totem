# 162 - C17.2 - Visual Design System

## Status

```text
visual_design_system_version=c17.2-appliance-ui.v1
target=wizard_splash_status_svg
no_external_assets=true
no_new_fonts=true
no_new_dependencies=true
runtime_heavy_rendering=false
c18_started=false
```

C17.2 defines a small visual system for the appliance UI. It is intentionally
plain: SVG rectangles, text and existing system fonts only. The goal is to make
the totem look like a dedicated product surface, not a Linux terminal or debug
tool.

## Principles

- Always show a product state before showing any technical detail.
- Make the primary action or wait state visible in a stable footer.
- Use the same dark appliance surface across wizard, splash and status screens.
- Prefer public categories over diagnostics: network, API, cache, media,
  player, update.
- Keep every screen readable at HDMI distance with short text and strong
  hierarchy.
- Do not add external assets, fonts, animation, network calls or heavier
  rendering.

## Palette

```text
background=#0b1220
surface=#111827
surface_raised=#151d2a
surface_active=#13263a
footer=#07111f
border=#2f3d4a
border_muted=#334155
text=#f8fafc
text_muted=#cbd5e1
text_dim=#94a3b8
accent_primary=#06b6d4
accent_strong=#22d3ee
success=#22c55e
warning=#f59e0b
error=#ef4444
```

## Layout

- Canvas remains `1280x720` landscape and `720x1280` portrait.
- Header: 12px accent bar, dark product header, brand chip and step/status
  context.
- Main content: one primary message area and one support/info panel.
- Cards and panels use 8px radius maximum.
- Active items use a left accent rail plus border; inactive items remain dark.
- Footer is a persistent 82px band with the primary action in a button-like
  chip and secondary actions as muted text.

## Typography

- Existing fallback stack only: `Arial, DejaVu Sans, sans-serif`.
- Brand chip: 26-28px bold.
- Screen title: 44-56px bold depending on surface.
- Subtitle/message: 21-30px regular.
- Panel title: 24-26px bold.
- Body items: 17-27px regular.
- Footer primary action: 19-24px bold.

## States

- Loading/waiting states must use explicit copy such as `Aguarde`,
  `Carregando conteudo` or `Preparando midias`.
- Error states use red accent and must include a recovery phrase or support
  path.
- Update states use blue for checking, amber for applying and red for failure.
- Wi-Fi weak/wrong-password screens must be recoverable without exposing SSID
  or password in public artifacts.

## Language

- Use product language first: `Configuracao pendente`, `Iniciando player`,
  `Carregando conteudo`.
- Avoid raw shell/systemd/network terms on HDMI.
- Keep titles under 42 characters and subtitles under 80 characters.
- Limit info panels to three items in the runtime wizard.
- Footers should lead with the primary command; secondary shortcuts follow.

## Screen Intent Matrix

| Screen | Function | Primary Action | Perceived State | Visual Risk |
|---|---|---:|---|---|
| boot | Show the appliance has started | Wait | Starting | Medium |
| preparing | Cover service startup | Wait | Preparing | Low |
| config_pending | Ask for local setup | F10 | Ready to configure | Low |
| config_missing | Explain missing config | F10 | Action needed | Medium |
| setup | Show settings opening | Wait | Transitioning | Medium |
| Wi-Fi list | Select usable network | Enter | Choosing network | Medium |
| Wi-Fi password | Enter secret safely | Enter | Protected input | Medium |
| environment | Enter environment identifier | Enter | Required field | Medium |
| review | Confirm before write | Enter saves | Ready to save | Low |
| saving | Show writer activity | Wait | Saving | Medium |
| complete | Confirm setup success | Wait/Enter | Done | Low |
| starting_player | Cover handoff to player | Wait | Starting display | Medium |
| loading_content | Cover API/cache/media wait | Wait | Loading content | Medium |
| waiting_for_api | Classify API wait | Wait/support | Backend pending | Medium |
| waiting_for_media | Classify media wait | Wait/support | Media pending | High |
| error_no_content | Avoid black failure | Retry/support | No content | High |
| update_checking | Show update check | Wait | Checking | Medium |
| update_applying | Show update apply | Wait | Updating | High |
| update_failed | Show safe update failure | Support/retry | Preserved version | Medium |

## Non-Goals

- No image build in C17.2.
- No HDMI/camera proof in this round.
- No player timing, sync, duration, playlist, loop or `exposure_time_ms`
  changes.
- No changes to writer, Wi-Fi/NetworkManager, update apply logic, kernel,
  U-Boot, DTB or read-only behavior.
