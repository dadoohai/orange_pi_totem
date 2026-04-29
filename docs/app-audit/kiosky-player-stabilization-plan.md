# Plano de estabilizacao do kiosky-player para appliance-v0.1

Data: 2026-04-29

Repositorios locais:

- `orange_pi_totem`: `/home/builder/totem-os/orange_pi_totem`
- `kiosky-player`: `/home/builder/kiosky-player`

Escopo desta etapa: plano tecnico e documentacao. Nao foi executado `kiosk.py`, nao foi iniciado MPV real, nao houve API real, nao houve download real de midia, nao houve SSH, nao houve apt e nada foi executado na Orange Pi.

## Decisao recomendada

Criar a branch `appliance-v0.1` a partir do HEAD atual `c62354ec17ee4175f25aa3ba5ebc11abf1a7698b`, nao a partir do segundo commit puro `fe2de3692ec4eec327ee048e96c2188bb1b10fb1`.

Justificativa:

- O HEAD contem correcoes que reduzem risco operacional: fallback offline sem credenciais quando ha cache, playlist a partir de cache local, tratamento de playlist vazia, cooldown para midia que falha no MPV, limpeza de `.tmp`, melhor controle de IPC do MPV e testes unitarios.
- O segundo commit e uma referencia historica de estabilidade, mas tem lacunas importantes para appliance: exige credenciais antes do fallback offline, nao monta playlist direto do cache, nao limpa temporarios antigos, nao tem cooldown de midia ruim e tem controle de MPV mais fragil.
- O HEAD tambem trouxe recursos que aumentam superficie de risco, principalmente sync/chrony, UI/hotkey, telemetria e paths mutaveis. Por isso a branch `appliance-v0.1` deve partir do HEAD e desativar ou corrigir esses pontos antes da placa.

Resumo da politica: usar HEAD como base tecnica, aplicar endurecimento minimo e usar configuracao conservadora. Nao instalar HEAD puro.

## Matriz de modulos e riscos

| Area | O que faz | Escrita em disco | Risco 24/7 | Risco root read-only | Risco queda de energia | Risco tela preta | Risco RAM/disco | Teste antes da placa |
|---|---|---|---|---|---|---|---|---|
| `load_config` | Le `config.json`, aplica defaults e resolve caminhos relativos ao diretorio da config. | Nao escreve. | Paths relativos podem cair em locais errados se o config estiver em `/opt` por engano. | Baixo se todos os paths mutaveis forem absolutos em `/data` ou `/tmp`. | Baixo. | Indireto: config ruim pode apontar IPC/cache/log para lugar invalido e impedir MPV/cache. | Baixo. | Unit test com config em `/data/config`, paths absolutos e paths relativos bloqueados por policy. |
| `setup_logging` | Configura stdout e `RotatingFileHandler` opcional. | `log_file` e diretorio pai se configurado. | Log persistente pode mascarar erro se diretorio nao existir/permissao falhar; stdout e mais previsivel no appliance. | Alto se `log_file` apontar para `/opt`. | Rotating log pode perder ultima linha, aceitavel; arquivo pode ficar inconsistente se FS falhar. | Indireto: excecao de permissao na inicializacao pode impedir app. | Crescimento limitado por rotacao, mas ainda consome `/data` se habilitado. | Teste com `log_file=""`, com `/data/logs`, e permissao negada simulada. |
| `download_media` | Baixa cada URL para `cache_dir`, escreve `.tmp`, confere `Content-Length` quando existe e promove com `os.replace`. | `cache_dir`, `cache_dir/*.tmp`, arquivo final por hash. | Sem guarda de espaco livre; sem validacao forte de codec/hash/content-type; download sem `Content-Length` pode promover truncado. | Medio se `cache_dir` estiver em `/data`; alto se config apontar para `/opt`. | Melhor que `fe2`: `os.replace` evita arquivo final parcial quando o processo cai antes da promocao; `.tmp` pode sobrar. | Arquivo corrompido pode entrar no MPV e gerar tela preta ate cooldown/skip. | Alto sem limite de bytes e sem preflight de espaco. | Fake media server com `Content-Length` correto, truncado, sem header, timeout, disco cheio e cache existente corrompido. |
| `MPVController` | Inicia MPV fullscreen, cria/limpa IPC, envia comandos, faz ping e restart. | Remove socket IPC; MPV cria socket. Hotkey pode gerar `runtime/hotkeys.conf` via `build_mpv_args`. | Restart interno pode entrar em loop se display/IPC indisponivel; precisa coordenar com systemd. | Baixo para IPC em `/tmp`; alto se hotkey escrever em `/opt`. | Queda de energia deixa socket antigo, mas `_cleanup_ipc_path` remove no boot. | Alto: display/MPV indisponivel, IPC travado ou midia ruim podem deixar tela preta. | MPV e preloading podem consumir RAM/GPU; stderr/stdout vao para `/dev/null`, reduz diagnostico local. | MPV fake que cria socket, simula ping, falha de IPC, processo morto, start sem socket e restart controlado. |
| `playback_loop` | Seleciona item, aplica sync UTC/offset, carrega midia no MPV, pre-carrega proxima, pula midia com falha temporaria. | Atualiza `cache_index` via `cache_index.touch`; indiretamente grava estado. | Complexidade alta; se todas as midias falham, fica esperando e pode manter tela preta. Sync adiciona risco de resync inesperado. | Baixo se state/cache em `/data`; alto se state cair em `/opt`. | Estado de ultimo uso pode perder poucos segundos, aceitavel. | Alto se playlist vazia, todas midias bloqueadas, MPV load falha ou sync `wait_until_anchor` for usado. | `preload_next` aumenta uso de RAM/decoder; cooldown em memoria e limitado pela playlist. | Fake MPV com load falhando, todas midias ruins, playlist vazia, reload de playlist, `preload_next` ligado/desligado, sync off/on. |
| `poller` | Faz polling da API, baixa midias, atualiza playlist, salva estado, limpa cache e envia telemetria de update/erro. | `playlist_last.json`, `last_success.json`, `cache_index.json`, cache de midia, logs. | API indisponivel gera backoff e mantem estado; sem cache inicial nao ha playback. Playlist vazia e tratada melhor no HEAD. | Medio: depende de todos os paths mutaveis em `/data`. | Escritas JSON usam `.tmp` + replace, bom; ainda pode sobrar `.tmp`. | Indireto: trocar para playlist incompleta/vazia poderia causar tela preta; HEAD evita em parte. | Alto se playlist grande baixar demais antes de limpeza; telemetria sem spool nao cresce. | Fake API vazia, API 500, timeout, update com item novo, download parcial, `require_full_download_before_switch`. |
| `watchdog` | Garante MPV rodando, pinga IPC e reinicia se nao responder. | Nao escreve, exceto logs/status. | Pode criar loop de restart se MPV/display/IPC estiverem indisponiveis; systemd precisa limitar. | Baixo. | Apos reboot, tenta recuperar MPV. | Pode tanto recuperar tela preta quanto piorar flicker se ping falso falhar. | Baixo direto; MPV restart frequente consome CPU. | Fake MPV sem IPC, IPC lento, ping falso, processo morto, contagem de restarts com rate limit externo. |
| `cleanup_worker` | Remove `.tmp` antigo e arquivos fora da playlist/estado; respeita `disable_cleanup_when_offline`. | Remove arquivos de `cache_dir`; atualiza status. | Pode remover midia necessaria se estado/playlist estiver inconsistente; offline safe reduz esse risco. | Medio se `cache_dir` errado. | Remove temporarios deixados por queda de energia; bom. | Indireto: limpeza incorreta pode deixar playlist sem arquivos. | Ajuda disco, mas `cache_max_bytes=0` desativa limite e limpeza so remove fora da playlist. | Cache com arquivos ativos, obsoletos, `.tmp` antigo/novo, offline com falha, limites por bytes/files. |
| `ConfigServer` | HTTP local para alterar `environment_id` e rotacao, salva config e aciona poll. | `config.json` e `config.json.tmp`. | Sem autenticacao; se exposto fora de loopback vira vetor de alteracao de ambiente. Depende de browser/hotkey para operacao. | Alto se config estiver em `/opt`; aceitavel em `/data/config`. | `os.replace` protege melhor; alteracao pode ser perdida se queda ocorrer antes do replace. | Rotacao errada ou ambiente sem playlist pode causar tela preta. | Baixo. | Teste com bind loopback, POST invalido, porta ocupada, config read-only, sem MPV real via mock. |
| `telemetry_worker` | Envia startup e healthcheck periodico; status varia com falhas do poller. | Nao escreve fila; atualiza status em memoria/log. | Token hardcoded e ausencia de spool; falhas recorrentes geram log, nao persistem fila. | Baixo direto. | Eventos se perdem; sem spool. | Indireto apenas. | Baixo em disco; rede periodica e potencial log de erro. | Testes com requests fake, HTTP 500, timeout, disabled, token via config/env. |
| `ensure_hotkey_conf` | Cria config de hotkey MPV para abrir browser local via `xdg-open`. | `./runtime/hotkeys.conf` relativo ao working directory. | Dependencia de teclado/browser; risco de manutencao acidental no campo. | Alto se `WorkingDirectory=/opt/totem/kiosky-player` read-only. | Arquivo pode sumir, mas e recriado em start. | Pode abrir UI/browser sobre o player; risco operacional. | Baixo. | Para v0.1, testar desativado. Se mantido, mover runtime para `/tmp` e testar sem escrita em `/opt`. |

## Comparacao `fe2de36` vs HEAD por area

| Area | Melhorias no HEAD | Riscos aumentados no HEAD | appliance-v0.1: ativar | appliance-v0.1: desativar ou corrigir |
|---|---|---|---|---|
| `load_config` | Resolve paths relativos a partir do diretorio do config, melhor para `/data/config`. | Pode mascarar config relativa apontando para `/data/config/media_cache` se o operador nao usar paths absolutos. | Manter. | Adicionar validacao/policy de paths absolutos em `/data` e `/tmp` antes da placa. |
| `setup_logging` | Sem mudanca relevante. | Nenhum novo relevante. | Manter stdout; `log_file=""`. | Log persistente ate existir politica de retencao. |
| `download_media` | Confere `Content-Length`, remove `.tmp` em erro, mantem cached file. | Ainda nao ha espaco livre minimo nem validacao de arquivo existente. | Manter `.tmp` + replace e full-download-before-switch. | Corrigir guarda de disco e validacao de cache antes da placa. |
| `MPVController` | Usa `RLock`, `_start_locked`, geracao de processo, IPC lock e resposta por `request_id`; evita recursao/false restarts do `fe2`. | Mais complexo; ainda sem rate limit interno. | Manter. | Testar com MPV fake; rate limit deve ser no systemd v0.1. |
| `playback_loop` | Cooldown para midia ruim, status de tela preta, offset para sync, invalidacao de preload por geracao. | Sync UTC aumenta complexidade; `preload_next` pode consumir RAM; todas as midias ruins ainda deixam espera/tela preta. | Manter cooldown e status. | `sync_enabled=false` inicialmente; `preload_next=false` para primeiro soak, reavaliar depois. |
| `poller` | Trata playlist vazia sem trocar se houver playlist/cache; fallback de cache local; backoff preservado. | Pode classificar playlist vazia como sucesso e atualizar `last_success`; precisa decisao semantica. | Manter `allow_empty_playlist_from_api=false`, `require_full_download_before_switch=true`, offline fallback. | Telemetria de erro sem token hardcoded; fake API tests obrigatorios. |
| `watchdog` | Sem mudanca funcional grande, mas se beneficia de MPVController melhor. | Restart loop continua possivel se MPV nunca subir. | Manter. | Limitar por systemd e testar com MPV fake. |
| `cleanup_worker` | Remove `.tmp` antigos por idade. | Se limites ficarem 0, cache ativo pode crescer sem teto. | Manter limpeza de `.tmp` e `disable_cleanup_when_offline=true`. | Definir `cache_max_bytes` e `cache_max_files`; testar limpeza. |
| `ConfigServer` | HEAD passa a capturar erro de bind da porta e nao derruba o app. | Continua sem autenticacao e grava config. | Desativar em producao v0.1. | Se necessario para bancada, ligar so localmente e com config em `/data/config`. |
| `telemetry_worker` | HEAD corrige tratamento de erro HTTP e tem cobertura. | Token hardcoded permanece; intervalo exemplo mudou para 60s. | Desativar no v0.1 ate remover token. | Remover token hardcoded, token via config/env, decidir spool. |
| `ensure_hotkey_conf` | Sem melhoria: continua escrevendo em `./runtime`. | Incompativel com `/opt/totem` read-only. | Desativar por config. | Mover para `/tmp` antes de qualquer uso em producao. |

## Perfil de configuracao appliance-v0.1 proposto

Este perfil e conservador: reduz escrita persistente, evita UI/telemetria/sync no primeiro ciclo e mantem dados mutaveis fora de `/opt/totem`.

```json
{
  "cache_dir": "/data/media",
  "state_dir": "/data/spool/kiosky-state",
  "log_file": "",
  "status_file": "/tmp/kiosky-status.json",
  "ipc_path": "/tmp/mpv-kiosk.sock",
  "hotkeys_enabled": false,
  "config_ui_enabled": false,
  "telemetry_enabled": false,
  "sync_enabled": false,
  "sync_ntp_command": "",
  "cache_max_bytes": 2147483648,
  "cache_max_files": 200,
  "tmp_max_age_sec": 3600,
  "cleanup_interval_sec": 1800,
  "low_resource_mode": true,
  "preload_next": false,
  "hwdec": "auto-safe"
}
```

Notas:

- `cache_max_bytes=2147483648` e um valor inicial de 2 GiB. Deve ser ajustado ao tamanho real de `/data` e ao volume esperado de campanhas.
- `preload_next=false` reduz uso de RAM no primeiro soak. Se houver flicker ou gap inaceitavel e a memoria estiver estavel, reavaliar para `true`.
- `sync_enabled=false` remove risco de `chronyc`, drift e resync durante a primeira estabilizacao. Se sincronismo global for requisito obrigatorio de produto, habilitar depois de testes dedicados com `sync_ntp_command=""` e chrony gerenciado pelo SO.
- `status_file` em `/tmp` evita escrita persistente a cada poucos segundos.
- `log_file=""` deixa logs no stdout/journald; para root read-only futuro, journald deve ser volatil ou limitado pelo SO.

## Mudancas minimas obrigatorias antes da placa

1. Remover token hardcoded de telemetria em `kiosk.py` e ajustar `tests/test_telemetry.py` para token via config/env/mock.
2. Sanitizar `config.example.json`: substituir endpoints sensiveis, `environment_id`, API key, telemetry URL e station por placeholders.
3. Criar `config.appliance.example.json` com o perfil appliance-v0.1 e placeholders seguros.
4. Adicionar validacao de paths mutaveis: `cache_dir` e `state_dir` em `/data`, `status_file` e `ipc_path` em `/tmp`, nenhum write em `/opt/totem`.
5. Impedir escrita em `/opt/totem`: hotkeys desativados no appliance; se hotkeys forem mantidos para bancada, `ensure_hotkey_conf` deve aceitar runtime dir em `/tmp`.
6. Adicionar guarda de espaco livre antes de download: usar `statvfs`, margem minima configuravel e recusar download quando `Content-Length` exceder espaco livre seguro. Para resposta sem `Content-Length`, aplicar limite maximo configuravel ou baixar com abort por teto.
7. Criar unit `systemd` de sistema em arquivo de projeto, sem instalar ainda: usuario `totem`, `WorkingDirectory=/opt/totem/kiosky-player`, config em `/data/config/config.json`, `Restart=on-failure`, `StartLimit*`, `ReadOnlyPaths=/opt/totem`, `ReadWritePaths=/data /tmp`.
8. Definir usuario `totem` e permissoes: `/opt/totem` legivel pelo usuario, `/data/config`, `/data/media`, `/data/spool` e opcional `/data/logs` gravaveis pelo usuario `totem`.
9. Remover instalacao via apt/sudo dos fluxos de placa. Dependencias entram pela imagem ou por pacote controlado, nunca por `scripts/install/deps.sh` no dispositivo.
10. Padronizar telemetria: desativada no v0.1 ou habilitada apenas apos token configuravel e decisao sobre spool offline.

## Suite de testes local obrigatoria antes da placa

Baseline ja executado nesta etapa:

```text
PYTHONPYCACHEPREFIX=/tmp/kiosky-player-pycache python3 -m unittest discover -s tests -p 'test_*.py' -q
```

Resultado: 17 testes, OK. O comando padrao `python3 -m unittest discover -q` nao encontrou testes; o runner do projeto deve ser documentado com `-s tests -p 'test_*.py'`.

Testes obrigatorios a adicionar/rodar antes da placa:

- Unit tests existentes: manter todos verdes.
- Fake API local: resposta normal, playlist vazia, API 500, timeout, JSON invalido, credenciais ausentes com cache local.
- Fake media server: midia pequena valida, midia grande, `Content-Length` correto, `Content-Length` maior que bytes enviados, sem `Content-Length`, conexao encerrada no meio.
- Download truncado: garantir que `.tmp` e removido e arquivo final antigo nao e sobrescrito.
- API vazia: com playlist atual, com cache local, sem cache.
- API 500: manter playlist/cache atual, backoff e status de erro.
- Timeout: tanto API quanto midia; garantir ausencia de travamento permanente.
- Cache parcial: arquivo zero byte, `.tmp` novo, `.tmp` antigo, arquivo com extensao valida mas conteudo ruim.
- Disco cheio simulado: usar filesystem temporario pequeno ou monkeypatch de `os.statvfs`/`open` para ENOSPC.
- MPV fake: substituir `subprocess.Popen` e IPC por fake local; testar watchdog, ping falso, processo morto, load falhando, restart sem abrir MPV real.
- Config read-only: garantir que appliance com UI/hotkeys off nao tenta escrever em `/opt/totem`.
- Root read-only simulado: checkout montado/permissoes read-only e paths mutaveis em temp `/data` fake.
- Soak local nao-placa: fake API + fake MPV por varias horas, validando crescimento de memoria, arquivos e threads.

## Criterios para permitir instalacao na Orange Pi

Antes de qualquer teste na placa, todos os criterios abaixo devem estar satisfeitos:

- Branch `appliance-v0.1` criada e revisada.
- Nenhum token, API key, URL sensivel ou `environment_id` real em arquivos versionados publicos.
- `config.appliance.example.json` existe e nao contem valores reais.
- `python3 -m unittest discover -s tests -p 'test_*.py' -q` passa localmente.
- Testes de fake API, fake media server, download truncado, API vazia/500/timeout, cache parcial, disco cheio e MPV fake passam localmente.
- Nenhuma escrita ocorre em `/opt/totem` durante testes com hotkeys/UI off.
- Todos os paths mutaveis do perfil apontam para `/data` ou `/tmp`.
- Unit `systemd` de sistema existe como arquivo revisavel, mas ainda nao instalada na placa.
- Usuario `totem` e permissoes de `/data` estao definidos no plano de imagem.
- `cache_max_bytes`, `cache_max_files` e margem minima de espaco livre estao definidos.
- Telemetria esta desativada ou tem token configuravel e sem hardcode.
- Sync/chrony esta desativado no app ou possui teste especifico e decisao humana de habilitacao.
- Ha plano de rollback: voltar para config offline/cache conhecido ou desabilitar servico sem reinstalar SO.

## Decisoes humanas pendentes

- Confirmar que `appliance-v0.1` deve partir de `c62354e` com hardening, e nao de `fe2de36` com backports.
- Confirmar se sincronismo global 00:05 UTC e requisito do v0.1 ou pode ficar desativado ate a fase seguinte.
- Confirmar tamanho real de `/data` e limite de cache inicial.
- Confirmar se `/data/spool/kiosky-state` e aceitavel para estado persistente, ou se deve existir `/data/state`.
- Confirmar se UI de configuracao existira em producao ou apenas em bancada.
- Confirmar politica de telemetria: off no v0.1, on sem spool, ou on com spool futuro.
- Confirmar stack grafica final para MPV: X11, Wayland, DRM/KMS ou outra.
- Confirmar `hwdec`: `auto-safe`, `auto`, ou `no` conforme MPV/driver da imagem.
- Confirmar retencao de logs: apenas stdout/journald volatil ou arquivo minimo em `/data/logs`.
- Confirmar usuario/grupo final: `totem:totem` ou outro padrao do projeto.

## Primeira implementacao recomendada

Sequencia minima para a primeira branch:

1. Criar branch `appliance-v0.1` no `kiosky-player` a partir de `c62354e`.
2. Sanitizar secrets e exemplos.
3. Adicionar `config.appliance.example.json`.
4. Desativar hotkeys/UI/telemetria/sync no perfil appliance.
5. Adicionar validacao de paths e runtime sem escrita em `/opt`.
6. Adicionar guarda de espaco livre em `download_media`.
7. Adicionar unit `systemd` de sistema como arquivo, sem instalar.
8. Adicionar testes com fake API/media/MPV e disco cheio.
9. Rodar suite local completa.
10. So depois preparar roteiro controlado para primeiro teste na Orange Pi.
