# Systemd dev autoboot - kiosky-player

Data: 2026-04-30

Placa: desenvolvimento, IP redigido.

HDMI: conectado durante toda a rodada.

## Objetivo

Preparar e validar boot automatico controlado do `kiosky-player.service` na
placa de desenvolvimento, mantendo HDMI conectado e sem executar ainda o teste
de HDMI ausente.

## Estrategia para HDMI ausente

Foi adicionado um launcher de servico que roda como `totem` e verifica
periodicamente os status DRM em `/sys/class/drm`.

- Se algum display estiver `connected`, o launcher inicia o app normalmente.
- Se nenhum display estiver `connected`, o launcher registra `display_missing`,
  atualiza um status JSON simples e aguarda antes de tentar de novo.
- Nesse estado o app/MPV nao e iniciado, evitando crash loop por falha de
  inicializacao DRM/KMS.
- O servico permanece controlavel por `systemd`.

O teste com HDMI fisicamente ausente nao foi executado nesta rodada.

## Unit e launcher

- Unit: `kiosky-player.service`.
- Launcher: `kiosky_service_launcher.sh`.
- Usuario/grupo do servico: `totem:totem`.
- Working directory do app preservado.
- Runtime temporario criado antes do start.
- Desktop, compositor, Xorg e Wayland nao foram adicionados.
- TTY hacks nao foram adicionados.
- Hardening de `/opt` somente leitura para o servico foi preservado.

Validacoes locais antes do deploy:

| Item | Resultado |
| --- | --- |
| `bash -n` do launcher | OK |
| `bash -n` em scripts de board/remote | OK |
| `systemd-analyze verify` da unit | OK |
| `git diff --check` | OK |

## Deploy e smoke antes do enable

Estado apos deploy e `daemon-reload`:

| Item | Resultado |
| --- | --- |
| `systemctl is-enabled` | `disabled` |
| `systemctl is-active` | `inactive` |
| DRM conectado | 1 |

Smoke de 60s antes do `enable`:

| Item | Resultado |
| --- | --- |
| Servico apos start | `active` |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |
| Launcher status | `running`, display conectado |
| App status | `playing`, MPV rodando |
| Falhas consecutivas | 0 |
| Midias bloqueadas | 0 |
| `last_poll_error` / `last_render_error` / risco de tela preta | ausentes |
| `systemctl --failed` | 0 units |
| Filtro critico de kernel bloqueante | 0 |
| Escrita no diretorio do app apos marcador | 0 |
| Processos remanescentes apos stop | 0 |

## Enable

`systemctl enable kiosky-player.service` foi executado apos o smoke de 60s
passar.

Estado confirmado: `enabled`.

## Reboot cycle 1

Validacao essencial apos boot:

| Item | Resultado |
| --- | --- |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |
| DRM conectado | 1 |
| Launcher status | `running`, display conectado |
| App status | `playing`, MPV rodando |
| Falhas consecutivas | 0 |
| Midias bloqueadas | 0 |
| `display_missing` no journal da janela | 0 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| Restarting MPV | 0 |
| Failed to load media | 0 |
| Falha DRM/KMS/GPU | 0 |
| `systemctl --failed` | 0 units |
| Filtro critico de kernel bloqueante | 0 |

Observer curto de 180s:

Artefato: `kiosky-service-observer-20260430-184850-0300.tar.gz`

| Metrica | Valor |
| --- | ---: |
| Amostras | 179 |
| IPC success | 179 |
| IPC timeout | 0 |
| IPC error | 0 |
| Aliases observados | 5 |
| Aliases com `time-pos` e frame avancando | 5/5 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| Restarting MPV | 0 |
| Failed to load media | 0 |
| `systemctl --failed` apos observer | 0 units |
| Filtro critico de kernel bloqueante | 0 |
| Escrita no diretorio do app apos marcador | 0 |
| Processos remanescentes apos stop do observer | 0 |

## Reboot cycle 2

Validacao essencial apos boot:

| Item | Resultado |
| --- | --- |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |
| DRM conectado | 1 |
| Launcher status | `running`, display conectado |
| App status | `playing`, MPV rodando |
| Falhas consecutivas | 0 |
| Midias bloqueadas | 0 |
| `display_missing` no journal da janela | 0 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| Restarting MPV | 0 |
| Failed to load media | 0 |
| Falha DRM/KMS/GPU | 0 |
| `systemctl --failed` | 0 units |
| Filtro critico de kernel bloqueante | 0 |

Observer opcional de 120s:

Artefato: `kiosky-service-observer-20260430-185448-0300.tar.gz`

| Metrica | Valor |
| --- | ---: |
| Amostras | 120 |
| IPC success | 120 |
| IPC timeout | 0 |
| IPC error | 0 |
| Aliases observados | 5 |
| Aliases com `time-pos` e frame avancando | 5/5 |
| MPV IPC command timeout | 0 |
| MPV IPC ping failed | 0 |
| Restarting MPV | 0 |
| Failed to load media | 0 |
| `systemctl --failed` apos observer | 0 units |
| Filtro critico de kernel bloqueante | 0 |
| Escrita no diretorio do app apos marcador | 0 |
| Processos remanescentes apos stop do observer | 0 |

## Diagnostico final

Artefato: `totem-diag-20260430-185814-0300.tar.gz`

Apos o observer opcional, o servico foi iniciado novamente para deixar a placa
em estado operacional:

| Item | Resultado |
| --- | --- |
| Estado final de enable | `enabled` |
| Estado final do servico | `active` |
| `kiosk.py` final | 1 processo |
| `mpv` final | 1 processo |
| Launcher final | `running`, display conectado |
| App final | `playing`, MPV rodando |
| `systemctl --failed` final | 0 units |
| Filtro critico de kernel final | 0 |

## Conclusao

Aprovado.

O `kiosky-player.service` foi habilitado para boot automatico na placa de
desenvolvimento e subiu corretamente em dois reboots controlados com HDMI
conectado. A estrategia de HDMI ausente foi implementada no launcher, mas a
validacao fisica sem HDMI fica para rodada separada.

## Proximos passos

- Teste HDMI ausente em rodada separada, sem alterar a placa de homologacao.
- Teste manual mais longo em fase de homologacao 2.
- Inicio do trabalho de splash/onboarding se a proxima rodada nao revelar
  regressao.
