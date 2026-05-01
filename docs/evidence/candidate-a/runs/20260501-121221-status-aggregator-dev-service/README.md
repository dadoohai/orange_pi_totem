# Status aggregator dev service

Data: 2026-05-01

Placa: desenvolvimento, IP redigido.

## Objetivo

Validar A1.2 na placa de desenvolvimento: launcher chamando o agregador de
status apenas para gerar `/tmp/dadooh-status/status.json` e
`/tmp/dadooh-status/status.svg`, sem renderer visual, sem MPV extra e sem
acesso direto a DRM/KMS.

## Arquivos implantados

- `totem_status_aggregate.py` em `/opt/totem/bin`;
- `totem_status_render_preview.py` em `/opt/totem/bin`;
- `kiosky_service_launcher.sh` em `/opt/totem/bin`;
- `kiosky-player.service` em `/etc/systemd/system`.

Foi executado `systemctl daemon-reload`. Nao houve alteracao de enable/disable.

## Timeout do agregador

O launcher usa `TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC` com padrao de 2 segundos.
Falha, ausencia ou timeout do agregador sao best-effort: geram warning
rate-limited e nao interrompem o fluxo principal do launcher.

Na rodada real do servico:

| Warning | Contagem |
| --- | ---: |
| `status_aggregator_unavailable` | 0 |
| `status_aggregator_timeout` | 0 |
| `status_aggregator_failed` | 0 |

## Rejeicao de `/tmp`

Validado manualmente na placa:

- `/tmp/dadooh-status-test` gerou `status.json` e `status.svg`;
- `--out-dir /tmp` foi rejeitado pelo agregador.

## Servico usado

Servico: `kiosky-player.service`.

Estado final:

| Item | Resultado |
| --- | --- |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |

## Status gerado

Arquivos confirmados:

- `/tmp/dadooh-status/status.json`;
- `/tmp/dadooh-status/status.svg`.

Campos publicos observados apos restart do servico:

| Campo | Valor |
| --- | --- |
| `schema_version` | `totem-status.v0` |
| `state` | `player_running` |
| `display_connected` | `true` |
| `config_state` | `valid` |
| `player_state` | `running` |
| `service_state` | `active` |
| `error_code` | `null` |
| `public_message` | `Exibicao em andamento` |
| `action_hint` | `Nenhuma acao necessaria.` |

## Stop/start controlado

Apos `systemctl stop kiosky-player.service` e espera de 5 segundos:

| Item | Resultado |
| --- | --- |
| `kiosk.py` | 0 processos |
| `mpv` | 0 processos |
| status agregado | `maintenance_placeholder` |
| `player_state` | `stopped` |
| `service_state` | `inactive` |

Apos `systemctl start kiosky-player.service` e espera de 30 segundos:

| Item | Resultado |
| --- | --- |
| `systemctl is-active` | `active` |
| status agregado | `player_running` |
| `kiosk.py` | 1 processo |
| `mpv` | 1 processo |

## Sanitizacao

Checagem automatica no `status.svg` nao encontrou:

- `api_key`;
- `api_url`;
- `environment_id`;
- `station_id`;
- payload privado;
- paths privados de midia/config;
- IP privado.

Somente campos publicos do `status.json` foram copiados para este README.

## Diagnostico

Artefato bruto coletado e mantido ignorado pelo Git:

- `totem-diag-20260501-121208-0300.tar.gz`

## Systemd e kernel

| Checagem | Resultado |
| --- | ---: |
| `systemctl --failed` | 0 units |
| `journalctl -k -p crit` | 0 entradas |
| filtro amplo de kernel | 10 linhas |

Resumo do filtro amplo: tokens `Error` e `thermal` apareceram no boot atual.
Nao houve falha de servico, processo remanescente, erro critico de kernel ou
regressao observada no player durante esta rodada. O detalhe bruto fica no
diagnostico ignorado pelo Git.

## Conclusao

Aprovado na placa de desenvolvimento.

O hardening local funcionou na placa: `/tmp` foi rejeitado como saida, o
agregador gerou `status.json` e `status.svg`, e o launcher continuou operando
com o player em `player_running`. Stop/start controlado nao deixou processos
remanescentes e o servico voltou a reproduzir.

## Proximo passo recomendado

Revisao humana do diff e commit. Depois, executar uma rodada especifica de HDMI
ausente/reconexao com o agregador integrado, ainda sem renderer visual.
