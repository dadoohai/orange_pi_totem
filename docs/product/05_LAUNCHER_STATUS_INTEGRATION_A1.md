# Launcher status integration A1.2

Status: implementacao local para revisao. Nao altera systemd, player ou placa.

Data: 2026-05-01

## Objetivo

Integrar o agregador de status sanitizado ao launcher apenas para gerar
arquivos publicos em `/tmp`. Esta etapa ainda nao exibe nada na tela, nao
inicia renderer, nao inicia MPV adicional e nao acessa `/dev/dri`.

O comportamento operacional esperado do launcher permanece o mesmo: detectar
HDMI, iniciar o `kiosky-player` quando houver display e manter
`display_missing` sem app/MPV quando nao houver display.

## Pontos de chamada

O launcher chama `totem_status_aggregate.py` dentro de `write_status`, depois
que o JSON bruto do launcher e gravado com sucesso.

Com isso, o agregador roda nos estados ja cobertos por `write_status`:

- `starting`;
- `display_missing`;
- `running`;
- `app_exited`;
- `stopped`.

## Arquivos gerados

O agregador recebe o caminho do status bruto recem gravado e escreve:

- `/tmp/dadooh-status/status.json`;
- `/tmp/dadooh-status/status.svg`.

O caminho padrao do agregador no appliance e:

- `/opt/totem/bin/totem_status_aggregate.py`.

Para deploy futuro, o arquivo `scripts/board/totem_status_aggregate.py` deve
ser copiado para `/opt/totem/bin/totem_status_aggregate.py` junto do launcher.
Nao ha necessidade de alterar a unit systemd nesta subfase se o deploy mantiver
o mesmo diretorio de binarios.

Variaveis de ambiente aceitas pelo launcher:

- `TOTEM_STATUS_AGGREGATOR`: caminho do agregador;
- `TOTEM_STATUS_OUT_DIR`: diretorio de saida, padrao `/tmp/dadooh-status`;
- `TOTEM_PLAYER_STATUS_FILE`: status do player, padrao `/tmp/kiosky-status.json`;
- `TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC`: intervalo minimo de warning.

## Falha do agregador

Falha do agregador nao falha o launcher. Se o arquivo nao estiver executavel ou
se o processo sair com erro, o launcher registra warning simples e segue o fluxo
principal.

Warnings previstos:

- `status_aggregator_unavailable`;
- `status_aggregator_failed rc=<codigo>`.

Esses warnings nao incluem config, URL, identificador privado, SSID, IP publico,
payload ou path de midia.

## Escopo negativo

Esta subfase nao faz:

- exibicao na tela;
- renderer;
- MPV extra;
- acesso a `/dev/dri`;
- mudanca em systemd;
- mudanca no `kiosky-player`;
- Wi-Fi setup;
- onboarding;
- QR code.

## Validacao local

Validacoes locais previstas:

- `bash -n scripts/board/kiosky_service_launcher.sh`;
- `bash scripts/board/smoke_launcher_status_integration.sh`;
- `python3 -m py_compile scripts/board/totem_status_aggregate.py`;
- `python3 -m py_compile scripts/board/totem_status_render_preview.py`;
- `git diff --check`.

O smoke local usa diretorio temporario em `/tmp`, importa as funcoes do
launcher sem entrar no loop principal, confirma geracao de `status.json` e
`status.svg`, e confirma que agregador ausente gera warning sem interromper
`write_status`.

## Proximos passos

Depois de revisao humana, a proxima etapa recomendada e deploy controlado
apenas na placa de desenvolvimento para confirmar que:

- o status sanitizado e atualizado durante `starting`, `display_missing`,
  `running`, `app_exited` e `stopped`;
- o comportamento HDMI ausente/reconexao continua igual ao validado;
- nenhum processo novo de renderer ou MPV aparece;
- `/tmp/dadooh-status` nao contem dado sensivel.
