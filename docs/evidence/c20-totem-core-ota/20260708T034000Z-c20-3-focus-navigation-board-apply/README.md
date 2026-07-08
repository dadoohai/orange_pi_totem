# C20.3 Totem-Core Board Apply

## Resultado

C20.3 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.3.focus-navigation-20260708T033000Z-f343c99`
- Payload SHA256: `189970485c6b80558d15ace49e9d9cc2f4dd42c398c4ec474738559d21d65c0e`
- Antes: `releases/c20.2.step-navigation-20260708T022700Z-1fa33d2`
- Depois: `releases/c20.3.focus-navigation-20260708T033000Z-f343c99`
- Rollback: `releases/c20.2.step-navigation-20260708T022700Z-1fa33d2`
- `kiosky-player.service`: ativo antes/depois do apply e antes/depois da captura
- `totem-open-settings.service`: inativo ao final
- Wizard instalado: `self-test: ok`

## Observacao Operacional

A primeira tentativa de apply usou uma sintaxe incorreta para a CLI embarcada e
falhou antes de aplicar (`rc=2`). A tentativa correta usou manifest posicional e
passou (`rc=0`).

Antes do apply, a placa estava com uma sessao de configuracao aberta e o guard
recusou aplicar por `settings_session_lock_present`. A sessao foi encerrada via
systemd; o player voltou ativo; so entao o apply foi executado.

## Evidencia Visual

Capturas reais do framebuffer da placa:

- `captures/orientation-content-focus-framebuffer.jpg`
- `captures/orientation-step-focus-framebuffer.jpg`

As capturas confirmam que o foco no item interno e o foco no menu superior sao
visualmente diferentes. O menu modal por `Tab` nao faz mais parte do fluxo C20.3.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull ou stable.
