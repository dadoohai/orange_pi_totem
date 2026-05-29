# Runtime monitor (sanitized) — Part 6

Monitor passivo `/tmp/dadooh_player_runtime_monitor.py`. Somente leitura: MPV IPC
`get_property` (NUNCA loadfile/seek/set) + `journalctl` parseado e sanitizado.
Fingerprints = `sha1(path)[:10]` (monitor) / `sha1(url)[:10]` (alias do journal).
Sem URLs, sem paths reais, sem secrets.

## Parametros
- monitor_duration_sec=900 (15 min), sample_interval_sec=2.0, samples=450
- ipc_available=true
- start ~17:06:56 (-03)

## Avanco da playlist (autoritativo = journal do player)
- journal_play_events=88 (~11 ciclos); janela estrita 15 min = 79 plays
- index_sequence = repeticao limpa: ...4,5,6,0,1,2,3,4,5,6,0,1,2,3...
- index_monotonic_wrap=true
- repeated_same_item_consecutive=0
- max_gap entre plays = 29 s (== item de 28,1 s); **sem stall**
- unique_items_seen_count=7 ; playlist_single_item=false
- expected_vs_observed_mismatches=0

## Janela vs duracao real do clip (primeiro ciclo limpo)
| index | exposure_time_ms | clip_s (MPV) | loops |
|-------|------------------|--------------|-------|
| 0     | 15100            | 15.07        | 0     |
| 1     | 15100            | 15.10        | 0     |
| 2     | 7200             | 7.22         | 0     |
| 3     | 5100             | 5.06         | 0     |
| 4     | 3900             | 3.90         | 0     |
| 5     | 28100            | 28.06        | 0     |
| 6     | 5000             | 5.04         | 0     |

=> conteudo atual tem `clip ~= janela`; politica de loop-fill quase nao atua.

## Sync / poll
- sync_events_count=0 ; poll_events_count=0 (janela de 15 min)
- chrony estavel (offset sub-ms) => drift < threshold (300 ms) => acao `none`
- resync_seen=false ; resync_reloaded_same_item=false

## MPV watchdog restarts (causa raiz provavel da repeticao)
- total_mpv_restarts_since_service_start=11 (~89 min) => ~1 a cada 8 min
- reason histogram: **11x `media_load_failed`** (0 outros)
- max_generation=11 ; durante o monitor: gen 8 -> 9 -> 10
- media_load_failed por fingerprint (proporcional ao uso, nao asset unico):
  b04db49d99=6, 8e4d41f6c2=6, 749f1db21b=6, 63e22e276f=6, fba32b0055=3,
  b8c9a5f04c=3, 7eefea6ba2=3
- block/cooldown events=0 (nenhum item descartado; recarga recupera)
- mpv_proc_count=1 ao final (sem processos MPV orfaos)
- efeito: recarga do item corrente => reinicio/piscar visivel + perturbacao da
  janela daquele item

## Artefato de medicao (registrado para honestidade)
O ultimo "slot" do monitor reportou index0 em loop por ~290 s / 19 loops. **Falso
positivo**: o monitor manteve a conexao IPC com a geracao antiga do MPV; apos o
reinicio do MPV o socket orfao devolveu `path`/`time-pos` velhos. O journal prova
avanco continuo no mesmo intervalo (88 plays, max_gap 29 s). Conclusao do monitor
sobre repeticao baseia-se no journal + histograma de restart, nao neste artefato.

## Classificacao
- repeat_issue_cause = media_load_failure_retries_previous (primario)
  + mpv_loop_file_inf_repeats_short_video (secundario/condicional)
- sync_status = enabled_stable
- mpv_loop_policy_status = loop_file_inf_present
