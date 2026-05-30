# C18.RUNTIME.3 — gpu-shader-cache-dir test (last cheap player-config workaround)

Teste cirurgico/reversivel (/opt swap, auto-restore, vo=gpu mantido). Placa
restaurada ao original. Sanitizado.

## Resultado (25 min)
- running: vo=--vo=gpu + `--gpu-shader-cache-dir` ativo (shader_cache=1).
- plays=138, media_load_failed_restarts=2, loadfile_send_failed=5.
- **failure_rate=1.45%** (baseline vo=gpu ~2.1%) — dentro do ruido; **NAO eliminou**.
- **cache_files_final=0** (cache nunca populou) => MPV nao compila shader por
  transicao; o cache nao tem o que otimizar => o custo por `loadfile` do caminho
  GPU **nao e compilacao de shader**.
- mpv_cpu (top) mean 113% / max 235% (regime normal de vo=gpu; sem regressao —
  metodologia top, comparavel ao vo=drm que deu 308%).

## Conclusao
`gpu-shader-cache-dir` **NAO resolve**. Com isso, **encerram-se as tentativas
baratas de player-config** (soft-retry, recv-timeout, send-timeout, normalizacao
de resolucao, vo=drm, shader-cache — todas refutadas/descartadas/sem efeito).

Restam apenas: **(A) imagem/userspace com HW decode (Cedrus/V4L2 Request)** —
plano em `docs/product/184_*` — ou **(C) aceitacao temporaria** (somente com
decisao humana). R4 (perms do updater) integrado em rodada propria.

## Guardrails
image_built=false ; kernel_touched=false ; release_published=false ; backend_changed=false
real_config_permanently_changed=false (shader-cache via /opt swap reversivel, restaurado)
apt/pip/upgrade=false ; poweroff=false ; c12_readonly_touched=false
urls/secrets/api_url/api_key/environment_id/ssid/wifi/ip/mac/dns_published=false
board_restored_to_original=true (vo=gpu, 38ecb0de, estavel, 0 restarts pos-restore; shader-cache dir removido)
limitation_C_accepted=false
