# C18 Operational Resume Current Session

Snapshot de retomada operacional para a placa allowlisted do piloto C18,
coletado antes de qualquer apply, rollback, thaw, publish ou power-loss.

Resultado:

- `operational-resume.json`: `passed=true`;
- `result_claim=c18_operational_resume_ready`;
- autorizacao atual: `2026-06-17T05:51:57Z` a `2026-06-17T09:51:57Z`;
- preflight fresco `pre_apply`: coletado em `2026-06-17T05:56:16Z`;
- target: `c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`;
- channel/ring: `homologation` / `pilot`.

O preflight da placa confirmou:

- policy `homologation`, `allow_prerelease=true`, `allow_downgrade=false`;
- `allowed_components=["totem-core"]`;
- timer de update desabilitado e inativo;
- freeze publico de `player-runtime` preservado via `rc=44`;
- imagem `c18-hwdecode-lab-1x` e marker esperado;
- stack C18 de MPV/hwdec ativa.

Non-claims:

- nao autoriza producao;
- nao promove `stable`;
- nao habilita auto-pull;
- nao publica releases;
- nao abre public thaw;
- nao satisfaz soak 24h;
- nao satisfaz matriz power-loss 17/17;
- nao substitui H2 readiness.
