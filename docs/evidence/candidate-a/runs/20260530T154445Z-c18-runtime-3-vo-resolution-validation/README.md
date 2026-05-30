# C18.RUNTIME.3 — VO/resolution transition hypothesis validation

Rodada curta e limitada (decisao, nao producao). Correlacao read-only + teste
cirurgico/reversivel de `vo=drm`. Doc: `docs/product/183_*`. Placa restaurada ao
original ao final. Sanitizado (midia por fingerprint hash + resolucao; sem URLs/
secrets/IP).

## Step 1 — correlacao read-only (falhas vs resolucao / 1080p)
- 7 clips, 5 resolucoes distintas: 480x848 (x3), 480x720, 576x1024, 1080x1920, 480x688.
- plays=5628, media_load_failed=118 (~2.1%).
- res_change=99 (84%) vs same_res=19 (16%); base rate de transicoes com mudanca
  de resolucao = **86%**. Taxa de falha: res_change **2.1%**, same_res **2.4%**.
- involves_1080p=32 (~27%, proporcional aos ~28% de transicoes que envolvem 1080p).
- **Conclusao:** falhas **NAO correlacionam** com mudanca de resolucao nem com o
  clip 1080p — sao ~2% uniformes por `loadfile`, independente da resolucao.
  => **normalizacao de resolucao (B') NAO e suportada** como fix.

## Step 2 — teste cirurgico vo=drm (reversivel, /opt swap, auto-restore)
Forcado `mpv_vo=drm` (sem gpu-context) via override de 1 linha em build_mpv_args;
backup do /opt; health-check; janela de 15 min; restauracao ao final.

| metrica | vo=gpu (baseline) | vo=drm |
|---|---|---|
| media_load_failed rate | ~2.1% | **1.06%** (caiu ~metade, nao zerou) |
| restarts MPV em 15min | ~1-2 | **generation->89 (~88 restarts)** (watchdog thrashing) |
| MPV CPU steady | ~54% (1/2 core) | **mean 308% / max 372%** (~3 de 4 cores) |
| plays / max_gap | — | 94 / 29s |

- vo=drm **derruba pela metade** os media_load_failed (2.1%->1.06%) => confirma
  que o caminho **VO/GPU contribui** para ~metade dos stalls.
- PORÉM o render por software (scale + rotacao 270, ate 1080p) **satura ~3 cores**
  (308% CPU), o que **deixa o MPV sem servir o IPC** => ~88 reinicios do watchdog
  em 15 min (muito pior que 1 media_load_failed).
- **Decisao (criterio do usuario): vo=drm DEGRADA MUITO => DESCARTADO** como
  caminho de producao.
- Caveat: via SSH confirma-se que o MPV renderiza frames (time-pos avancando, sem
  erro de VO), mas a tela nao foi vista; regressao visual nao foi observada
  diretamente — porem os 88 restarts implicam instabilidade visivel (flashes).

## Decisao da rodada
- Option B (decode leve): refutado (R10 — init <0.5s).
- B' (normalizacao de resolucao): nao suportado (step 1 — falhas nao correlacionam).
- vo=drm (workaround de player-config): descartado (step 2 — CPU 308%, 88 restarts).
- O VO/GPU esta implicado (vo=drm cortou metade), mas **nenhum fix de
  player-config/conteudo e viavel**. => Restam **(A) imagem/userspace com HW decode
  (Cedrus/V4L2 Request)** ou **(C) aceitacao temporaria**. Decisao da equipe.
- **Limitacao NAO aceita** nesta rodada. **Sem imagem/kernel/release/backend.**

## Guardrails
image_built=false ; kernel_touched=false ; release_published=false ; backend_changed=false
real_config_permanently_changed=false (vo=drm via /opt swap reversivel, restaurado)
apt/pip/upgrade=false ; poweroff=false ; c12_readonly_touched=false
urls/secrets/api_url/api_key/environment_id/ssid/wifi/ip/mac/dns_published=false
board_restored_to_original=true (vo=gpu, sha 38ecb0de, estavel, 0 restarts pos-restore)
r4_kept_on_branch=c18-runtime-updater-perms-fix
