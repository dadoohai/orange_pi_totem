# 180 — C18.RUNTIME.2 media_load_failed Soft-Retry Fix (kiosky-player)

> **REFUTADO E REVERTIDO (ver doc 182).** A validacao em hardware mostrou que o
> soft-retry **nao resolve** o `media_load_failed` (0 recoveries; restart mesmo
> assim; prolonga o lingering). A causa raiz e **software decode**
> (`hwdec-current=no`): o init de `loadfile` satura o main thread do MPV >8s e
> bloqueia o IPC — nenhum fix de timeout/retry no player resolve. O commit
> `kiosky-player@7ca6691` foi **revertido** em `e76204a` (de volta a baseline
> C18.2). Este documento fica como registro historico da tentativa. Conclusao e
> evidencia no doc **182**.

Rodada de **correcao** derivada do diagnostico C18.RUNTIME.1 (doc 179). Corrige a
causa raiz provavel da repeticao/percepcao de tempo incorreto observada pelo
operador na placa C17.4.2: reinicios desnecessarios do MPV por
`media_load_failed`. Fix **em repo** (`kiosky-player`), validado em simulacao;
**sem deploy na placa, sem release, sem update remoto**. Validacao em hardware
permanece obrigatoria.

Commit: `kiosky-player@7ca6691` (branch `appliance-v0.1`).
Diagnostico de origem: `docs/product/179_C18_RUNTIME_PLAYER_REPETITION_DURATION_DIAGNOSIS.md`.

## Problema (de C18.RUNTIME.1)

Na placa C17.4.2 (player `/opt` == commit `307d986`/C18.1, sem C18.2), o
diagnostico mostrou que **duracao nao e o problema** (a API retorna so
`exposure_time_ms` e o player honra 1:1). A unica anomalia recorrente eram
**reinicios do MPV pelo watchdog**: 11 em ~89 min, **100% `media_load_failed`**,
atingindo todos os 7 ativos intermitentemente, com 0 cooldown/skip permanente e
nenhum MPV orfao. Cada reinicio recarrega o item corrente => o espectador ve o
item **reiniciar/piscar** e o tempo daquele item e perturbado.

## Causa raiz

`MPVController.load_file()` considera falha quando o **ACK IPC do comando
`loadfile`** nao retorna `success` dentro de `mpv_ipc_timeout_sec` (2.0s). Ao
primeiro ACK falho, o player fazia um **restart completo do MPV**
(`mpv_watchdog_grace_after_load_sec=0`), visivel como tela preta + recarga do
item. Como o MPV normalmente confirma `loadfile` em milissegundos, timeouts de
2s intermitentes em **todos** os assets indicam **contencao transitoria do IPC**
no SoC de baixa potencia (H618), nao corrupcao de midia (a reproducao funciona
bem o resto do tempo, com duracoes corretas e 0 bloqueios permanentes).

## Correcao

Antes de escalar para o restart completo do MPV, **reenviar o `loadfile`** ate
`mpv_load_soft_retries` vezes (default **2**, intervalo
`mpv_load_soft_retry_delay_sec` default **0.3s**). Se o reenvio carregar, segue a
reproducao sem restart visivel. Se nao, mantem-se o comportamento atual (restart
+ retry + cooldown + skip). E **estritamente mais seguro**: falhas reais ainda
reiniciam; o caminho de ping do watchdog nao muda; so reduz restarts
desnecessarios.

- `kiosk.py`: `playback_loop` ganha o laco de soft-retry antes do
  `mpv.restart(...)`; novas chaves em `DEFAULT_CONFIG`.
- `tests/fakes/player_simulation.py`: `FakeMPV` ganha `transient_fail_counts`
  (modela ACK que falha N vezes e depois carrega); o laco do simulador espelha o
  soft-retry e registra `media_load_recovered_without_restart`.
- `config.appliance.example.json` / `config.example.json`: documentam as novas
  chaves.

### Novos parametros (defaults seguros)
| chave                            | default | efeito |
|----------------------------------|---------|--------|
| `mpv_load_soft_retries`          | 2       | reenvios de loadfile antes do restart |
| `mpv_load_soft_retry_delay_sec`  | 0.3     | intervalo entre reenvios |

## Testes

- `python3 -m py_compile kiosk.py tests/fakes/player_simulation.py tests/test_player_timing_simulation.py`
- `python3 -m unittest discover -s tests` => **101 OK** (era 99; +2).
- Novos cenarios:
  - `test_transient_load_failure_recovers_without_mpv_restart`: ACK falha 1x e
    recupera no reenvio => **sem restart**, ambos itens tocam.
  - `test_transient_load_failure_beyond_soft_retries_still_restarts`: falhas
    acima do limite => **escalacao para restart preservada**.
- Regressao: `test_media_load_failure_advances_or_errors_cleanly` (falha
  permanente) continua reiniciando e avancando.

## Status

- `c18_runtime_2_status=fixed_in_repo_sim_validated`
- `player_code_changed=true`, `scheduler_changed=false`, `sync_changed=false`,
  `duration_changed=false`, `watchdog_ping_changed=false`
- `board_touched=false`, `release_published=false`, `update_pushed=false`
- `hardware_validation_required=true`
- `ready_for_c18_3_release_package=true` (junto com C18.2; ambos pre-C18.2/board)

## Pendencias / honestidade

- O diagnostico C18.RUNTIME.1 inferiu o mecanismo (ACK timeout transitorio) a
  partir de codigo + comportamento; o `duration_sec` exato dos eventos
  `loadfile returned error` **nao foi capturado** porque a placa ficou
  **inacessivel via SSH** (porta 22 caiu) no meio da rodada do fix. O soft-retry
  e robusto independente disso (ACK lento OU erro transitorio sao ambos
  cobertos), mas a confirmacao em hardware deve: (a) capturar `duration_sec`
  para confirmar timeout vs erro; (b) medir a queda na taxa de
  `media_load_failed`/restart com o fix; (c) considerar tambem aumentar
  `mpv_ipc_timeout_sec` para `loadfile` e/ou `mpv_watchdog_grace_after_load_sec`
  se o reenvio nao bastar.
- Empacotamento como release candidate e validacao fisica em Orange Pi sao o
  proximo passo (C18.3), fora desta rodada.
