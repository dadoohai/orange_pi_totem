# C19.2 Esc Clean Cycles

Data: 2026-07-07.

Objetivo: validar na placa real que sair do wizard com `Esc` a partir da tela
inicial encerra a sessao de settings sem deixar `totem-open-settings.service`
em estado `failed`, restaurando o player.

Resultado:

- ciclo 1: `Result=success`, `ExecMainStatus=0`, `ActiveState=inactive`;
- ciclo 2: `Result=success`, `ExecMainStatus=0`, `ActiveState=inactive`;
- nos dois ciclos: `kiosky-player.service=active`, MPV vivo, lock ausente,
  request ausente, `PLAYER_STATUS=playing`;
- `systemctl is-failed` nao acusou falha em nenhum ciclo.
- status final da sessao confirma `setup_cancelled=true`,
  `real_config_written=false` e `wifi_changed=false`.

Artefatos principais:

- `status-1-after-escape.txt`;
- `status-2-after-escape.txt`;
- `operation.log`;
- `1-opened-visible.jpg`;
- `2-opened-visible.jpg`;
- `session-status-final.json`;
- `setup-cancelled-final.json`;
- `captures.tgz`.
