# Marco de desenvolvimento - status/splash

Status: marco de desenvolvimento pos-RC1. Nao e homologacao e nao libera
producao.

Data: 2026-05-01

## Objetivo

Consolidar o ponto atual da frente status/splash depois da definicao da
homologacao `v0.1-rc1`. O marco registra o que foi validado na placa de
desenvolvimento, o que ficou preservado como evidencia historica, e qual deve
ser a proxima fase: C0, planejamento do onboarding Wi-Fi/configuracao.

Este documento nao altera a historia das rodadas anteriores. Quando uma
hipotese antiga foi superada, ela permanece preservada no documento original e
e contextualizada aqui como superada por evidencia posterior.

## Relacao com a homologacao v0.1-rc1

A homologacao `v0.1-rc1` continua sendo uma frente separada. Ela congela a
configuracao candidata validada no app real por 300s, ainda sem `systemd` da
aplicacao:

- `mpv_query_uses_fresh_ipc=true`;
- `mpv_vo=gpu`;
- `mpv_gpu_context=drm`;
- `mpv_ao=null`;
- `low_resource_mode=false`.

Referencia: [Homologacao v0.1-rc1](../releases/v0.1-rc1-homologacao/README.md).

O desenvolvimento status/splash usa essa base tecnica como antecedente, mas nao
altera o escopo da RC1 e nao deve ser tratado como homologado para producao.

## Linha de corte

### Ate RC1

- Base Armbian Candidato A validada em bancada.
- Runtime minimo sem desktop, compositor, Xorg, Wayland ou Chromium.
- MPV via DRM/KMS direto.
- `kiosky-player` manual como usuario `totem`.
- IPC/watchdog/loadfile estabilizados por `mpv_query_uses_fresh_ipc=true`.
- Saida MPV explicita `--vo=gpu --gpu-context=drm --ao=null`.
- Observer do app real por 300s aprovado.
- Homologacao pendente em segunda placa/cartao.

### Pos-RC1 em desenvolvimento

- `kiosky-player.service` validado com `systemd` start/stop.
- Boot automatico validado na placa de desenvolvimento.
- HDMI ausente/reconexao validado.
- Launcher passou a publicar `display_missing`.
- Status aggregator criado e integrado ao launcher.
- Refresh periodico de status agregado validado.
- `config_missing` validado sem iniciar `kiosk.py` nem MPV principal.
- Renderer visual Dadooh validado para `config_missing`.
- B1 visual "Configuracao pendente" validado por observacao humana.
- Player e renderer nao rodam juntos no caminho validado.
- Ao restaurar config valida, o sistema volta para `player_running`.

### Producao futura

Ainda nao ha liberacao de producao. Permanecem pendentes homologacao completa,
teste longo, root read-only, corte seco, Wi-Fi/setup, ativacao backend,
monitoramento, update/rollback e criterios operacionais de campo.

## Capacidades aprovadas em desenvolvimento

- `systemd` start/stop controlado do `kiosky-player.service`.
- Boot automatico na placa de desenvolvimento com HDMI conectado.
- Tratamento de HDMI ausente/reconexao sem iniciar app/MPV enquanto nao ha
  display.
- Status aggregator publico e sanitizado em `/tmp/dadooh-status/status.json` e
  `/tmp/dadooh-status/status.svg`.
- Refresh periodico do status agregado enquanto o player esta vivo.
- Estado `config_missing` antes de iniciar o player.
- Renderer visual Dadooh para `config_missing`, separado do MPV principal.
- Tela B1 "Configuracao pendente" validada visualmente em desenvolvimento.

## Evidencias principais

| Evidencia | Leitura atual |
| --- | --- |
| [Observer com saida MPV explicita](../evidence/candidate-a/runs/20260430-133130-kiosky-playback-observer-explicit-mpv-output/README.md) | Base da RC1: app real aprovado por 300s com IPC/loadfile estaveis e 5/5 aliases avancando. |
| [Systemd dev smoke](../evidence/candidate-a/runs/20260430-174718-systemd-dev-smoke/README.md) | Start/stop controlado aprovado na placa de desenvolvimento com HDMI conectado. |
| [Systemd dev autoboot](../evidence/candidate-a/runs/20260430-185824-systemd-dev-autoboot/README.md) | Boot automatico aprovado em dois reboots controlados com HDMI conectado. |
| [Systemd dev HDMI missing](../evidence/candidate-a/runs/20260430-194110-systemd-dev-hdmi-missing/README.md) | Boot sem HDMI publica `display_missing`, nao inicia app/MPV e inicia apos reconexao. |
| [Status aggregator refresh HDMI](../evidence/candidate-a/runs/20260501-132142-status-aggregator-refresh-hdmi/README.md) | Refresh A1.2.1 converge o status agregado para `player_running` apos reconexao. |
| [Status aggregator config_missing](../evidence/candidate-a/runs/20260501-141332-status-aggregator-config-missing/README.md) | Config ausente/invalida gera `config_missing`, servico ativo e player parado. |
| [Status renderer config_missing](../evidence/candidate-a/runs/20260501-145916-status-renderer-config-missing/README.md) | Renderer Dadooh exibiu `config_missing` sem rodar junto com o player. |
| [Status renderer visual B1](../evidence/candidate-a/runs/20260501-190932-status-renderer-visual-b1/README.md) | Tela B1 foi observada por humano e restaurou para `player_running` com observer curto limpo. |

## Decisoes aceitas neste marco

- `systemd` inicia um launcher, nao diretamente o player como unico processo de
  decisao.
- O launcher supervisiona display, config e player antes de entregar DRM/KMS ao
  MPV principal.
- O status aggregator publica somente estado publico sanitizado.
- O renderer visual so roda quando o player nao deve rodar.
- O renderer deve parar antes do MPV principal iniciar.
- `config_missing` mostra tela Dadooh de configuracao pendente.
- `display_missing` nao tenta renderizar sem display fisico.
- Chromium, compositor, Xorg e Wayland continuam fora deste caminho.
- O `kiosky-player` nao vira configurador de Wi-Fi/ativacao.

## Documentos historicos superados, mas preservados

Alguns documentos antigos tratam IPC/watchdog como bloqueio principal. Eles
foram corretos no momento em que foram escritos, porque as evidencias
disponiveis apontavam para timeouts IPC, restarts e falhas de `loadfile`.

Esses documentos nao devem ser reescritos para parecerem atuais:

- [Hipoteses MPV IPC e watchdog](../app-integration/03_HIPOTESES_MPV_IPC_WATCHDOG.md);
- [Evolucao MPV IPC/watchdog](../app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md);
- [A/B timeout IPC 5s](../evidence/candidate-a/runs/20260429-174349-kiosky-manual-probe-ipc-timeout-5s/README.md);
- [Watchdog threshold 2](../evidence/candidate-a/runs/20260429-194954-kiosky-manual-probe-watchdog-threshold-2/README.md);
- [Coordenacao IPC/restart](../evidence/candidate-a/runs/20260429-210204-kiosky-manual-probe-ipc-restart-coordination/README.md);
- [MPVController playlist probe](../evidence/candidate-a/runs/20260430-011115-mpv-controller-playlist-probe/README.md).

Estado atual: a hipotese de IPC/watchdog como bloqueio principal foi superada
pela combinacao posterior de:

- `mpv_query_uses_fresh_ipc=true`;
- saida MPV explicita `--vo=gpu --gpu-context=drm --ao=null`;
- `systemd`/launcher supervisionando display e config;
- status/splash publico para estados em que o player nao deve rodar.

## Riscos remanescentes

- O filtro amplo de kernel da rodada B1 teve ruido nao bloqueante, mas deve ser
  revisado antes de qualquer decisao de producao.
- Teste longo fica para homologacao 2.
- `player_error` visual ainda nao foi validado operacionalmente.
- Renderer e MPV principal continuam disputando DRM/KMS se a ordem de parada
  for quebrada.
- Campos novos de status podem vazar dados privados se sairem da allowlist.
- Wi-Fi/setup, hotspot, portal e ativacao backend ainda nao foram implementados.
- Root read-only e corte seco ainda nao foram validados.
- Monitoramento, update e rollback ainda estao pendentes.

## Criterios de nao regressao

- `display_missing` nao inicia `kiosk.py`, MPV principal ou renderer.
- `config_missing` nao inicia `kiosk.py` nem MPV principal.
- `player_running` nao mantem renderer ativo.
- Renderer encerra antes de qualquer inicio do player.
- Se o renderer nao parar, o launcher bloqueia o player e registra erro
  controlado.
- `status.json` e `status.svg` continuam sem secrets, URLs privadas, IDs
  privados, payloads privados, SSID, IP publico, paths reais ou nomes privados.
- Restaurar config valida volta para `player_running`.
- Observer curto apos restauracao mantem IPC timeout `0` e aliases avancando.
- `systemctl --failed` permanece em `0`.
- Nenhum pacote grafico novo e instalado.
- Nenhuma mudanca no `kiosky-player` e exigida por este marco.

## Ainda nao implementado

- Wi-Fi setup.
- Hotspot.
- Portal local.
- Ativacao backend.
- Reset real.
- Manutencao operacional.
- Telemetria.
- Root read-only.
- Corte seco.
- Producao.

## Proxima fase recomendada

C0: planejamento do onboarding Wi-Fi/configuracao.

C0 deve especificar fluxo, seguranca, estados publicos, limites de dados
sensiveis, criterios de rollback e plano de teste antes de qualquer
implementacao de hotspot, portal local, ativacao backend ou escrita real de
config por operador.
