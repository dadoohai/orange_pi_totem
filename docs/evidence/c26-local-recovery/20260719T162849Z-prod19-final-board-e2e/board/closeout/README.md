# C26 board closeout probes

These probes supplement the destructive prod19 campaign without repeating its
restart, restore, power-cut or poweroff operations.

## Real input and safe exits

- A temporary Linux uinput keyboard was enumerated by the installed settings
  trigger and held `F10` for six seconds. The system journal then records the
  real `totem-open-settings` unit starting. This proves the kernel input and
  production trigger path; it is not represented as a human keypress.
- `Reiniciar` and `Restaurar` confirmations opened with `Cancelar` selected.
  Pressing Enter on that default left boot ID, updater links/state, config,
  orientation, reset state and terminal units unchanged.
- Escape from the restore confirmation returned without mutation.
- Holding Enter on the restart confirmation did not execute the destructive
  action or escape the confirmation. The screen still showed `Cancelar`
  selected and all compared state remained identical.
- The session exited normally with `q`; `totem-open-settings` finished with
  status zero and the player remained active with zero restarts.

## Concurrency guard

While the F10 settings session held the update lock, a governed
`totem-updatectl rollback --component totem-core` returned `rc=40`
(`update_lock_busy`). Current, previous and updater state were byte-identical
before and after.

## Boot contract

The live boot probe records an enabled, successful firstboot gate ordered
before both update agents, a root-only ready marker bound to the current boot
ID and a passing `c26-product-reset-gc-static-v1` image-contract check.

## Auto-pull observation

`core-agent-live.txt` preserves a negative operational observation. The timer
is enabled and waiting, but its last oneshot run selected public stable C21.24,
which is older than embedded C26.16. The updater rejected it without mutation
using `rc=45`; systemd consequently marks the oneshot failed and the system
degraded. Player health is unaffected. This is not called a successful no-op
and must receive an explicit final disposition.

The framebuffer images in this directory were visually inspected. They contain
no pairing code, QR payload, credential or customer data.
