# 151 - C16.1 - Personas and Actors

## Purpose

These personas are operational roles, not marketing abstractions. Each one
exists to make product, QA and engineering discussions concrete.

## Actors

### Operador instalador

- Goal: Put the totem into service on the first visit.
- Knowledge: Medium.
- Anxiety: High during black screens or network failure.
- Expected action: Power on, press F10, select Wi-Fi, enter environment,
  finish.
- Likely error: Wrong password, weak network, treating wait as freeze.
- Needed feedback: Current state, next action, recoverable error, success.
- Criticality: Critical.

### Operador de suporte

- Goal: Diagnose operation remotely.
- Knowledge: High.
- Anxiety: Medium when status is ambiguous.
- Expected action: Check status, guide local operator, decide update/reconfig.
- Likely error: Confusing content wait with player failure.
- Needed feedback: Public status, timeline, sanitized categories.
- Criticality: High.

### Espectador passivo

- Goal: See content, not infrastructure.
- Knowledge: Low.
- Anxiety: Low, but technical screens break trust.
- Expected action: None.
- Likely error: Treating black screen or login as product failure.
- Needed feedback: Content or clean wait message.
- Criticality: Medium.

### Cliente que recebe o equipamento

- Goal: Receive a finished-feeling product.
- Knowledge: Low.
- Anxiety: High if first setup needs support.
- Expected action: Watch install or use configured device.
- Likely error: Thinking boot/update wait is broken.
- Needed feedback: Clean, consistent visual states.
- Criticality: High.

### Tecnico remoto

- Goal: Recover and maintain safely.
- Knowledge: High.
- Anxiety: High when logs lack categories.
- Expected action: Use SSH, updater and sanitized probes.
- Likely error: Collecting too much data or using destructive flow.
- Needed feedback: Safe status contracts and guardrails.
- Criticality: Critical.

### Backend/API

- Goal: Provide playlist/config data.
- Knowledge: System.
- Anxiety: None.
- Expected action: Respond or fail observably.
- Likely error: Timeout without public category.
- Needed feedback: `waiting_for_api`, cache/fallback/error categories.
- Criticality: High.

### Appliance autonomo

- Goal: Keep the product surface safe.
- Knowledge: System.
- Anxiety: None.
- Expected action: Boot, show state, play, update, recover.
- Likely error: No feedback, TTY/DRM fight, raw technical screen.
- Needed feedback: Public state machine and minimal visual feedback.
- Criticality: Critical.

## Practical Use

Every journey and screen should identify the primary actor. A design is not
accepted only because it is technically correct; it must reduce the most likely
confusion for the actor who sees that state.

The installer and remote technician are the highest-risk actors during setup.
The spectator and customer are the highest-risk actors during normal operation:
they cannot distinguish a valid wait from a defect unless the appliance tells
them.
