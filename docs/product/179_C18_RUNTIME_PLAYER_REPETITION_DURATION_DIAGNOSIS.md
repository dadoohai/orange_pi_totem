# 179 — C18.RUNTIME.1 Player Repetition & Duration Diagnosis (C17.4.2 board)

Rodada de **diagnostico orientado a evidencia** sobre a placa Orange Pi Zero 3
em imagem C17.4.2. Objetivo: explicar por que algumas midias parecem repetir/
loopar e se o tempo retornado pela API esta sendo usado como tempo de exibicao.
Nenhum release publicado, nenhum update remoto, nenhuma imagem, nenhum writer,
nenhuma alteracao de config real, nenhum poweroff/corte seco. Toda evidencia
sanitizada (sem URLs, sem api_url/api_key/environment_id, sem SSID/senha, sem
IP/MAC/DNS, sem payload bruto).

Evidencia: `docs/evidence/candidate-a/runs/20260529T200805Z-c18-runtime-player-repetition-duration-diagnosis/`.

## TL;DR

- **Duracao NAO e o problema.** A API search (Habitat) **retorna apenas
  `exposure_time_ms` (snake_case canonico)** para todas as campanhas ativas deste
  ambiente. **Nao retorna `exposureTimeMs`, nem `exposureTimeSeconds`, nem
  `duration`.** O player na placa (pre-C18.2) **honra `exposure_time_ms`
  corretamente**: as duracoes em runtime batem **exatamente** com as da API.
  **C18.2 nao mudaria o comportamento atual** (so importa se/quando a API passar
  a mandar aliases camelCase ou segundos).
- A playlist **avanca de forma previsivel** (0->1->...->6->wrap), confirmado por
  88 eventos de play / ~11 ciclos em 15 min, sem reset de indice, sem item
  repetido consecutivo no nivel de playlist, sem evento de sync/resync/poll.
- **Causa raiz provavel da repeticao percebida: `media_load_failed` ->
  reinicio do MPV pelo watchdog -> recarga do item atual.** Em ~89 min de
  servico ocorreram **11 reinicios de MPV, TODOS `media_load_failed`**, atingindo
  **todos os 7 ativos** de forma intermitente (~1 a cada 8 min), sem bloqueio
  permanente (0 cooldowns) e sem processos MPV orfaos (so 1 MPV vivo). Cada falha
  recarrega o item corrente => o espectador ve aquele item **reiniciar/piscar** e
  o tempo daquele item e perturbado. **Isto NAO e bug de campo de duracao e NAO e
  resolvido por C18.2.**
- A politica de **`--loop-file=inf` repetindo video curto para preencher a janela
  de exposicao** (documentada em C18.2 como `short_video_policy=repeat_to_fill_
  exposure`) e real, porem **pouco relevante no conteudo atual**: o monitor mediu
  cada clip com duracao ~igual a sua janela (`clip_s ~= exposure_time_ms`), logo
  `loops=0` no ciclo limpo.
- Descartado por evidencia: API duplicada (nao), playlist de 1 item (nao),
  sync/resync (0 eventos; chrony sub-ms), cache offline (online), scheduler
  travado (avanca normal).

## 1. Estado da placa

- Imagem: **C17.4.2** (ultima validada em cartao limpo).
- Placa: Orange Pi Zero 3; kernel `6.12.58-current-sunxi64`; Armbian 25.11.1.
- Host: redacted. Acesso por SSH apenas para diagnostico; senha nao salva, nao
  registrada em arquivo/log/doc/evidencia.
- Servicos: `kiosky-player.service=active`, `NetworkManager=active`,
  `ssh/sshd=active`, `chrony=active` (`systemd-timesyncd=inactive`),
  `totem-core.service=inactive`. `systemctl --failed`: **1** unidade
  (`aw859a-bluetooth.service`) — sem relacao com playback.
- chrony: stratum 2, offset sub-milissegundo, Leap Normal. Tempo do sistema
  estavel (relevante para sync/resync — ver secao 8).
- `totem-updatectl`: **ausente** nesta imagem (ferramental remoto C17.5+ nao
  presente em C17.4.2).

## 2. Qual player esta rodando (Parte 3)

A unit usa o launcher `/opt/totem/bin/totem-kiosky-launcher.sh` ->
`kiosky_service_launcher.sh`. O processo Python real (`/proc/<pid>/cmdline`)
executa:

```
/usr/bin/python3 /opt/totem/kiosky-player/kiosk.py --config <config.json>
```

- **board_player_source = `/opt`** (a imagem assada). O caminho de update remoto
  `/data/apps/kiosky-player/current` existe e aponta para um release staged
  (`homolog-...-c71318a`), porem **nao e o que executa** nesta imagem.
- Identificacao por checksum (sem imprimir conteudo):
  - `/opt/totem/kiosky-player/kiosk.py`: sha256 `38ecb0de...`, size `131071`,
    mtime `2026-05-14` (data do build C17.4.2). Confere **byte a byte** com o
    commit local **`307d986` (C18.1)** do repo kiosky-player.
  - `/data/apps/.../current/kiosk.py` (staged, nao ativo): sha256 `24539f00...`,
    size `119853` = commit local **`c71318a`**.
- Assinatura C18.2 no arquivo em execucao (`/opt`):
  `resolve_exposure_duration_ms=0`, `exposureTimeMs=0`, `exposureTimeSeconds=0`,
  `duration_source=0`; expressao antiga presente
  (`exposure_time_ms ... or cfg[...default_duration_ms]` = 1).
- **board_has_c18_2_duration_fix = false** (confirmado por conteudo + assinatura
  + expressao antiga). HEAD local do repo e `d4e4c4e` (C18.2); a placa esta
  exatamente **1 commit de kiosk.py atras** do fix de duracao.

Logica de duracao do player em execucao (pre-C18.2):

```python
duration_ms = int(campaign.get("exposure_time_ms") or cfg["default_duration_ms"])
```

So `exposure_time_ms` (snake_case) e honrado. `exposureTimeMs`,
`exposureTimeSeconds` e `duration` seriam **ignorados** e cairiam no
`default_duration_ms` (default `10000` ms). `default_duration_ms` **nao**
sobrescreve um valor valido de `exposure_time_ms`.

## 3. Shape da API search (Parte 4, sanitizado)

Probe `/tmp/dadooh_player_api_probe.py` carregou a config **internamente** (via
`kiosk.load_config`, identico ao player) e chamou a **mesma** rota search:

- `endpoint_kind=search`, `method=POST`, auth via header `x-api-key`.
- payload: `{environmentId, onlyStandby, searchIn, includeDescendants, limit}`
  (mesmos valores do player: `onlyStandby=true`, `searchIn=campaign`,
  `includeDescendants=true`, `limit=20`).
- `has_environment_id=true`, `has_station_id=true`, `has_auth=true`.
- Resposta: `units_count=1`, `campaigns_total=7`, `campaigns_active=7`
  (`status=ativa`), `unit_status=online`, `media_items_count=7`,
  `content_empty=false`. **Sem payload bruto, sem URLs.**

## 4. Campos de duracao retornados (Parte 4/5)

Varredura de campos de duracao nas 7 campanhas ativas:

| campo                 | contagem |
|-----------------------|----------|
| `exposure_time_ms`    | **7**    |
| `exposureTimeMs`      | 0        |
| `exposureTimeSeconds` | 0        |
| `duration`            | 0        |
| `durationMs`          | 0        |
| outros `*duration*/*expos*` | nenhum |
| sem qualquer duracao  | 0        |

Valores (C18.2-normalizados, ms): min `3900`, max `28100`,
amostra `[3900, 5000, 5100, 7200, 15100, 28100]`. `all_equal_default=false`.

Comparacao logica antiga (placa) vs C18.2:
`campaigns_board_uses_default=0`, `campaigns_alias_only_board_would_default=0`,
`board_vs_c18_2_mismatch_count=0`.

**Conclusao:** a API entrega o campo canonico que a placa entende. A placa nunca
cai no default neste ambiente.

## 5. O player usa o tempo da API? (Parte 5)

Sim. Os fingerprints de midia da API (`sha1(url)[:10]`) batem **exatamente** com
os aliases `media-<fp>` que o player loga em runtime, e as duracoes coincidem:

| media_fp     | api_field         | api_ms | player_duration_ms (journal) | matched |
|--------------|-------------------|--------|------------------------------|---------|
| 63e22e276f   | exposure_time_ms  | 15100  | 15100 (index 0)              | true    |
| b04db49d99   | exposure_time_ms  | 15100  | 15100 (index 1)              | true    |
| 8e4d41f6c2   | exposure_time_ms  | 7200   | 7200  (index 2)              | true    |
| fba32b0055   | exposure_time_ms  | 5100   | 5100  (index 3)              | true    |
| 749f1db21b   | exposure_time_ms  | 3900   | 3900  (index 4)              | true    |
| b8c9a5f04c   | exposure_time_ms  | 28100  | 28100 (index 5)              | true    |
| 7eefea6ba2   | exposure_time_ms  | 5000   | 5000  (index 6)              | true    |

Fonte de duracao do player na placa: **logs sanitizados** (`journalctl -u
kiosky-player`), que registram `Playing media alias=... index=... duration_ms=...
offset_ms=...`. A placa pre-C18.2 **nao** expoe `duration_source`
(`duration_source_not_available=true`), mas como so existe um campo possivel
(`exposure_time_ms`) a fonte e inequivoca.

- `player_uses_api_duration = true`
- `player_uses_default_duration = false`
- `default_duration_overrides_api = false`

## 6. Por que algumas midias repetem (Parte 6/7)

Mecanismo de exibicao do player (identico em c71318a/C18.1/HEAD; so a resolucao
de duracao mudou em C18.2):

- MPV e iniciado com **`--loop-file=inf`** e `--image-display-duration=inf`,
  `--idle=yes`, `--keep-open=yes`, `--vo=gpu --gpu-context=drm`,
  `--video-rotate=270`, IPC em `/tmp/kiosky/mpv.sock`. **Nao** ha
  `--loop-playlist`.
- O avanco entre itens e **dirigido pelo scheduler**: o item toca por
  `exposure_time_ms`; ao fim da janela o player envia `loadfile <path> replace`
  para o proximo item. MPV nao decide o avanco; eventos `end-file` nao sao
  observados (so watchdog por ping).
- Consequencia: se o **clip e mais curto que a janela** `exposure_time_ms`,
  `--loop-file=inf` **repete o clip** ate a janela fechar. Exemplo: uma campanha
  com `exposure_time_ms=28100` (28,1 s) cujo video tenha ~5 s aparece repetindo
  ~5x antes de avancar. E exatamente o que o operador percebe como "repete/
  loopa".

Esta repeticao **dentro do slot** e a politica **intencional** ja registrada em
C18.2: `short_video_policy=repeat_to_fill_exposure`,
`short_video_loop_intentional=true`. Porem, no **conteudo atual**, o monitor de
runtime mediu `clip_s ~= exposure_time_ms` para todos os itens (ex.: clip 28,06 s
em janela 28,1 s; clip 7,22 s em janela 7,2 s), logo `loops=0` no ciclo limpo —
ou seja, **a politica de loop-fill quase nao atua agora**. Ela so geraria
repeticao visivel se uma campanha tiver `exposure_time_ms` maior que a duracao
real do criativo.

### Causa raiz provavel: media_load_failed -> reinicio do MPV -> recarga do item

A unica anomalia recorrente observada em runtime sao **reinicios do MPV pelo
watchdog por `media_load_failed`**:

- **11 reinicios de MPV desde o start do servico (~89 min)**, **100%
  `media_load_failed`** (`generation` chegou a 11; nenhum `ipc_unresponsive`,
  nenhum `path_mismatch`).
- Atingem **todos os 7 ativos** proporcionalmente (b04db49d99, 8e4d41f6c2,
  749f1db21b, 63e22e276f: 6x cada; fba32b0055, b8c9a5f04c, 7eefea6ba2: 3x cada)
  => **nao e um asset corrompido especifico**, e flakiness sistemica de
  verificacao de carga (provavel timeout de load/first-frame no SoC de baixa
  potencia).
- **0 eventos de block/cooldown** => nenhum item e descartado; a recarga sempre
  recupera. So 1 processo MPV vivo (sem orfaos).
- Efeito: em `media_load_failed` o player reinicia o MPV e **recarrega o item
  corrente**; o espectador ve aquele item **reiniciar/piscar** (~1 a cada 8 min)
  e a janela daquele item e perturbada. Isto explica tanto "parece repetir/
  loopar" quanto "parece nao respeitar o tempo" para itens isolados, **sem** que
  haja qualquer erro de duracao.

Classificacao: `repeat_issue_cause = media_load_failure_retries_previous`
(recarga do item corrente apos falha de carga). Contribuinte secundario e
condicional: `mpv_loop_file_inf_repeats_short_video` (politica de fill, pouco
ativa no conteudo atual).

Descartado por evidencia:
- `api_returns_duplicate_media`: **falso** (`duplicates=false`, 7 fps distintos).
- `playlist_single_item`: **falso** (7 itens).
- `api_returns_same_playlist_order_and_player_restarts`: poll a cada 1800 s, so
  reaplica em mudanca de fingerprint; fingerprint estavel; 0 eventos de poll no
  monitor.
- `sync_resync_reloads_same_item`: **falso** (0 eventos de sync/resync; chrony
  sub-ms).
- `cache_reload_reselects_same_item`: caminho de cache so em offline; placa
  online.
- `player_scheduler_does_not_advance`: **falso** (indice avanca 0->6->wrap, 88
  plays/15min, `index_monotonic_wrap=true`).

## 7. Sync/resync (Parte 8)

- `sync_enabled` default **true**; `sync_drift_threshold_ms=300`,
  `sync_hard_resync_ms=1200`, `sync_checkpoint_interval_sec=3600`,
  `sync_prep_mode=play_then_resync`.
- `classify_drift_action`: `none` se `|drift|<300ms`; `soft_resync` ate 1200ms;
  `hard_resync` acima. Um resync recomputa a posicao do ciclo via UTC e **pode**
  recarregar o mesmo item — porem so dispara com drift relevante.
- Com chrony estavel (offset sub-ms), o drift fica **abaixo** do threshold, logo
  a acao classificada e `none`: resync praticamente **nao dispara**. Checkpoint
  so a cada 1 h.
- `sync_related_to_repeat = false` (a repeticao observada e o loop intra-slot, ja
  explicado). Confirmacao final pelos eventos do monitor de runtime — ver
  secao 9.

## 8. C18.2 resolve o problema?

- **Para o problema atual: nao muda nada.** A API ja usa `exposure_time_ms`
  canonico, que a placa honra. C18.2 normaliza tambem `exposureTimeMs` e
  `exposureTimeSeconds` e ignora `duration` ambiguo — uteis **somente** se a API
  mudar o formato no futuro.
- C18.2 e valioso como **robustez/forward-compat** e por **tornar visivel** a
  fonte de duracao (`duration_source` no status), o que facilita diagnostico. E
  recomendado empacotar para a placa de qualquer forma, mas **nao** e o que
  corrige a percepcao de "repeticao".
- A causa raiz da percepcao do operador e de **dado/criativo**: janelas
  `exposure_time_ms` maiores que a duracao real do clip, preenchidas por
  `loop-file=inf` (politica intencional). Acao recomendada na secao 10.

## 9. Monitor de runtime (Parte 6) — resultados

Monitor passivo `/tmp/dadooh_player_runtime_monitor.py` (somente leitura: MPV IPC
`get_property` — nunca loadfile/seek/set — + journalctl sanitizado), 900 s, 450
amostras a cada 2 s. Detalhe em `runtime_monitor_summary.md`.

- `monitor_duration_sec=900`, `ipc_available=true`.
- **Avanco**: `journal_play_events=88`, sequencia de indices = repeticao limpa
  `...4,5,6,0,1,2,3,4,5,6,0...` (`index_monotonic_wrap=true`),
  `repeated_same_item_consecutive=0`. Na janela estrita de 15 min: 79 plays,
  **max_gap entre plays = 29 s** (== item de 28,1 s) — **sem stall**.
- **Duracao observada vs janela**: `expected_vs_observed_mismatches=0`; cada slot
  do primeiro ciclo teve `clip_s ~= exposure_time_ms` e `loops=0`.
- **Sync/poll**: `sync_events_count=0`, `poll_events_count=0` na janela.
- **MPV restarts**: `generation` 8->9->10 durante o monitor; **1-2 reinicios**,
  todos `media_load_failed` (ver secao 6). `mpv_proc_count=1` ao final (sem
  orfaos).
- **Artefato de medicao**: o ultimo "slot" do monitor reportou o item index0 em
  loop por ~290 s (19 loops). Isto e **falso** — efeito de socket IPC orfao apos
  o reinicio do MPV (o monitor mantinha conexao com a geracao antiga). O journal
  (fonte autoritativa do player) prova avanco continuo no mesmo intervalo (88
  plays, max_gap 29 s). Registrado como artefato, nao como comportamento do
  player.

## 10. Proxima acao recomendada

1. **Duracao: nenhuma acao de codigo necessaria** para este ambiente — o player
   honra `exposure_time_ms`. Nenhuma alteracao foi feita na placa nesta rodada.
2. **Causa raiz da repeticao = `media_load_failed` -> reinicio do MPV ->
   recarga do item.** Proximo passo (NOVO fix de runtime, ainda nao
   implementado, fora desta rodada de diagnostico):
   - investigar por que `loadfile`/first-frame falha intermitentemente neste SoC
     (timeout de verificacao de carga, `hwdec=auto` vs decode por software,
     pressao de I/O ao ler de `/data/media`, tamanho/codec do criativo);
   - aumentar a janela de tolerancia de carga / grace do watchdog para
     first-frame antes de declarar `media_load_failed`, e/ou recarregar com
     `offset_ms` preservado (retomar em vez de reiniciar do zero) para nao gerar
     repeticao visivel;
   - validar em **hardware** (`hardware_validation_required=true`).
3. **C18.2 (`d4e4c4e`)** pode ser empacotado como RC **independente** (robustez de
   aliases camelCase/segundos + `duration_source` observavel). E util como
   forward-compat/observabilidade, mas **nao resolve** a repeticao atual; portanto
   nao deve ser anunciado como "fix da repeticao". RC, nunca deploy automatico.
4. Para conteudo: opcionalmente alinhar `exposure_time_ms` a duracao real do
   criativo e/ou definir explicitamente a politica de preenchimento (loop vs
   congelar ultimo frame), hoje implicitamente "loop para preencher".
5. Manter C12/read-only bloqueado e fora de escopo.

## Versionamento observado (sanitizado)

- board `/opt` player == `307d986` (C18.1), sha256 `38ecb0de...`.
- board `/data/apps/current` (staged, inativo) == `c71318a`, sha256 `24539f00...`.
- repo HEAD kiosky-player == `d4e4c4e` (C18.2), nao presente na placa.
- repo orange_pi_totem HEAD == `bbbea28` (C17.9); arvore limpa; manifest JSON
  valido.
