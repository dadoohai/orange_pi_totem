# C20.4 Totem-Core Board Apply

## Resultado

C20.4 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.4-f10-tty-guard-timeout-20260708T035500Z-d54341d`
- Payload SHA256: `12140293c9afb6728aba898ea8b7ef61d550e2795a1a2d380373ff4d2fc382db`
- Antes: `releases/c20.3.focus-navigation-20260708T033000Z-f343c99`
- Depois: `releases/c20.4-f10-tty-guard-timeout-20260708T035500Z-d54341d`
- Rollback: `releases/c20.3.focus-navigation-20260708T033000Z-f343c99`

## Diagnostico

A falha original foi reproduzida: o F10 gerava request, mas
`totem-open-settings.service` ficava preso no `ExecStartPre` de
`totem_visual_tty_guard.sh`.

C20.4 corrigiu esse primeiro bloqueio: o `ExecStartPre` passou com
`status=0/SUCCESS`.

## Limite Encontrado

O teste de abertura real revelou um segundo bloqueio dentro de
`totem_open_settings_session.sh`, no `show_transition`, que ainda escrevia
diretamente em `/dev/tty2`. Essa segunda parte e corrigida na rodada C20.5.

## Escopo

Esta rodada atualiza apenas `totem-core`. Nao altera player-runtime, MPV,
midias, config de cliente, kernel, auto-pull ou stable.
