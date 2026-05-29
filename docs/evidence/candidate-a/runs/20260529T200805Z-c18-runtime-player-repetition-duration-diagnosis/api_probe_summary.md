# API search probe + duration cross-reference (sanitized) — Parts 4 & 5

Script `/tmp/dadooh_player_api_probe.py` na placa. Config lida **internamente**
via `kiosk.load_config` (identico ao player). **Sem payload bruto, sem URLs, sem
api_url/api_key/environment_id.** Apenas contagens, enums, ms e fingerprints
(`sha1(url)[:10]`).

## Request shape
- config_loader=kiosk.load_config (request byte-identico ao player)
- endpoint_kind=search ; method=POST ; auth via header x-api-key
- payload_keys=[environmentId, onlyStandby, searchIn, includeDescendants, limit]
- valores: onlyStandby=true, searchIn=campaign, includeDescendants=true, limit=20
- has_environment_id=true ; has_station_id=true ; has_auth=true
- config_default_duration_ms=10000 ; config_status_file_set=true

## Response summary
- http_status=200, http_ok=true
- units_count=1 ; campaigns_total=7 ; campaigns_active=7 ; media_items_count=7
- campaign_status_values=['ativa'] ; unit_status_values=['online']
- content_empty=false

## Duration fields seen (7 campanhas ativas)
| campo                 | count |
|-----------------------|-------|
| exposure_time_ms      | **7** |
| exposureTimeMs        | 0     |
| exposureTimeSeconds   | 0     |
| duration              | 0     |
| durationMs            | 0     |
| duration_ms           | 0     |
| exposureTime          | 0     |
| exposure_seconds      | 0     |
| other_duration_like_keys | [] |
| missing_any_duration  | 0     |

## Duration values (C18.2-normalizado, ms)
- min_ms=3900 ; max_ms=28100
- sample_values_ms=[3900, 5000, 5100, 7200, 15100, 28100]
- all_equal_default=false

## Board resolution comparison (logica antiga da placa vs C18.2)
- active_campaigns=7
- campaigns_board_uses_default=0
- campaigns_alias_only_board_would_default=0
- board_vs_c18_2_mismatch_count=0

## Media fingerprints / sequence
- media_fingerprints=[63e22e276f, b04db49d99, 8e4d41f6c2, fba32b0055, 749f1db21b, b8c9a5f04c, 7eefea6ba2]
- duplicates=false
- single_item_playlist=false

## Part 5 table — fp | api_field | api_ms | player_duration_ms (journal) | matched
(player_duration vindo de logs sanitizados `Playing media ... duration_ms=...`;
placa pre-C18.2 nao expoe duration_source, mas so existe um campo possivel)

| media_fp   | api_field        | api_ms | player_ms | matched |
|------------|------------------|--------|-----------|---------|
| 63e22e276f | exposure_time_ms | 15100  | 15100     | true    |
| b04db49d99 | exposure_time_ms | 15100  | 15100     | true    |
| 8e4d41f6c2 | exposure_time_ms | 7200   | 7200      | true    |
| fba32b0055 | exposure_time_ms | 5100   | 5100      | true    |
| 749f1db21b | exposure_time_ms | 3900   | 3900      | true    |
| b8c9a5f04c | exposure_time_ms | 28100  | 28100     | true    |
| 7eefea6ba2 | exposure_time_ms | 5000   | 5000      | true    |

## Conclusao
- API retorna SOMENTE `exposure_time_ms` (canonico). Sem aliases camelCase, sem
  segundos, sem `duration`.
- O player (pre-C18.2) honra `exposure_time_ms` corretamente; duracoes batem
  exatamente. `player_uses_api_duration=true`,
  `player_uses_default_duration=false`, `default_duration_overrides_api=false`.
- duration_issue_cause = api_returns_only_exposure_time_ms_and_player_uses_it_correctly
- C18.2 nao alteraria o comportamento atual neste ambiente.

## Guardrails do probe
- api_payload_raw_published=false ; media_urls_published=false
- api_url/api_key/environment_id/station_id NUNCA impressos
- resposta bruta nao salva
