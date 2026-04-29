# Auditoria inicial do kiosky-player

Data: 2026-04-29

Repositorio auditado: `https://github.com/dadoohai/kiosky-player`

Checkout local: `/home/builder/kiosky-player`

Escopo: auditoria estatica local. Nao foi executado `kiosk.py`, nao foi iniciado MPV, nao houve chamada de API, nao houve download de midia, nao foi usado SSH e nada foi executado na Orange Pi.

Nota de redacao: tokens, URLs sensiveis, API keys e `environment_id` foram omitidos ou descritos sem reproduzir valores.

## Sumario executivo

O HEAD atual contem melhorias relevantes sobre o segundo commit: fallback offline mais forte, montagem de playlist a partir do cache, verificacao parcial de download incompleto, cooldown para midia que falha no MPV, status/telemetria mais completos, sincronismo diario por UTC e testes unitarios. Ao mesmo tempo, o HEAD ainda nao esta pronto para instalacao direta na placa como appliance 24/7.

A recomendacao tecnica e nao instalar nem o segundo commit puro nem o HEAD puro. O caminho mais seguro e criar uma branch de estabilizacao a partir do HEAD atual e aplicar correcoes de integracao para Orange Pi: sanitizacao de secrets/config, layout `/opt/totem` + `/data`, servico `systemd` de sistema, limites de disco, caminho de runtime em `/tmp`, politica clara para UI de configuracao, telemetria sem token hardcoded e testes de soak antes de ir para placa.

O segundo commit (`fe2de36`) e menor e foi informado como base para rollback em campo, mas tambem tem riscos: fallback offline mais limitado, ausencia do sincronismo UTC atual, ausencia de alguns tratamentos de midia ruim e uma fragilidade no fluxo de restart do MPV quando o IPC nao fica disponivel. Portanto, ele serve como referencia de estabilidade historica, nao como base final sem backports.

## Commits analisados

| Ordem | Commit | Mensagem | Papel provavel |
|---:|---|---|---|
| 1 | `38d2680b92e2dca1d26774c3d3da5aea1ca605cb` | Initial kiosk player | MVP inicial: player MPV, polling de API, scripts, config e docs iniciais. |
| 2 | `fe2de3692ec4eec327ee048e96c2188bb1b10fb1` | Add offline-first playback and cache safeguards | Primeira versao estavel informada: cache/state/offline, telemetria/status/watchdog/limpeza. |
| 3 | `0768e022c95dc1a5bb664d332adb58ab5b777d81` | Mudanca de timout | Ajuste pontual de timeout. |
| 4 | `13610d640aa6230458a0b732c07e903f46d4b468` | "watchdog" | Endurecimento de watchdog/MPV. |
| 5 | `1dd49d5db852d96a3a139eb884f868b1399c42f3` | Add UTC-based daily sync with drift handling | Sincronismo diario por UTC, drift e testes. |
| 6 | `d3b67500cc8464028b24c47e3e66452c67b919da` | Harden reboot resilience and offline playback fallback | Resiliencia de reboot e fallback offline mais completo. |
| 7 | `449c2ebe1cccbd8ceb01a3c76224b4fd0e389768` | Fix false MPV path mismatch restarts that caused black flashes | Correcao de reinicios falsos do MPV e flashes/tela preta. |
| 8 | `f5ddf4db42f4468b9fb8d3b0b55755fee9c93e58` | Rebuild from fe2 baseline with nightly sync and offline boot resilience | Reconstrucao sobre a base do segundo commit, mantendo parte das melhorias. |
| 9 | `5cca8dc9dab21ea44b62210c670db0f53b2dd2ee` | Fix daily 00:05 UTC rearm and zero-drift action handling | Ajuste do rearm diario 00:05 UTC e drift zero. |
| 10 | `c62354ec17ee4175f25aa3ba5ebc11abf1a7698b` | Fix telemetry HTTP error handling and add coverage | HEAD atual: tratamento de erro HTTP na telemetria e testes. |

Primeiro commit: `38d2680b92e2dca1d26774c3d3da5aea1ca605cb`

Segundo commit: `fe2de3692ec4eec327ee048e96c2188bb1b10fb1`

HEAD atual: `c62354ec17ee4175f25aa3ba5ebc11abf1a7698b`

## Diferencas entre segundo commit e HEAD

Comando auditado:

```text
git diff --stat fe2de36..HEAD
```

Resultado:

```text
INSTRUCOES.md                  |    9 +
README.md                      |   33 +-
config.example.json            |   15 +-
kiosk.py                       | 1054 +++++++++++++++++++++++++++++++++++-----
tests/test_offline_fallback.py |   86 ++++
tests/test_resilience.py       |   58 +++
tests/test_sync.py             |   71 +++
tests/test_telemetry.py        |  105 ++++
8 files changed, 1311 insertions(+), 120 deletions(-)
```

Arquivos alterados:

```text
M  INSTRUCOES.md
M  README.md
M  config.example.json
M  kiosk.py
A  tests/test_offline_fallback.py
A  tests/test_resilience.py
A  tests/test_sync.py
A  tests/test_telemetry.py
```

Mudancas funcionais relevantes desde `fe2de36`:

- Configuracoes novas: `offline_ignore_max_age_when_no_network`, `allow_empty_playlist_from_api`, `media_load_retry_cooldown_sec`, `tmp_max_age_sec`, `sync_enabled`, `sync_drift_threshold_ms`, `sync_hard_resync_ms`, `sync_boot_hard_check_sec`, `sync_checkpoint_interval_sec`, `sync_prep_mode`, `sync_ntp_command`.
- `telemetry_interval_sec` mudou no exemplo de configuracao de 300 para 60 segundos. A documentacao ainda cita 300 segundos em alguns pontos, o que precisa ser decidido/corrigido.
- O player atual consegue iniciar em modo offline sem credenciais de API se houver cache local valido. O segundo commit exigia `api_key` e `environment_id` antes de chegar ao fallback.
- O HEAD adiciona montagem de playlist diretamente a partir de arquivos no cache quando o estado salvo nao existe ou esta incompleto.
- Downloads passaram a usar arquivo `.tmp`, `os.replace` e verificacao de `Content-Length` quando o servidor informa esse header.
- Arquivos `.tmp` antigos passam a ser limpos por idade.
- Midia que falha ao carregar no MPV entra em cooldown temporario e o player tenta avancar para a proxima.
- Foram adicionados status internos para risco de tela preta, drift de sincronismo, estado de playback e contador de midias bloqueadas.
- Foi adicionado sincronismo diario global por UTC com ancora 00:05 UTC, PREP window e correcao de drift.
- O controle de MPV atual tem geracao de processo, lock reentrante e resposta por `request_id` no IPC. Isso reduz risco de restart falso e corrige fragilidades do fluxo anterior.
- Foram adicionados testes unitarios para fallback offline, resiliencia, sync e telemetria.

## Arquitetura atual

Entrypoint principal: `kiosk.py`, funcao `main()`. O binario esperado e:

```text
python kiosk.py --config config.json
```

Dependencia Python declarada: `requests>=2.31`.

Dependencias de sistema:

- MPV instalado e funcional.
- Stack grafica para o MPV abrir fullscreen: X11/Wayland/DRM conforme imagem final.
- `xdg-open` e navegador apenas se a UI de configuracao por hotkey ficar habilitada.
- `chronyc`/chrony se `sync_ntp_command` ficar habilitado.
- rede, DNS e TLS para API de playlist, URLs de midia e telemetria.
- `systemd` para autostart.

Fluxo atual:

- `load_config()` carrega o JSON e resolve caminhos relativos a partir do diretorio do arquivo de configuracao.
- `setup_logging()` envia logs para stdout e opcionalmente para `log_file` com rotacao.
- `fetch_media_list()` faz POST para a API usando `api_key` no header e `environment_id` no payload.
- `download_media()` baixa midias com `requests.get(stream=True)` para `cache_dir`, gravando primeiro em `.tmp` e promovendo por `os.replace`.
- `CacheIndex` grava metadados de cache em JSON.
- `save_playlist_state()` grava a ultima playlist usada para boot offline.
- `MPVController` inicia um processo MPV fullscreen, abre IPC e controla `loadfile`, `playlist-next`, `seek`, `set_property` e `ping`.
- `playback_loop()` escolhe o item atual, aplica offset UTC se sincronismo estiver habilitado, pre-carrega o proximo item e pula midias com falha temporaria.
- `poller()` atualiza playlist, baixa novas midias, evita troca incompleta quando configurado e faz limpeza apos update.
- `watchdog()` reinicia MPV quando o processo cai ou o IPC nao responde.
- `ConfigServer` sobe HTTP local para alterar `environment_id` e rotacao.
- `telemetry_worker()` envia startup/healthcheck/playlist update, mas nao persiste fila offline.
- `status_writer()` grava status JSON se `status_file` estiver configurado.
- `cleanup_worker()` remove `.tmp` antigo e arquivos fora da playlist/estado, respeitando modo offline.

## Pontos de escrita em disco

| Escrita | Local atual/padrao | Observacao | Ajuste recomendado para appliance |
|---|---|---|---|
| Config principal | `config.json` passado por `--config` | A UI salva usando `config.json.tmp` + replace. | `/data/config/config.json`. |
| Cache de midia | `cache_dir`, padrao `./media_cache` | Arquivos por hash da URL + extensao. | `/data/media` ou subpasta dedicada em `/data/media/kiosky-player`. |
| Download temporario | `cache_dir/*.tmp` | Promovido por `os.replace`; `.tmp` antigo e limpo por idade. | Mesmo filesystem de `/data/media`. |
| Estado persistente | `state_dir`, padrao `cache_dir/.state` | `playlist_last.json`, `cache_index.json`, `last_success.json`, sempre com `.tmp`. | Decidir entre `/data/media/.state`, `/data/spool/kiosky-state` ou criar `/data/state`. |
| Log persistente | `log_file`, padrao vazio | Se configurado, usa `RotatingFileHandler`. | Preferir stdout/journald volatil; se necessario, `/data/logs/kiosky-player.log` com rotacao curta. |
| Status JSON | `status_file`, padrao vazio | Escreve a cada `status_interval_sec`; pode gerar churn. | Preferir `/tmp/kiosky-status.json` em RAM; persistir somente se houver consumidor real. |
| IPC MPV | `ipc_path`, padrao `/tmp/mpv-kiosk.sock` em Linux | Socket removido em start/stop. | Manter em `/tmp`, idealmente `/tmp/kiosky/mpv.sock`. |
| Hotkey MPV | `./runtime/hotkeys.conf` | Sempre relativo ao `WorkingDirectory`, nao ao config. | Incompativel com `/opt/totem` read-only; mover para `/tmp` ou desabilitar hotkeys em producao. |
| Venv/dependencias | `.venv` no repo por scripts | `deps.sh` cria venv e pode chamar apt/sudo. | Preparar na imagem/build; nao executar scripts de deps na placa. |
| systemd user unit | `$HOME/.config/systemd/user/kiosky.service` | Criado por `scripts/install/linux.sh`. | Substituir por unit de sistema em `/etc/systemd/system`. |

## Adequacao para `/opt/totem` e `/data`

O codigo ja permite configurar `cache_dir`, `state_dir`, `log_file`, `status_file` e `ipc_path`. Isso e positivo para root read-only no futuro. Porem ainda ha incompatibilidades antes de integrar:

- `ensure_hotkey_conf()` escreve `./runtime/hotkeys.conf` no diretorio de trabalho. Se a aplicacao ficar em `/opt/totem` read-only, isso quebra ou exige escrita em `/opt`.
- `scripts/run.sh` e `scripts/install/deps.sh` criam `.venv` dentro do repo e podem instalar pacotes no sistema. Isso nao combina com a placa validada nem com politica de imagem imutavel.
- `scripts/install/linux.sh` instala servico de usuario, nao servico de sistema. Para appliance, precisamos controle de boot, display, limites de restart, usuario dedicado e paths explicitos.
- `config.example.json` tem valores sensiveis/reais demais para servir como exemplo publico. Deve virar template redigido.
- O estado mutavel ainda precisa de decisao de arquitetura: usar `state_dir` dentro de `/data/media/.state`, criar `/data/state`, ou usar subpasta em `/data/spool`. A opcao mais limpa seria um diretorio de estado dedicado; se a arquitetura nao quiser criar outro ponto, `/data/spool/kiosky-state` e aceitavel.

Mapeamento recomendado inicial:

```json
{
  "cache_dir": "/data/media",
  "state_dir": "/data/spool/kiosky-state",
  "log_file": "",
  "status_file": "/tmp/kiosky-status.json",
  "ipc_path": "/tmp/kiosky/mpv.sock",
  "hotkeys_enabled": false,
  "config_ui_enabled": false,
  "telemetry_enabled": false
}
```

Telemetria pode ser reabilitada depois que token/config/spool estiverem definidos.

## Robustez 24/7

Riscos altos:

- Ha token de telemetria hardcoded no codigo e coberto por teste. Se for segredo real, deve ser removido e rotacionado antes de publicar ou instalar.
- `config.example.json` contem `environment_id` com aparencia real e endpoints sensiveis. Deve ser redigido.
- Modelo atual de instalacao Linux usa `systemd --user`, `.venv` no repo e scripts que podem usar apt/sudo. Nao e adequado ao appliance Orange Pi.
- O app nao tem guarda explicita de espaco livre antes de baixar midia. Uma playlist grande pode encher `/data` antes da limpeza.
- Runtime de hotkey escreve no diretorio da aplicacao; isso conflita com `/opt/totem` read-only.
- Se MPV/display estiverem indisponiveis, ha risco de tela preta ou restart loop entre watchdog interno e systemd externo.

Riscos medios:

- Validacao de midia e limitada: extensao/tamanho e erro de load no MPV. Nao ha checksum, validacao de codec, content-type confiavel, nem quarentena persistente de arquivo corrompido.
- Download incompleto so e detectado quando `Content-Length` existe. Sem esse header, arquivo truncado pode ser promovido.
- Arquivo de cache existente nao e revalidado antes de entrar na playlist online; cache antigo parcial/corrompido pode chegar ao MPV.
- `sync_ntp_command` usa comando shell configuravel. Em appliance, sincronismo de hora deve ser responsabilidade do sistema, com chrony validado fora da aplicacao.
- UI de configuracao depende de teclado/hotkey e navegador. Isso e fragil para manutencao remota/operacional e deve ser uma decisao explicita.
- UI local nao tem autenticacao. O bind padrao e loopback, mas nao deve ser exposto em rede sem protecao.
- Telemetria nao tem spool offline em `/data/spool`; falhas sao apenas logadas.
- Escrita de `status_file` a cada 5 segundos pode ser excessiva se persistida em `/data/logs` ou `/data/config`.
- Se a API estiver indisponivel no primeiro boot e nao houver cache, o player nao tem placeholder visual robusto.
- O intervalo de telemetria esta inconsistente entre exemplo e documentacao.

Riscos baixos:

- Risco de vazamento de memoria em Python parece baixo pela leitura estatica: listas principais sao limitadas pela playlist e cooldown e em memoria. Ainda precisa soak test.
- `RotatingFileHandler` limita crescimento de log quando `log_file` esta configurado corretamente.
- Limpeza de cache remove arquivos fora da playlist/estado, mas precisa ser combinada com limite de bytes e teste de disco cheio.

## Seguranca e configuracao

Achados:

- Existe token de telemetria hardcoded em `kiosk.py` e teste correspondente em `tests/test_telemetry.py`.
- `api_key` principal aparece como placeholder no exemplo, mas o projeto contem endpoints sensiveis e um `environment_id` default com aparencia real.
- A documentacao cita endpoint de telemetria. Em documento publico, esse tipo de URL deve ser redigido ou movido para documentacao privada.
- A UI exibe e grava `environment_id` em texto claro. Isso pode ser aceitavel em loopback local, mas nao deve ser exposto em rede.
- `sync_ntp_command` configuravel com `shell=True` deve ser desabilitado ou rigidamente controlado em producao.

Recomendacoes:

- Remover token hardcoded do codigo e dos testes; carregar por config local ou variavel de ambiente protegida.
- Rotacionar o token se ele ja foi exposto fora de ambiente privado.
- Redigir `config.example.json`: `api_url`, `telemetry_url`, `environment_id`, `api_key` e `station_id` devem ser placeholders.
- Separar `config.example.json` publico de `config.device.json` privado.
- Validar permissoes: `/data/config/config.json` deve ser gravavel apenas pelo usuario do servico e equipe de manutencao.

## Instalacao atual

`scripts/install/linux.sh`:

- Gera unit em `$HOME/.config/systemd/user/kiosky.service`.
- Usa `WorkingDirectory` no checkout.
- Usa Python da `.venv` no checkout.
- Usa `config.json` no checkout.
- Executa `systemctl --user enable --now`.

`scripts/linux/systemd/kiosky.service`:

- Tambem e unit de usuario.
- Depende de `network-online.target`.
- Usa paths placeholder.
- `Restart=always` e `RestartSec=5`, sem `StartLimit`.

Decisao: `systemd --user` nao e adequado como modelo final para o totem appliance. Ele depende de usuario/logind/linger, nao modela bem display e boot, nao protege paths e nao combina com root read-only.

Proposta de direcao para servico de sistema, sem implementar ainda:

```ini
[Unit]
Description=Totem Kiosky Player
After=network-online.target time-sync.target graphical.target
Wants=network-online.target time-sync.target

[Service]
Type=simple
User=totem
Group=totem
WorkingDirectory=/opt/totem/kiosky-player
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/totem/venv/bin/python /opt/totem/kiosky-player/kiosk.py --config /data/config/config.json
Restart=on-failure
RestartSec=10
StartLimitIntervalSec=300
StartLimitBurst=5
NoNewPrivileges=yes
ReadOnlyPaths=/opt/totem
ReadWritePaths=/data /tmp

[Install]
WantedBy=multi-user.target
```

Ainda falta decidir como a sessao grafica sera criada e como o MPV recebera `DISPLAY`/Wayland/DRM no ambiente final.

## Recomendacoes antes de instalar na placa

1. Criar branch de estabilizacao a partir do HEAD atual.
2. Sanitizar secrets e exemplos: token de telemetria, URLs sensiveis e `environment_id`.
3. Definir layout final: app em `/opt/totem/kiosky-player`, config em `/data/config/config.json`, midia em `/data/media`, estado em diretorio decidido dentro de `/data`, status em `/tmp`.
4. Desabilitar hotkeys/UI em producao inicial ou mover runtime para `/tmp`.
5. Trocar instalacao `systemd --user` por unit de sistema com usuario dedicado e limites de restart.
6. Remover uso de apt/sudo dos scripts de instalacao na placa; dependencias devem vir da imagem ou de pacote controlado.
7. Adicionar limite de cache por bytes e checagem de espaco livre antes de download.
8. Melhorar validacao de midia: arquivo existente deve ser revalidado, arquivo ruim deve ser quarentenado, e downloads sem `Content-Length` precisam de politica conservadora.
9. Desligar `sync_ntp_command` no app e validar chrony como servico do sistema, ou restringir o comando a um wrapper controlado.
10. Definir telemetria: token via config/env, spool offline em `/data/spool` se for requisito, e intervalo padronizado.

## Proximos testes propostos

- Rodar `python3 -m unittest discover` localmente, sem MPV e sem API real.
- Criar fake API local e fake servidor de midias para testar playlist vazia, HTTP 500, timeout, queda de internet e downloads truncados.
- Testar com MPV em bancada nao-placa: midia valida, midia corrompida, codec nao suportado, imagem, video curto e video longo.
- Testar disco cheio usando filesystem temporario pequeno para `/data/media`.
- Testar boot offline com cache valido, cache parcial e sem cache.
- Testar queda de rede por varias horas e retorno de rede.
- Testar reboot perto de 00:05 UTC e drift de relogio.
- Testar rotacao 0/90/180/270 em monitor real.
- Testar `systemd` de sistema com display real e limites de restart.
- Rodar soak test minimo de 24h antes de instalar em Orange Pi.

## Pontos que exigem decisao humana

- Usar HEAD como base da branch de estabilizacao ou pinning temporario no segundo commit com backports selecionados.
- Politica final de telemetria: habilitar agora, adiar, ou exigir spool offline.
- Onde armazenar estado mutavel: `/data/media/.state`, `/data/spool/kiosky-state` ou novo `/data/state`.
- Se a UI de configuracao por hotkey/browser deve existir em producao.
- Qual stack grafica sera padrao no Candidato A para o MPV.
- Retencao de logs persistentes: nenhum, erros minimos em `/data/logs`, ou apenas journal volatil.
- Tamanho maximo de cache e margem minima de espaco livre.
- Se URLs de API/telemetria devem ficar em config local privada ou em provisioning separado.

## Validacao local realizada

Comando executado:

```text
PYTHONPYCACHEPREFIX=/tmp/kiosky-player-pycache python3 -m compileall -q /home/builder/kiosky-player
```

Resultado: sucesso. A compilacao sintatica passou e o bytecode foi direcionado para `/tmp`, sem alterar o checkout do `kiosky-player`.

Nao executado:

- `python kiosk.py`
- MPV
- API real
- download de midias
- scripts de instalacao
- apt/sudo
- comandos na Orange Pi
