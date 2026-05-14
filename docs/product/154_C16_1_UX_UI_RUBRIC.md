# 154 - C16.1 - UX/UI Rubric

## Dimensions

Each screen or journey is scored from 1 to 5:

| Dimension | What is scored |
| --- | --- |
| Task clarity | The user understands why the screen exists |
| Primary action clarity | The next action is obvious |
| Text density | The screen is readable without overload |
| Visual hierarchy | Title, content and actions have clear priority |
| Progress feedback | Waiting states look intentional |
| Error recovery | Failure has a safe next step |
| Language consistency | Words match the rest of the appliance |
| Perceived trust | The appliance feels reliable, not improvised |
| Perceived polish | The screen looks like product UI |
| Confusion risk | Low, medium or high likelihood of misinterpretation |

## Score Meaning

- **5:** premium/aspirational. Clear, calm, polished, measurable.
- **4:** good for homologation. No major confusion; safe to ship in private
  homologation image.
- **3:** acceptable temporarily. Works, but should be improved.
- **2:** confusing. Can cause support load or operator anxiety.
- **1:** blocking. Prevents use, leaks technical state, or creates unsafe
  interpretation.

## Severity

### P0

- Prevents the user from using a critical journey.
- User does not know what to do.
- A valid wait looks like a frozen appliance for too long.
- Terminal, shell, login or raw technical screen appears.
- A secret can appear.
- Critical error has no recovery path.

### P1

- Feedback is insufficient in a critical journey.
- Copy is confusing.
- Flow causes avoidable anxiety.
- Recoverable error is poorly explained.
- Critical transition looks abrupt or unreliable.

### P2

- Polish.
- Microcopy.
- Visual consistency.
- Layout refinement.

### P3

- Motion design.
- Premium experience.
- Advanced responsive layout.
- Aspirational design-system work.

## C16.1 Result

The C16.1 offline rubric found no P0. P1 items remain around negative-path
coverage, HDMI/camera perception, update UX and full-wizard polish. These are
not blockers to start C17, but they must become explicit C17 validation gates
or scheduled C16.2/C16.3 work.
