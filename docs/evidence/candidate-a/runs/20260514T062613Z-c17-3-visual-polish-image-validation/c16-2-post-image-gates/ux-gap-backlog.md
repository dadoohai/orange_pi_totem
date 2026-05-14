# C16.2 UX Gap Backlog

## Summary

- P0: 0
- P1 inherited gates: 5
- P1 journeys flagged: 9
- Worst journey: T - Estado sem cache (3.6/5)
- Worst screen: wifi_list (4.3/5)
- Synthetic user runs below 3.5: 10

## P0

None.

## P1

### P1-001 - Negative API/cache/content scenarios

- gate: C17-GATE-API-CACHE-CONTENT
- decision: vira gate C17
- journeys: G, I, K, R, T
- can_be_tested_by_remote_update: true
- notes: C18 fica restrito a timing/sync/duration/loop.

### P1-002 - Wi-Fi wrong password / weak Wi-Fi

- gate: C17-GATE-WIFI-NEGATIVE
- decision: vira gate C17
- journeys: E, F
- can_be_tested_by_remote_update: true
- notes: C16.2 cobre galeria e output sintetico; C17 valida runtime se autorizado.

### P1-003 - Update UX path

- gate: C17-GATE-UPDATE-UX
- decision: vira gate C17
- journeys: M, N
- can_be_tested_by_remote_update: true
- notes: Nao aplicar release real durante a simulacao de UX.

### P1-004 - HDMI/camera methodology

- gate: SCALE-GATE-HDMI-CAMERA
- decision: opcional antes de C17, obrigatorio antes de escala
- journeys: A, B, C, H, I, J, K, R, T
- can_be_tested_by_remote_update: false
- notes: SSH/timeline nao substitui percepcao visual final.

### P1-005 - Wizard visual consistency

- gate: C17-GATE-WIZARD-VISUAL-CONSISTENCY
- decision: vira gate C17 por galeria + rubrica
- journeys: C, D, E, F, H
- can_be_tested_by_remote_update: true
- notes: C16.2 deve bloquear C16.4 apenas se tela critica ficar abaixo de 4.

## P2

- Keep HDMI/camera methodology as scale gate if C17 runs without it.
- Keep C18 reserved for player timing/sync/duration/loop.
- Refine support runbook after C17 status evidence.

## P3

- Evolve visual design system after C17 image validation.
