# Systemd dev HDMI missing

Data: 2026-04-30

Placa: desenvolvimento, IP redigido.

## Objetivo

Validar fisicamente a estrategia do launcher para HDMI ausente no
`kiosky-player.service`, sem tocar na placa de homologacao.

Estrategia esperada:

- Com display conectado, o launcher inicia o app.
- Sem display conectado, o launcher registra `display_missing` e aguarda.
- Sem display, `kiosk.py` e MPV nao devem iniciar.
- O servico deve permanecer controlavel por `systemd`.

## Passos fisicos

1. Estado inicial validado com HDMI conectado.
2. Operador desconectou fisicamente o HDMI.
3. A placa foi reiniciada sem HDMI.
4. Operador reconectou fisicamente o HDMI.
5. A reconexao foi validada com app e MPV ativos.

## Estado inicial com HDMI

| Item | Resultado |
| --- | --- |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `systemctl --failed` | 0 units |
| DRM conectado | 1 |
| Launcher | `running`, display conectado |
| App status | `playing`, MPV rodando |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |
| Falhas consecutivas | 0 |
| Midias bloqueadas | 0 |
| Erro de poll/render/risco de tela preta | ausente |
| Kernel critico | 0 |
| Filtro bloqueante de kernel | 0 |

## Boot sem HDMI

Apos o operador desconectar o HDMI, foi executado `sync` e reboot controlado.
Com SSH de volta, o estado observado foi:

| Item | Resultado |
| --- | --- |
| Uptime no snapshot | 88s |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `systemctl --failed` | 0 units |
| DRM conectado | 0 |
| DRM HDMI | `disconnected` |
| Launcher status | `display_missing` |
| Launcher `display_connected` | `false` |
| `kiosk.py` | 0 processos |
| `mpv` | 0 processos |
| App status em `/tmp` | ausente |
| `display_missing` no journal do boot | 2 |
| `starting_app` no journal do boot | 0 |
| Falha KMS/GPU no journal do boot | 0 |
| Erros do servico no journal do boot | 0 |
| Kernel critico | 0 |
| Filtro bloqueante de kernel | 0 |

Nao houve evidencia de restart loop agressivo: o launcher iniciou uma vez,
manteve o servico `active` e apenas aguardou display conectado.

## Reconexao HDMI

Apos o operador reconectar o HDMI, a primeira checagem ja mostrou:

| Item | Resultado |
| --- | --- |
| DRM conectado | 1 |
| Launcher | `running`, display conectado |
| App status | `playing`, MPV rodando |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |

Depois do observer, o servico foi reiniciado para deixar a placa em estado
operacional:

| Item | Resultado |
| --- | --- |
| Estado antes do restart controlado | `inactive` |
| Processos antes do restart | `kiosk.py=0`, `mpv=0` |
| Estado final de enable | `enabled` |
| Estado final do servico | `active` |
| Processos finais | `kiosk.py=1`, `mpv=1` |
| DRM conectado final | 1 |
| Launcher final | `running`, display conectado |
| App final | `playing`, MPV rodando |
| Falhas consecutivas finais | 0 |
| Midias bloqueadas finais | 0 |
| Erro de poll/render/risco de tela preta final | ausente |

## Observer apos reconexao

Artefato: `kiosky-service-observer-20260430-195058-0300.tar.gz`

O observer planejado era curto, mas nesta execucao rodou com o padrao do script
de 10 minutos. O resultado e uma validacao mais longa do que a janela minima
pedida.

| Metrica | Valor |
| --- | ---: |
| Amostras | 597 |
| IPC success | 597 |
| IPC timeout | 0 |
| IPC error | 0 |
| Aliases observados | 5 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| MPV IPC ping ok | 60 |
| Restarting MPV | 0 |
| MPV process started durante observer | 0 |
| Failed to load media | 0 |
| MPV loadfile returned error | 0 |
| Falha KMS/GPU no journal | 0 |
| Traceback/ERROR no journal | 0 |

Tabela por alias sanitizado:

| Alias | Duracao configurada (ms) | Duracao MPV (s) | `time-pos` min | `time-pos` max | `time-pos` avancou? | Frame min | Frame max | Frame avancou? | Pause? | Idle? | EOF? | Amostras |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | ---: |
| `<media-path:89207012a7>` | 7000 | 16.064218 | 0.000000 | 6.866667 | Sim | 0 | 206 | Sim | Nao | Nao | Nao | 91 |
| `<media-path:8f9272521c>` | 8600 | 8.568186 | 0.000000 | 8.416667 | Sim | 0 | 201 | Sim | Nao | Nao | Nao | 113 |
| `<media-path:c406539999>` | 15100 | 15.069751 | 0.000000 | 14.900000 | Sim | 0 | 447 | Sim | Nao | Nao | Nao | 196 |
| `<media-path:e7efe47f02>` | 10000 | 10.000000 | 0.066667 | 9.833333 | Sim | 2 | 295 | Sim | Nao | Nao | Nao | 129 |
| `<media-path:fece6ae2c0>` | 5100 | 5.131610 | 0.000000 | 4.916667 | Sim | 0 | 118 | Sim | Nao | Nao | Nao | 68 |

O observer parou o servico ao final para confirmar cleanup. Resultado: 0
processos `kiosk.py`/`mpv` do usuario `totem` apos stop. A unica linha em
`post-processes-all` e o proprio comando de verificacao `pgrep`.

## Diagnostico final

Artefato: `totem-diag-20260430-200141-0300.tar.gz`

| Item | Resultado |
| --- | --- |
| `systemctl --failed` | 0 units |
| `journalctl -k -p crit` | sem entradas |
| Filtro critico de kernel | apenas ruido de boot conhecido; sem bloqueador |
| Escrita em `/opt/totem/kiosky-player` durante observer | 0 |

Nao foram observados `Oops`, `panic`, erro EXT4, remount read-only ou
timeout/reset de MMC.

## Conclusao

Aprovado.

A estrategia de HDMI ausente funcionou como esperado na placa de
desenvolvimento: no boot sem HDMI o servico permaneceu `active`, o launcher
registrou `display_missing`, e app/MPV nao iniciaram. Apos reconectar o HDMI, o
launcher iniciou o app, o status voltou para `playing` com MPV rodando, e todos
os aliases avancaram no observer.

## Recomendacao

Usar esta estrategia como base da proxima rodada de homologacao. O proximo
passo recomendado e repetir a validacao de HDMI ausente na placa/cartao de
homologacao quando ela estiver reservada para esse teste, mantendo o mesmo
criterio: sem app/MPV no boot sem HDMI, inicio automatico ao reconectar e
observer limpo apos reconexao.
