# Launcher status integration A1.2/A1.2.1/A1.3/A1.4

Status: implementacao incremental para revisao. Nao altera systemd nem player.
A1.4 adiciona renderer visual experimental controlado pelo launcher.

Data: 2026-05-01

## Objetivo

Integrar o agregador de status sanitizado ao launcher apenas para gerar
arquivos publicos em `/tmp`. Esta etapa ainda nao exibe nada na tela, nao
inicia renderer, nao inicia MPV adicional e nao acessa `/dev/dri`.

O comportamento operacional esperado do launcher permanece o mesmo: detectar
HDMI, iniciar o `kiosky-player` quando houver display e manter
`display_missing` sem app/MPV quando nao houver display.

A1.2.1 adiciona refresh periodico best-effort do agregador enquanto o processo
do player estiver vivo. Essa correcao existe porque a validacao
`20260501-123806-status-aggregator-hdmi-missing` mostrou que, apos reconexao
HDMI, o launcher escreveu `running` antes de `/tmp/kiosky-status.json`
convergir para `playing`; sem refresh posterior, o estado agregado ficou em
`starting_player` mesmo com app e MPV rodando.

A1.3 adiciona deteccao segura de `config_missing` antes de iniciar o player.
Quando ha display conectado, mas a config nao existe, nao e JSON valido ou nao
contem campos essenciais, o launcher publica `config_missing`, nao inicia
`kiosk.py`, nao inicia MPV e permanece ativo tentando novamente.

A1.4 adiciona um renderer MPV separado para exibir
`/tmp/dadooh-status/status.svg` apenas quando o player nao deve rodar,
inicialmente em `config_missing`. O launcher para esse renderer antes de
iniciar `kiosk.py`; se nao conseguir parar, nao inicia o player.

## Pontos de chamada

O launcher chama `totem_status_aggregate.py` dentro de `write_status`, depois
que o JSON bruto do launcher e gravado com sucesso.

Com isso, o agregador roda nos estados ja cobertos por `write_status`:

- `starting`;
- `display_missing`;
- `config_missing`;
- `running`;
- `app_exited`;
- `stopped`.

Em A1.2.1, depois que o launcher inicia o child app e grava `running`, ele
inicia um loop auxiliar de refresh. Enquanto o child estiver vivo, esse loop
chama o agregador no intervalo configurado por `TOTEM_STATUS_REFRESH_SEC`.

Quando o app sai, ou quando o launcher recebe `SIGTERM`/`SIGINT`, o loop de
refresh e encerrado. O fluxo `display_missing` nao inicia esse loop.

Em A1.3, quando o display esta conectado, o launcher valida a config antes de
chamar `run_app_once`. Se a config falhar na validacao basica, o launcher chama
`write_status "config_missing" "true"` e dorme por `KIOSKY_CONFIG_RETRY_SEC`.
O conteudo da config e seus valores nunca sao impressos.

Em A1.4, apos escrever `config_missing`, o launcher tenta iniciar o renderer de
status. O start e best-effort: renderer ausente, SVG ausente ou falha de start
geram warning simples e nao derrubam o servico. Em `display_missing`, o
launcher garante que o renderer esteja parado. Antes de `run_app_once`, o
launcher chama `stop_status_renderer` e so inicia o app se o renderer tiver
encerrado.

## Arquivos gerados

O agregador recebe o caminho do status bruto recem gravado e escreve:

- `/tmp/dadooh-status/status.json`;
- `/tmp/dadooh-status/status.svg`.

O diretorio de saida deve ser um subdiretorio de `/tmp`. O proprio `/tmp`
e proibido como `--out-dir`, inclusive quando informado como `/tmp/.`, para
evitar mudanca de permissao no diretorio global de temporarios.

O caminho padrao do agregador no appliance e:

- `/opt/totem/bin/totem_status_aggregate.py`.

Para deploy futuro, o arquivo `scripts/board/totem_status_aggregate.py` deve
ser copiado para `/opt/totem/bin/totem_status_aggregate.py` junto do launcher.
Nao ha necessidade de alterar a unit systemd nesta subfase se o deploy mantiver
o mesmo diretorio de binarios.

Variaveis de ambiente aceitas pelo launcher:

- `KIOSKY_CONFIG_PATH`: caminho da config, padrao `/data/config/config.json`;
- `KIOSKY_CONFIG_RETRY_SEC`: intervalo de nova tentativa quando a config esta
  ausente ou invalida, padrao 5 segundos;
- `TOTEM_STATUS_AGGREGATOR`: caminho do agregador;
- `TOTEM_STATUS_OUT_DIR`: diretorio de saida, padrao `/tmp/dadooh-status`;
- `TOTEM_PLAYER_STATUS_FILE`: status do player, padrao `/tmp/kiosky-status.json`;
- `TOTEM_STATUS_AGGREGATOR_TIMEOUT_SEC`: timeout defensivo, padrao 2 segundos;
- `TOTEM_STATUS_REFRESH_SEC`: intervalo do refresh periodico enquanto o player
  estiver vivo, padrao 5 segundos;
- `TOTEM_STATUS_AGGREGATOR_WARN_INTERVAL_SEC`: intervalo minimo de warning.
- `TOTEM_STATUS_RENDERER`: caminho do renderer visual, padrao
  `/opt/totem/bin/totem_status_renderer.sh`;
- `TOTEM_STATUS_SVG`: SVG publico exibido pelo renderer, padrao
  `/tmp/dadooh-status/status.svg`;
- `TOTEM_STATUS_RENDERER_STOP_TIMEOUT_SEC`: tempo para aguardar parada antes
  de enviar `KILL`, padrao 3 segundos;
- `TOTEM_STATUS_RENDERER_WARN_INTERVAL_SEC`: intervalo minimo de warning do
  renderer.

## Falha do agregador

O agregador e best-effort, tanto nas chamadas imediatas de `write_status`
quanto no refresh periodico de A1.2.1. Falha do agregador nao falha o launcher.
Se o arquivo nao estiver executavel, se `timeout` nao estiver disponivel, se o
processo sair com erro ou se exceder o timeout defensivo, o launcher registra
warning simples e segue o fluxo principal.

Warnings previstos:

- `status_aggregator_unavailable`;
- `status_aggregator_timeout_unavailable`;
- `status_aggregator_timeout`;
- `status_aggregator_failed rc=<codigo>`.

Esses warnings nao incluem config, URL, identificador privado, SSID, IP publico,
payload ou path de midia.

## Config ausente ou invalida

A validacao A1.3 e deliberadamente minima e local. Ela confirma que:

- o arquivo de config existe;
- o arquivo e legivel pelo usuario do launcher;
- o conteudo e JSON valido;
- a raiz do JSON e um objeto;
- campos essenciais estao presentes e nao vazios.

O launcher nao registra os valores desses campos, nao imprime o JSON e nao
copia payloads para status. O status publico gerado pelo agregador e
`config_missing`, com `config_state=missing`, `player_state=not_started` e
`service_state=active`.

O servico permanece `active`: isso evita restart loop agressivo e permite que
uma etapa futura de onboarding/manutencao corrija a config em `/data`.

Em A1.4, esse mesmo estado pode manter o renderer visual ativo enquanto o
launcher segue tentando a config periodicamente. Se a config passar a ser
valida, o renderer e parado antes do player.

## Renderer visual A1.4

O renderer fica em `scripts/board/totem_status_renderer.sh` e, no appliance, em
`/opt/totem/bin/totem_status_renderer.sh`. Ele recebe o caminho do SVG como
argumento ou usa `/tmp/dadooh-status/status.svg`.

O renderer executa MPV com saida explicita:

```sh
--vo=gpu
--gpu-context=drm
--ao=null
```

Ele tambem usa flags de imagem/status como `--no-config`, tela cheia,
`--image-display-duration=inf`, `--loop-file=inf`, `--no-osc`,
`--osd-level=0` e entrada desabilitada. O processo nao acessa internet, nao le
config privada e nao inicia `kiosk.py`.

Regra critica: o renderer nunca deve permanecer ativo junto com o MPV principal
do player.

## Escopo negativo

Mesmo com A1.4, esta frente nao faz:

- mudanca em systemd;
- mudanca no `kiosky-player`;
- Wi-Fi setup;
- onboarding;
- QR code.

Observacao: A1.4 passa a fazer exibicao visual experimental por MPV separado em
`config_missing`, com acesso DRM/KMS indireto pelo MPV do renderer, mas ainda
nao adiciona setup, portal, onboarding ou manutencao.

## Validacao local

Validacoes locais previstas:

- `bash -n scripts/board/kiosky_service_launcher.sh`;
- `bash -n scripts/board/totem_status_renderer.sh`;
- `bash scripts/board/smoke_launcher_status_integration.sh`;
- `python3 -m py_compile scripts/board/totem_status_aggregate.py`;
- `python3 -m py_compile scripts/board/totem_status_render_preview.py`;
- `git diff --check`.

O smoke local usa `/tmp/dadooh-status-test`, importa as funcoes do launcher sem
entrar no loop principal, confirma geracao de `status.json` e `status.svg`,
confirma que `/tmp` e rejeitado como `--out-dir`, e confirma que agregador
ausente ou lento gera warning sem interromper `write_status`. Em A1.2.1, o
smoke tambem exercita um child fake e confirma que o refresh periodico agrega
o estado `running` mais de uma vez enquanto o child esta vivo, e para depois
que o child termina.

Em A1.3, o smoke usa um caminho de config inexistente, chama o fluxo de display
conectado, confirma que o agregado fica em `config_missing` e confirma que o
app fake nao e chamado.

Em A1.4, o smoke tambem usa renderer fake para confirmar que:

- o renderer inicia em `config_missing`;
- o renderer nao inicia em `display_missing`;
- o renderer nao duplica;
- o renderer e parado antes do app fake iniciar;
- falha de parada do renderer impede app fake;
- renderer ausente nao derruba o launcher;
- config valida continua chamando app fake.

## Proximos passos

Depois de revisao humana, a proxima etapa recomendada e deploy controlado
apenas na placa de desenvolvimento para confirmar que:

- o status sanitizado e atualizado durante `starting`, `display_missing`,
  `running`, `app_exited` e `stopped`;
- apos reconexao HDMI, o status agregado converge de `starting_player` para
  `player_running` quando `/tmp/kiosky-status.json` passa a indicar playback;
- com config ausente/invalida e HDMI conectado, o status agregado converge para
  `config_missing` sem iniciar `kiosk.py` ou MPV;
- o comportamento HDMI ausente/reconexao continua igual ao validado;
- nenhum processo novo de renderer ou MPV aparece;
- `/tmp/dadooh-status` nao contem dado sensivel.
