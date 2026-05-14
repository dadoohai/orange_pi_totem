# 151 - C16.1 - Personas and Actors

## Purpose

These personas are operational roles, not marketing abstractions. Each one
exists to make product, QA and engineering discussions concrete.

| Actor | Goal | Knowledge | Anxiety | Expected action | Likely error | Needed feedback | Criticality |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Operador instalador | Put the totem into service on the first visit | Medium | High during black screens or network failure | Power on, press F10, select Wi-Fi, enter environment, finish | Wrong password, weak network, treating wait as freeze | Current state, next action, recoverable error, success | Critical |
| Operador de suporte | Diagnose operation remotely | High | Medium when status is ambiguous | Check status, guide local operator, decide update/reconfig | Confusing content wait with player failure | Public status, timeline, sanitized categories | High |
| Espectador passivo | See content, not infrastructure | Low | Low, but technical screens break trust | None | Treating black screen or login as product failure | Content or clean wait message | Medium |
| Cliente que recebe o equipamento | Receive a finished-feeling product | Low | High if first setup needs support | Watch install or use configured device | Thinking boot/update wait is broken | Clean, consistent visual states | High |
| Tecnico remoto | Recover and maintain safely | High | High when logs lack categories | Use SSH, updater and sanitized probes | Collecting too much data or using destructive flow | Safe status contracts and guardrails | Critical |
| Backend/API | Provide playlist/config data | System | None | Respond or fail observably | Timeout without public category | `waiting_for_api`, cache/fallback/error categories | High |
| Appliance autonomo | Keep the product surface safe | System | None | Boot, show state, play, update, recover | No feedback, TTY/DRM fight, raw technical screen | Public state machine and minimal visual feedback | Critical |

## Practical Use

Every journey and screen should identify the primary actor. A design is not
accepted only because it is technically correct; it must reduce the most likely
confusion for the actor who sees that state.

The installer and remote technician are the highest-risk actors during setup.
The spectator and customer are the highest-risk actors during normal operation:
they cannot distinguish a valid wait from a defect unless the appliance tells
them.
