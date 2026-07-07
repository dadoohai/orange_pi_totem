# C19.3 Signal ASCII Preview Burst

Data: 2026-07-07.

Objetivo: validar no renderer real da placa que o indicador de sinal Wi-Fi nao
aparece mais como `????`.

Resultado:

- captura `burst-1-visible.jpg` mostra a lista Wi-Fi;
- indicador aparece como ASCII (`[####]`, `[###.]`, `[##..]`) em vez de
  `????`;
- lista segue com 4 redes por pagina em paisagem;
- teste nao aplicou Wi-Fi nem escreveu config;
- estado final: `PLAYER_AFTER=active`, `MPV_AFTER=1`.

Artefatos principais:

- `burst-1-visible.jpg`;
- `status-before.txt`;
- `status-after.txt`;
- `operation.log`;
- `captures.tgz`.
