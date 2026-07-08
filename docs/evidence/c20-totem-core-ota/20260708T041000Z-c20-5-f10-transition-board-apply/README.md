# C20.5 Totem-Core Board Apply

## Resultado

C20.5 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.5-f10-transition-timeout-20260708T040500Z-6ef0b0b`
- Payload SHA256: `fcef52866f6d723f416e6525502b355cab1cc5ab4739e14e60385209a471edad`
- Antes: `releases/c20.4-f10-tty-guard-timeout-20260708T035500Z-d54341d`
- Depois: `releases/c20.5-f10-transition-timeout-20260708T040500Z-6ef0b0b`
- Rollback: `releases/c20.4-f10-tty-guard-timeout-20260708T035500Z-d54341d`

## Diagnostico

C20.4 corrigiu o bloqueio no `ExecStartPre`, mas a abertura real ainda podia
parar dentro de `totem_open_settings_session.sh`, no `show_transition`, porque o
script escrevia diretamente em `/dev/tty2`.

C20.5 protege `chvt`, limpeza do TTY, escrita de texto e splash visual com
timeouts curtos. O settings service passou do `ExecStartPre`, entrou na sessao
interativa e abriu o wizard real via `openvt`.

## Evidencia

- `board/apply-local.txt`: apply governado com `apply_success`.
- `board/open-settings-progress-test.txt`: `totem_setup_visual_wizard.py` visto
  em execucao no `tty2`.
- `captures/f10-wizard-open-framebuffer.jpg`: captura real do framebuffer com o
  wizard aberto.

## Estado Operacional

O teste deixou o wizard aberto para confirmacao do operador, porque o incidente
reportado era justamente o F10 nao abrir Configuracoes.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull ou stable.
