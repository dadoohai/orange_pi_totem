# 176 - C17.8.1 - Wizard UX Operation Model

Status: passed

C17.8.1 audits and tightens the local visual setup wizard as a product
operation flow. It uses only local simulation, fake inputs and generated SVGs.
It does not use Orange Pi hardware, SSH, card writes, image builds, real writer,
real config, totem-core release publishing or player timing work.

## Current Flow Audit

`wizard_current_flow_audit`

| screen_id | purpose | primary_action | secondary_action | current_keys | current_footer | text_density | confusion_risk | missing_state | recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `01-welcome` | Start setup | Enter starts | Esc cancels | Enter, Esc | Enter inicia / Esc cancela | low | low | none | keep |
| `01-orientation` | Choose display orientation | Enter previews | Esc cancels | arrows, Enter, Esc, numeric shortcuts | Setas / Enter / Esc | medium | medium | help not needed | simplify footer grammar |
| `01-orientation-confirm` | Confirm physical orientation | Enter confirms | Esc goes back | arrows, Enter, Esc, B/Ctrl+B compatibility | Setas / Enter / Esc | low | low | none | remove B from primary instructions |
| `02-connection` | Choose internet path | Enter confirms | Esc cancels | arrows, Enter, Esc | Setas / Enter / Esc | low | medium | current Wi-Fi missing can error | keep, shorten labels |
| `02-wifi-list` | Pick local Wi-Fi | Enter selects | R refreshes, Esc returns | arrows, PageUp/Down, R, Enter, Esc, B/Ctrl+B compatibility | Setas / Enter / R/Esc | medium | medium | weak/no networks handled | keep pagination, simplify footer |
| `02-wifi-psk` | Enter Wi-Fi password | Enter confirms | Esc returns, F2/Ctrl+P toggles | text, Backspace, arrows, Ctrl+U, F2, Ctrl+P, Esc, Ctrl+B compatibility | Enter / Esc / F2 | medium | medium | wrong password state needed | keep password hidden and add replay |
| `02-wifi-result` | Report Wi-Fi apply outcome | Enter continues | Esc returns | Enter, Esc, B/Ctrl+B compatibility | Enter / Esc | medium | medium | clearer retry path | keep as result state |
| `03-environment` | Enter environment UUID | Enter validates | Esc returns | text, arrows, Backspace, Delete, Ctrl+U, Enter, Esc | Enter / Esc / Setas+Ctrl+U | medium | low | invalid UUID state | keep cursor and replay edit-middle |
| `03-environment-validation` | Remote/content preflight | Enter continues/corrects | Esc returns/cancels | Enter, Esc, B/Ctrl+B compatibility | Enter / Esc | medium | medium | API unavailable confirmation | keep explicit warnings |
| `05-review` | Review before saving/candidate | Enter saves/prepares | Esc returns | Enter, Esc, B/Ctrl+B compatibility | Enter / Esc | low | low | none | Esc returns, never saves |
| `06-complete` | Exit setup | Enter exits | none | Enter | Enter sai | low | low | none | keep |
| error/cancel | Recover or abort | Enter retries/returns | Esc cancels | Enter, Esc | Enter / Esc | low | low | none | keep safe no-write path |

## Navigation Contract

Standard keys:

- Enter advances, confirms the primary action or validates the current field.
- Esc goes back when a previous step exists; on top-level/cancel screens it
  cancels. Esc never saves.
- Up/Down arrows navigate lists and options.
- Left/Right arrows move the cursor in text fields and can also switch simple
  two-option controls.
- Backspace edits text only; it does not navigate.
- Ctrl+U clears the current text field.
- R refreshes Wi-Fi/list screens.
- F2 toggles password visibility. Ctrl+P remains a compatibility fallback for
  the same toggle.
- F10 opens settings outside the wizard session and is not shown inside normal
  wizard screens.
- B and Ctrl+B remain accepted as temporary compatibility shortcuts for back,
  but they are no longer primary footer instructions.

Footer grammar:

- Always show the primary action first.
- Always show how to go back or cancel when the screen accepts it.
- Show no more than three footer groups on normal screens.
- Text fields may compress edit hints as `Setas/Ctrl+U editam` while the full
  contract is documented here.
- Error screens say what Enter does and whether Esc cancels or returns.

## Target Flow

| step | user objective | primary_action | secondary_action | possible_error | short_message | technical_state | simulated_test |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Welcome / Configuracao inicial | Start local setup | Enter starts | Esc cancels | operator cancels | Vamos ajustar tela, rede e ambiente. | wizard session lock active | `cancel_flow` |
| Tela / orientacao | Match physical installation | Enter confirms orientation | Esc goes back/cancels | wrong orientation selected | Escolha como o totem esta instalado. | orientation candidate only | `happy_path_synthetic`, `back_navigation` |
| Internet / Wi-Fi | Select current Wi-Fi, local Wi-Fi, or bench | Enter confirms | R refreshes lists, Esc returns | no networks, wrong password | Escolha a conexao. | no real writer in replay | `wifi_wrong_password_fake` |
| Ambiente | Enter valid UUID | Enter validates | Esc returns, Ctrl+U clears | invalid UUID, API unavailable | Digite o ID do ambiente. | local UUID validation and optional preflight | `environment_invalid_uuid`, `environment_edit_middle`, `api_unavailable_fake` |
| Revisao | Confirm before candidate/write | Enter prepares/saves | Esc returns | operator needs correction | Confira antes de concluir. | no save until Enter | `happy_path_synthetic` |
| Salvando | Busy state | wait | none | writer/apply failure | Aguarde. | writer gated outside replay | gallery only |
| Concluido | Exit setup | Enter exits | none | none | Candidata pronta. | player restoration follows wrapper | `happy_path_synthetic` |

No step was removed in C17.8.1. The current step count is justified because
orientation, network, environment and review each map to a different operational
risk. The simplification is in navigation grammar, footer density and replayable
states, not in removing functional gates.

## Code Changes

Runtime wizard changes in `scripts/board/totem_setup_visual_wizard.py`:

- Footers changed from mixed `B`/`Ctrl+B` grammar to Enter/Esc-first grammar.
- Esc now returns from substeps such as orientation confirm, Wi-Fi list, password
  entry, Wi-Fi result, environment validation and review.
- B/Ctrl+B remain accepted as compatibility fallback but are not primary
  instructions.
- Text input footers were shortened while preserving Backspace, arrows, Delete,
  Ctrl+U, F2 and Ctrl+P behavior.
- Wi-Fi wrong-password and API-unavailable paths are now covered by local replay
  artifacts, without changing NetworkManager or writer behavior.

Gallery changes in `scripts/qa/generate_ui_ux_gallery.py`:

- Wizard gallery footers and metadata were updated to the same navigation
  contract.

Replay changes:

- `scripts/sim/run_wizard_input_replay.py` is now a real harness.
- It renders SVGs, trace JSON, assertions JSON and summary Markdown.
- It uses only TEST_* synthetic data and does not call writer, backend, SSH,
  MPV, NetworkManager or real config.

## Replay Results

Evidence path:

`docs/evidence/candidate-a/runs/20260518T200936Z-c17-8-1-wizard-ux-operation-model/`

Input replay:

- `scenario_count=7`
- `screens_count=19`
- `assertions_count=14`
- `assertions_passed=true`

Scenarios:

- `happy_path_synthetic`
- `back_navigation`
- `environment_invalid_uuid`
- `environment_edit_middle`
- `wifi_wrong_password_fake`
- `api_unavailable_fake`
- `cancel_flow`

Gallery/rubric:

- `gallery_screen_count=53`
- `png_render_available=false`
- `p0_items_count=0`
- `min_task_clarity=5`
- `min_visual_hierarchy=5`
- `min_text_density_score=4`
- `high_risk_screens=0`

## Limitations

Still requires Orange Pi:

- F10 physical entry path.
- HDMI readability, flicker and real orientation perception.
- Real Wi-Fi radio, NetworkManager apply and RF conditions.
- Real writer/apply path and post-wizard player restoration.
- MPV/DRM/KMS behavior.
- C17.7 hardware boot validation.
- C12/read-only and C12.4 power-cut.

## Decision

`c17_8_1_status=passed`

`totem_core_package_needed=true`

`ready_for_c17_8_2_totem_core_package=true`

`ready_for_hardware_wizard_validation=true`

`ready_for_c18_player_work=true`

## C17.8.2 Follow-Up

C17.8.2 packaged the C17.8.1 wizard runtime as local totem-core RC
`c17.8.2-wizard-ux-rc-20260518T202740Z` on channel `lab`. The package manifest
and SHA256 were validated, apply-local/rollback/fallback/settings-lock guard
passed in `.sim/c17-8-2`, and the input replay/gallery were executed against
`.sim/c17-8-2/data/core/totem/current`.

No remote GitHub Release was published. Next update-channel governance belongs
in C17.9.
