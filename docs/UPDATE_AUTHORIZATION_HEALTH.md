# C18 - Autorizacao De Update E Health Gates

Nota operacional curta para dev/IA retomar a linha C18 sem abrir caminho
acidental para update inseguro. Em caso de divergencia, o contrato vigente esta
em `docs/UPDATE_CONTRACT.md`; o baseline live fica em
`docs/product/189_C18_OTA_READINESS_GATE.md`.

## Estado Operacional Vigente (2026-06-16)

C18 Homologation RC esta pronta para piloto assistido, nao para producao. O
alvo corrente e
`c18.player-runtime-homolog-20260611-mpv-path-verify-c16fb3e`, em
`channel=homologation` e `ring=pilot`. A evidencia operacional atual esta em
`docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/`,
com retomada operacional em
`docs/evidence/c18-update-validation/20260617T055616Z-operational-resume-current-af1bb94/`
e macro-governanca atual em
`docs/evidence/c18-update-validation/20260617T064617Z-current-macro-governance-a761a67/`.
A trilha de 2026-06-12 continua preservada como rastreabilidade historica:
H1 decisive traceability refresh em
`docs/evidence/c18-update-validation/20260612T194911Z-1x-h1-decisive-traceability-refresh-7e40e80/h1-release-gate.json`,
autorizacao historica de piloto em
`docs/evidence/c18-update-validation/20260612T195336Z-pilot-authorization-traceability-refresh/pilot-authorization.json`
e pilot readiness traceability refresh em
`docs/evidence/c18-update-validation/20260612T195516Z-pilot-readiness-traceability-refresh-c16fb3e/`.
O snapshot H2 corrente esta versionado em
`docs/evidence/c18-update-validation/20260617T030214Z-current-h2-readiness-13d4cbd/`:
H1, server-side, repo clean e tracked inputs verdes; H2/producao ainda vermelho.
O agregador macro pre-H2 e `scripts/qa/c18_ota_macro_governance_gate.py`; ele
valida o retrato versionado de H1, pilot readiness, H2 vermelho e diagnostico
read-only de placa. Esse gate nao substitui H2, nao reabre janela expirada de
piloto, nao publica, nao promove `stable`, nao liga auto-pull e nao autoriza
producao.
Snapshot versionado:
`docs/evidence/c18-update-validation/20260617T064617Z-current-macro-governance-a761a67/`.
O snapshot pre-soak scale governance atual esta em
`docs/evidence/c18-update-validation/20260617T065222Z-pre-soak-scale-governance-6937b26/`:
`c18_ota_pre_soak_scale_governance_gate.py` verde em arvore limpa, com release
gate interno verde, H2 ainda vermelho pelos blockers esperados, server-side
atual, preflight H2 power-loss aceito e retomada operacional default-deny. Esse
snapshot sustenta a governanca pre-soak para escala; nao autoriza producao,
`stable`, auto-pull, publish, public thaw, soak 24h nem power-loss 17/17.
Retomada operacional agora passa por
`scripts/qa/c18_ota_operational_resume_gate.py`. Esse gate nao usa o snapshot
como autorizacao viva: exige nova janela ativa e preflight `pre_apply` fresco da
placa. Com a autorizacao/preflight antigos, o resultado correto e bloqueado por
janela expirada e preflight velho.
O preflight fresco deve ser produzido por
`scripts/board/c18_homologation_pilot_preflight_collect.py`, coletado na placa
sem reconcile de manutencao autorizado e commitado antes do gate de retomada.
Snapshot do bloqueio:
`docs/evidence/c18-update-validation/20260616T224130Z-operational-resume-blocked-99c0af8/`.
O refresh operacional atual esta versionado em
`docs/evidence/c18-update-validation/20260617T055616Z-operational-resume-current-af1bb94/`:
autorizacao da janela atual + preflight `pre_apply` fresco da placa +
`c18_ota_operational_resume_gate.py` verde. Isso libera apenas retomada
assistida do piloto em homologacao; H2/producao permanecem bloqueados.
O pilot readiness atual, rerodado sobre esse refresh operacional, esta em
`docs/evidence/c18-update-validation/20260616T232546Z-current-pilot-readiness-5b2128c/`:
`c18_player_runtime_pilot_readiness_gate.py` verde com H1 decisivo, pacote
`c16fb3e`, autorizacao vigente, preflight fresco e cinco checkpoints P0
seletivos. Ele substitui o readiness antigo somente para a retomada operacional
atual; nao reduz blockers H2.

O piloto controlado autoriza somente entrega assistida por operador, com
rollback pronto, allowlist de devices, preflight de placa, H1 decisivo
image-bound e P0 power-loss seletivo. Ele nao autoriza producao, `stable`,
auto-pull, thaw publico, soak 24h, power-loss 17/17 nem pular H2.

A familia server-side/signature do alvo `c16fb3e` tambem esta gateada no host,
sem publicar release e sem habilitar auto-pull, em
`docs/evidence/c18-update-validation/20260612T125127Z-server-side-governance-c16fb3e/`.
O snapshot corrente de revalidacao server-side esta em
`docs/evidence/c18-update-validation/20260617T001804Z-server-side-current-c16fb3e/`:
`c18_server_side_publish_governance_gate.py` verde para `player-runtime`, trust
anchor externo verificado e lista de 14 assets assinados/atestados hash-bound.
O inventario versionavel dos assets server-side desse pacote esta em
`docs/evidence/c18-update-validation/20260612T172602Z-server-side-asset-list-c16fb3e/`,
com paths repo-relative, bytes e SHA256; ele tambem nao publica, nao promove
`stable` e nao abre thaw.
O diagnostico operacional read-only tambem esta versionado em
`docs/evidence/c18-update-validation/20260612T183722Z-board-readonly-diagnostics-17a1f9d/`:
appliance `player_running`, playback `playing`, `privacy_scan=ok`, config
content nao lido e display `unknown` por HDMI `connected`/`enabled` com modos,
mas sem arquivo `mode` observavel no sysfs da placa. Essa evidencia ajuda
suporte/homologacao, mas nao substitui deep-health, power-loss, soak, H2,
`stable`, producao, publish, auto-pull ou thaw.
Depois disso, H2/stable/producao continuam bloqueados por quatro itens:
power-loss 17/17, soak 24h, stable promotion e decisao formal de thaw.
Os blockers exatos esperados continuam:
`full_physical_powerloss_matrix:powerloss_matrix_incomplete`,
`soak_endurance_24h:missing_24h_soak_summary`,
`stable_promotion_authorization:missing_stable_promotion_evidence` e
`explicit_operator_thaw_decision:missing_operator_thaw_decision`.

Roots canonicos de artefato:

- `totem-core`: `releases/core-updates`;
- `player-runtime`: `releases/player-runtime`;
- `releases/totem-core`: nao canonico para C18;
- `releases/app-updates`: historico C14/kiosky, nao usar como C18 corrente.

## Modelo De Classes

| Classe | Inclui | Caminho de update |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, validadores, helpers de Wi-Fi/config, settings | OTA C18 manual, operador presente |
| `player-runtime` | `kiosk.py`, launchers do player, logica de start, flags de MPV, timing/sync/duracao/playlist | piloto assistido `channel=homologation`/`ring=pilot` via gate; thaw publico somente H2/stable futuro |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, wrapper, HDMI/display, kernel, DTB, U-Boot, BSP | nova imagem + homologacao |
| `field-data` | config real, seed, midia, cache, playlist, estado local | fluxo operacional em `/data`; nao e release de software |

## O Que Pode Atualizar Agora

OTA C18 comum pode atualizar somente `totem-core`.

Condicoes minimas:

- comando explicito com `--component totem-core`;
- policy presente em `/data/updates/policy.json`;
- `device_track="c18-hwdecode"`;
- `allowed_components=["totem-core"]`;
- `allow_downgrade=false`;
- canal exato (`lab`, `homologation` ou `stable`), sem heranca entre canais;
- dry-run aprovado antes do apply real;
- rollback definido antes do apply;
- evidencia sanitizada, sem segredo, URL real, SSID, IP, MAC, DNS ou config
  privada.

## O Que Esta Congelado

Ficam congelados fora do OTA comum:

- `kiosky-player`;
- `player-runtime`;
- `kiosk.py`;
- `kiosky_service_launcher.sh`;
- `totem-kiosky-launcher.sh`;
- MPV, ffmpeg, libplacebo, hwdecode e wrapper de MPV;
- units/timers systemd, updater, policy de fabrica, kernel, DTB, U-Boot, BSP;
- qualquer mudanca que precise de reboot para ser verdadeira.

Tentativas publicas de apply/rollback de `kiosky-player` ou `player-runtime`
devem continuar falhando com `rc=44` enquanto nao houver thaw explicito.

## Quem Autoriza

O device autoriza tecnicamente pelo conjunto:

- manifest da release;
- policy local do device;
- canal do device;
- lista `allowed_components`;
- features exigidas pelo updater;
- gate offline de release;
- dry-run que seleciona exatamente a release esperada.

O humano autoriza operacionalmente a janela de update. Sem decisao humana
explicita, nao gerar imagem de producao, nao publicar stable, nao ligar
auto-pull, nao regravar cartao, nao fazer poweroff/reboot operacional e nao
descongelar `player-runtime`.

Para stable, a autorizacao humana precisa vir junto de evidencia JSON aprovada
`dadooh.c18.stable_promotion.v1` e do bypass controlado
`ALLOW_C18_STABLE_PROMOTION=1`. Para `player-runtime`, tambem precisa da
decisao formal `dadooh.c18.player_runtime.thaw_decision.v1`, validada por
`scripts/qa/c18_player_runtime_thaw_decision_gate.py`, alem de H2 readiness.
Isso nao substitui homologacao fisica.

## Health, Deep-Health E Soak

`service health` e o minimo operacional:

- `kiosky-player.service` ativo;
- `NRestarts_delta=0`;
- processo MPV esperado vivo;
- apply nao reiniciou/parou o player.

Isso prova que o servico esta de pe, mas nao prova playback nem decode.

`deep-health` prova playback curto e decode:

- MPV real pela stack C18 (`/opt/totem/hwdecode/bin/mpv` ou wrapper);
- `hwdec-current=v4l2request-copy`;
- `vo-configured=true`;
- progresso de frame observado, nao apenas `time_pos`;
- transicoes/aliases observados quando houver playlist suficiente;
- `media_load_failed=0`;
- `mpv_restart=0`;
- `ipc_timeout=0`;
- `panfrost_faults=0`;
- `mmc_timeout_reset=0`.

O coletor preferencial e
`scripts/board/c18_playback_health_collect.py`, gerando artefatos publicos
sanitizados e `dadooh.c18.playback.deep_health.v1`.

Na linha C18 atual, progresso de frame estimado e evidencia obrigatoria para
aprovar playback de video. Se uma classe futura de midia legitima nao expuser
`estimated-frame-number`, ela deve ganhar health contract proprio; nao voltar ao
criterio inseguro de aprovar apenas por `time_pos`.
Em playlists com multiplos itens, cada segmento avaliavel precisa demonstrar
progresso de frame; um ultimo item saudavel nao pode mascarar stall em item
anterior.

`soak` e endurance, nao smoke test. Para producao/batch, o soak esperado e uma
janela longa, tipicamente 24h, com a mesma config candidata, aprovando:

- restarts zero;
- panfrost/mmc/I-O/ext4 sem erros;
- `media_load_failed=0`;
- `hard_resync=0`;
- temperatura sem throttle;
- RSS estavel;
- CPU com p95/pico registrado;
- volume de log aceitavel.

## Status Atual

Baseline de laboratorio/delivery registrado em 2026-06-08:

- imagem golden: `c18-hwdecode-lab-1u`;
- sha256:
  `57cd3e1620820c14ff9b297850386d7d95a1979b2f06201ff082526b8ffd13dd`;
- estado: `final_image=false`, nao stable, nao batch de producao;
- OTA manual de `totem-core` validado com apply, rollback e reapply;
- release de referencia aplicada:
  `c18.ota-core-config-missing-20260603T150429Z-2a7a327`;
- timer de update desligado;
- auto-pull fora de escopo;
- `kiosky-player` e `player-runtime` ainda congelados no fluxo publico;
- player esperado pelo fallback da imagem, com HW decode
  `v4l2request-copy`, `vo-configured=true`, `NRestarts=0`;
- deep-health real em hardware validado apos config real e apos cold-boot
  controlado:
  progresso de frame presente/avancando, `media_load_failed=0`,
  `mpv_restart=0`, panfrost/mmc/ext4 `0`.
- evidencia auditavel da 1u:
  `docs/evidence/c18-update-validation/20260608T035330Z-1u-coldboot-deep-health/`.
- a `1u` valida tambem `RequiresMountsFor=/data`, `After=local-fs.target`,
  reconcile de boot explicitamente autorizado e nao fatal, boot-state com
  discriminadores pre/post, timer off, policy restrita a `totem-core`,
  ausencia de `/data/player-runtime/current` e `player-runtime` publico
  congelado com `rc=44` em apply, rollback e reconcile; alem disso prova em
  hardware `reconcile --component kiosky-player` publico com `rc=44`.
- ensaio lab-only de `player-runtime` em hardware validado com pacote local
  `homologation` do commit `3af11d4`, `data_root` temporario em `/tmp`,
  candidato isolado com canario local, `github_used=false`,
  `network_required=false`, apply `rc=0`, rollback `rc=0`, reconcile `rc=0`,
  CLI publico ainda congelado com `rc=44`, e deep-health do servico real
  aprovado apos restart. Esse marco foi registrado como resumo operacional da
  sessao; antes de qualquer ensaio persistente em `/data`, a evidencia deve ser
  preservada em artefatos sanitizados e auditaveis, nao apenas em prosa.
- primeiro ensaio lab-only persistente de `player-runtime` em `/data` validado
  na `1r` com pacote local `homologation`
  `c18.player-runtime-lab-20260605T052721Z-1562cd3`;
- evidencia auditavel do trial persistente:
  `docs/evidence/c18-update-validation/20260605T052805Z-1r-player-runtime-data-trial/`;
- esse trial provou apply local em `/data/player-runtime`, marker verificado,
  adocao real do servico por `/data`, deep-health pos-restart, rollback com
  quarentena do candidato testado e retorno ao fallback de imagem com
  deep-health aprovado; o CLI publico continuou congelado com `rc=44`.
- nao provou thaw publico, GitHub publish, auto-pull, stable/producao,
  cold-boot, power-loss nem rollback A->B entre duas releases persistentes em
  `/data`; o manifest de evidencia deste primeiro trial tambem nao registra
  `image_tag`/`image_sha256`, entao a vinculacao com a `1r` fica registrada
  nos docs e no contexto operacional, nao dentro do manifest do trial.
- ensaio lab-only A->B->A de `player-runtime` em `/data` validado na `1r` com
  pacotes locais `homologation`
  `c18.player-runtime-ab-a-20260605T055913Z-8edcd1c` e
  `c18.player-runtime-ab-b-20260605T055913Z-8edcd1c`;
- evidencia auditavel do trial A->B->A:
  `docs/evidence/c18-update-validation/20260605T060200Z-1r-player-runtime-data-aba-trial/`;
- esse trial provou A ja ativa e verificada em `/data`, apply local de B,
  adocao real de B pelo servico, deep-health de B, rollback lab-only com
  quarentena de B e retorno para A como `previous` real em `/data`, com
  deep-health aprovado apos rollback; o CLI publico continuou congelado com
  `rc=44` em apply, rollback e reconcile.
- nao provou thaw publico, GitHub publish, auto-pull, stable/producao,
  cold-boot, power-loss, soak nem comportamento sob corte de energia; ao fim da
  validacao, a placa foi limpa por rollback lab-only adicional para
  `image_fallback`, e o launcher voltou a selecionar `/opt`.
- ensaio M-6 lab-only de `player-runtime` em `/data` com cold-boot real
  validado na golden `1t` com pacotes locais `homologation`
  `c18.player-runtime-m6-a-20260605T183103Z-m6-695298f-retry2` e
  `c18.player-runtime-m6-b-20260605T183103Z-m6-695298f-retry2`;
- evidencia auditavel do M-6:
  `docs/evidence/c18-update-validation/20260605T183103Z-1t-player-runtime-m6-data-coldboot-trial/`;
- esse trial provou apply A->B em `/data`, B adotado pelo launcher apos reboot
  real, deep-health de B pos-cold-boot, rollback de B para A como previous real
  em `/data` e deep-health pos-rollback; ele passou no release gate host
  existente na captura, mas nao deve ser usado como `decisive` contra o gate
  atual porque o pacote antecede a feature obrigatoria
  `c18-player-runtime-verify-then-promote-v1`; o CLI publico continuou
  congelado com `rc=44`;
- nao provou thaw publico, GitHub publish, auto-pull, stable/producao,
  power-loss fisico nem soak/endurance.
- ensaio M-6 decisivo lab-only de `player-runtime` em `/data` validado na
  golden `1t` com pacotes locais `homologation`
  `c18.player-runtime-m6-a-20260608T011301Z-m6-ac59f7f-retry1` e
  `c18.player-runtime-m6-b-20260608T011301Z-m6-ac59f7f-retry1`;
- evidencia auditavel decisiva:
  `docs/evidence/c18-update-validation/20260608T011301Z-1t-player-runtime-m6-data-coldboot-trial/`;
- esse trial provou apply A->B em `/data`, B adotado pelo launcher apos reboot
  controlado, deep-health de B pos-cold-boot, rollback de B para A como previous
  real em `/data` e deep-health pos-rollback; o release gate aceitou essa
  evidencia em modo `decisive` na rodada em que a golden era `1t`. Apos o bump
  para `1u`, essa evidencia fica image-pinned a `1t` e nao e autorizacao
  `decisive` atual; o CLI publico continuou congelado com `rc=44`;
- nao provou thaw publico, GitHub publish, auto-pull, stable/producao,
  power-loss fisico nem soak/endurance.
- imagem `c18-hwdecode-lab-1u` foi derivada offline com evidencia em
  `docs/evidence/c18-update-validation/20260608T024500Z-1u-offline-build/`;
  sha256
  `57cd3e1620820c14ff9b297850386d7d95a1979b2f06201ff082526b8ffd13dd`;
  depois foi validada em HW e substitui a golden `1t` para laboratorio/delivery;
  ainda nao prova power-loss fisico, soak, thaw publico, stable ou producao.
- bundle M-6 decisivo lab-only atual de `player-runtime` em `/data` validado
  na imagem `c18-hwdecode-lab-1x`, com pacotes locais `homologation`
  `c18.player-runtime-m6-a2-20260610T072826Z-29ff33b` e
  `c18.player-runtime-m6-b2-20260610T072826Z-29ff33b`;
- evidencias auditaveis decisivas atuais:
  `docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-coldboot/`,
  `docs/evidence/c18-update-validation/20260610T072826Z-1x-m6-data/` e os
  teardown dirs `20260610T052324Z-1x-teardown`,
  `20260610T185956Z-1x-teardown-fresh-ipc-probe` e
  `20260611T050939Z-1x-production-stop`;
- esse bundle provou A2->B2->cold-boot->A2 em `/data`, com B2 adotado de
  `/data/player-runtime/current`, deep-health, teardown/relaunch repetido,
  req#4 fresh-IPC exercitado, parada SIGTERM saudavel do Python-kiosk via IPC
  quit, rollback para A2 real em `/data` e release gate host em modo
  `decisive` pinado a `c18-hwdecode-lab-1x`;
- essa evidencia restaura a autorizacao decisiva lab de `player-runtime`, mas
  nao promove a `1x` como golden baseline/fallback geral. A fonte canonica de
  recovery/delivery continua sendo `current-golden.json` (`1u`) enquanto nao
  houver promocao propria de baseline/fallback da `1x`;
- nao provou thaw publico, OTA de `kiosky-player`, GitHub publish, auto-pull,
  stable/producao, power-loss fisico nem soak/endurance.

## Gates Antes De Thaw Do Player-Runtime

Antes de piloto homologation assistido:

- `scripts/qa/c18_player_runtime_pilot_readiness_gate.py` precisa passar sobre
  o pacote real e a evidencia commitada;
- a autorizacao formal precisa declarar `ring=pilot`, `channel=homologation`,
  operador, janela, rollback owner e devices allowlisted por hash/sanitizados;
- o preflight da placa precisa provar policy `homologation`,
  `allow_prerelease=true`, timer off, public freeze `rc=44` e marcador/imagem
  esperados;
- o gate precisa carregar non-claims explicitos: sem producao, sem `stable`,
  sem auto-pull, sem soak 24h, sem power-loss 17/17, sem assinatura/attestation
  como requisito do piloto e sem thaw publico;
- o P0 seletivo aceito para piloto e: `after_current_symlink`,
  `rollback_after_current_to_previous`, `rollback_after_previous_removed`,
  `rollback_after_quarantine` e `rollback_after_state_success`;
- o resto da matriz power-loss permanece H2/producao.

Antes de qualquer thaw de laboratorio:

- `scripts/qa/c18_player_runtime_release_gate.py` precisa passar no pacote real;
- pacote nao pode ser `stable`;
- payload nao pode tocar config, seed, arquivos de imagem/controle, paths
  absolutos, symlinks, hardlinks, traversal ou arquivos com cara de segredo;
- `kiosk.py` precisa compilar e preservar wrapper/HW decode no caminho efetivo
  ate `subprocess.Popen(args, ...)`;
- apply lab-only unitario deve usar
  `scripts/qa/c18_player_runtime_lab_apply.py` com flags e env vars lab-only;
- rollback/reconcile lab-only deve usar
  `scripts/qa/c18_player_runtime_lab_rollback.py` com flags e env vars
  lab-only (`C18_PLAYER_RUNTIME_LAB_ROLLBACK=1` + `--lab-only-rollback`) antes
  de qualquer ensaio persistente em `/data`;
- thaw de laboratorio decisivo deve usar
  `scripts/qa/c18_player_runtime_lab_thaw.py`, que orquestra o fluxo M6
  duas-fases (`arm` -> reboot real -> `resume`), le a golden atual de
  `docs/evidence/c18-update-validation/current-golden.json`, exige
  `C18_PLAYER_RUNTIME_LAB_THAW=1` + `--lab-only-thaw`, aceita apenas
  `lab|homologation`, rejeita `source_dirty=true` e so autoriza a rodada se o
  release gate rodar em modo `decisive`;
- durante o `arm`, o harness M6 deve manter `kiosky-player.service` parado e
  mascarado apenas em runtime enquanto cada apply lab executa health do
  candidato, para evitar que `Restart=always`/`ExecStartPre reconcile` readote
  fallback e limpe a release ainda em verificacao;
- `reconcile --component player-runtime` de manutencao deve exigir
  `--allow-player-runtime-maintenance` e `C18_PLAYER_RUNTIME_RECONCILE=1`; o
  boot da imagem pode passar essa autorizacao explicitamente, mas o comando nao
  deve ficar solto como API publica mutavel;
- o proximo ensaio persistente deve ser orquestrado por
  `scripts/qa/c18_player_runtime_persistent_trial.py`, mantendo o CLI publico
  congelado, e deve guardar `evidence-manifest.json`, manifest do pacote,
  payload SHA, hashes dos artefatos, `playback-samples.tsv`, sidecars
  `deep-health-*.json`, `candidate-health-result.json`,
  `launcher-adoption.json` e `playback-deep-health-public.json` sanitizados;
- a evidencia precisa provar semanticamente apply, marker verificado, adocao
  real de `/data/player-runtime/current` pelo launcher, deep-health do servico
  apos restart, rollback real, links `current`/`previous` antes/depois e
  fallback/previous esperado apos rollback; para trial persistente, o rollback
  deve usar quarentena do `current` testado para impedir readocao automatica do
  candidato revertido;
- o trial persistente deve ter caminho de aborto explicito: se for
  interrompido depois do stop do servico ou depois de promover um candidato em
  `/data`, o harness precisa comparar o `current` pre/post, executar rollback
  lab-only com `--quarantine-current` quando houver `current` novo, reiniciar
  `kiosky-player.service` e escrever `abort-cleanup.json`; boot reconcile nao
  substitui essa limpeza, pois um candidato valido e marcado pode ser adotado
  corretamente pelo launcher;
- antes de commitar essa evidencia, rodar
  `scripts/qa/c18_player_runtime_evidence_gate.py --run-dir <dir>` para aplicar
  allowlist de arquivos, scan de vazamento, hashes e validacao semantica dos
  artefatos;
- health de candidato deve usar runner lab-only isolado, sem GitHub, sem timer,
  sem auto-pull e sem policy permanente; se o harness for iniciado como root,
  o candidato deve rodar como usuario nao-root (`totem` por padrao), nunca como
  root;
- quando nao houver API real no runner, o health de candidato deve usar canario
  offline explicito (`--canary-media`) sob `/tmp` ou `/data/media`, com playlist
  temporaria isolada e sem publicar o path em evidencia publica;
- em Orange Pi/DRM, validacao de candidato pode exigir janela controlada com o
  player vivo parado para liberar DRM master; isso e validacao de laboratorio,
  com restart do servico ao final, nao thaw publico nem auto-pull;
- launcher deve adotar `/data/player-runtime/current` somente com marker
  `.release_verified.json` valido, hashes conferidos, deep-health aprovado e
  identidade nao quarentenada;
- falha, marker ausente/corrompido ou hash divergente deve cair para
  `/opt/totem/kiosky-player`.

Passar esses gates ainda nao libera producao; apenas permite teste controlado
de laboratorio.

O gate de laboratorio A->B com release persistente anterior verificada foi
satisfeito pela evidencia `20260605T060200Z-1r-player-runtime-data-aba-trial`.
Qualquer repeticao desse ensaio deve usar `--rollback-expectation
data-previous` e preencher `--image-tag`, `--image-sha256` e, quando
disponivel, `--image-marker-file`; o evidence gate deve falhar se o rollback
cair em `image_fallback`, se faltar `service-before-apply`, ou se os
`tree_sha256` de A e B forem indistinguiveis.

A evidencia historica
`20260605T183103Z-1t-player-runtime-m6-data-coldboot-trial` provou a mecanica
M6: apply A->B, reboot real, B adotada de `/data`, deep-health, rollback para A
por previous em `/data` e deep-health pos-rollback. Depois dela, o contrato de
pacote foi endurecido para exigir `requires.updater_features` com
`c18-player-runtime-verify-then-promote-v1`; portanto essa evidencia antiga nao
deve ser usada como `decisive` contra o gate atual.

A evidencia `20260608T011301Z`
`20260608T011301Z-1t-player-runtime-m6-data-coldboot-trial` repetiu esse fluxo
pelo wrapper `c18_player_runtime_lab_thaw.py`, com pacote contendo
`c18-player-runtime-verify-then-promote-v1`, repo limpo e release gate em modo
`decisive` quando a golden era `1t`. Com a golden atual `1u`, ela permanece
como marco historico de laboratorio para adocao `player-runtime` em `/data`,
mas nao como autorizacao `decisive` corrente. A autorizacao decisiva lab
corrente foi restaurada pelo bundle `1x`
`20260610T072826Z-1x-m6-coldboot` + `20260610T072826Z-1x-m6-data` + teardown
dirs `1x`, pinado a `c18-hwdecode-lab-1x`, sem promover a `1x` como golden
baseline/fallback geral.
Os gates que ainda ficam para homologacao/producao sao
interrupcao/power-loss fisico, soak/endurance, publish/server-side governado e
decisao explicita de promocao sem `stable` nem auto-pull.

Antes de thaw publico, stable ou producao de `player-runtime`:

- `scripts/qa/c18_player_runtime_h2_readiness_gate.py` precisa passar;
- `scripts/qa/c18_stable_promotion_gate.py` precisa validar a promocao stable;
- `scripts/qa/c18_player_runtime_thaw_decision_gate.py` precisa validar a
  decisao formal de thaw, com janela UTC ativa de no maximo 4h;
- `scripts/qa/c18_player_runtime_stable_decision_draft_build.py` pode gerar
  rascunhos fail-closed dos JSONs finais, hash-bound aos artefatos reais, mas
  esses rascunhos nao aprovam stable nem thaw ate serem preenchidos por operador
  depois de H2 verde; `passed=true` nesse builder significa apenas que os
  rascunhos foram escritos e continuam reprovando nos gates como esperado;
- `scripts/qa/c18_server_side_publish_governance_gate.py` precisa validar a
  familia server-side/signature e trust anchor;
- `scripts/qa/c18_server_side_publish_asset_collect.py` pode materializar a
  lista repo-relative de assets server-side e hashes, sem publicar release;
- a matriz fisica power-loss precisa estar 17/17;
- o planner
  `docs/evidence/c18-update-validation/20260617T020912Z-h2-powerloss-matrix-plan-custom-setup-c16fb3e/`
  registra 5/17 cobertos e 12/17 pendentes, com instrucoes manuais explicitas
  para checkpoints `requires_custom_setup`;
- o runbook
  `docs/evidence/c18-update-validation/20260617T081018Z-h2-powerloss-operator-runbook-payload-image-bind-c16fb3e/`
  pode orientar os 12 checkpoints pendentes, bloqueia setup customizado sem
  comandos/instrucoes, recusa placeholder `<utc>`/diretorio local existente no
  helper de pull, materializa o manifest local exigido pelo evidence gate, fixa o
  marker de imagem esperado no preflight, injeta binding de payload/imagem no
  manifest local e nao conta como evidencia fisica;
- antes de iniciar uma sessao fisica, rodar
  `scripts/board/c18_player_runtime_h2_powerloss_preflight_collect.py` na placa
  e validar o JSON com
  `scripts/qa/c18_player_runtime_h2_powerloss_preflight_gate.py` contra o plano
  da matriz; esse preflight confirma pacote/imagem/topologia de sessao e
  continua sem reivindicar power-loss, 17/17, stable, producao ou thaw;
- em `20260612T163008Z`, esse preflight encontrou o target `c16fb3e` ainda
  quarentenado; o reset lab-only em
  `docs/evidence/c18-update-validation/20260612T163437Z-h2-powerloss-quarantine-reset-c16fb3e/`
  removeu uma entrada do target sem mudar links e com CLI publico ainda
  congelado; o preflight pos-reset em
  `docs/evidence/c18-update-validation/20260612T163650Z-h2-powerloss-board-preflight-after-reset-c16fb3e/`
  ficou verde para iniciar a sessao fisica;
- depois da nova retomada com placa acessivel, o preflight fresco em
  `docs/evidence/c18-update-validation/20260617T071517Z-h2-powerloss-board-preflight-fresh-c2c6c8d/`
  reconfirmou pacote `c16fb3e`, imagem `c18-hwdecode-lab-1x`, policy
  `homologation`, timer inativo/desabilitado, target nao linkado, target nao
  quarentenado, raiz H2 sem diretorios de checkpoint pendentes e custom setup
  reportado para `after_previous_symlink` e `rollback_after_current_unlinked`;
  continua sendo somente preflight e nao evidencia power-loss;
- o soak precisa ter no minimo 24h;
- a evidencia final precisa versionar stable evidence, thaw decision,
  `h2-readiness-final.json` e README com non-claims/hashes;
- nada disso publica release, liga auto-pull ou remove `rc=44` por si so.

A imagem `1t` ja embarca e valida em cold-boot do baseline/fallback:

- `RequiresMountsFor=/data` no drop-in do `kiosky-player.service`, para o
  reconcile de boot nao operar contra `/data` ausente;
- fsync estrito da arvore de release antes de marker/current de
  `player-runtime`;
- deep-health falhando fechado tambem para segmento final curto sem progresso
  comprovado;
- evidencias com non-claims explicitos para server-side gate, power-loss e soak.

Isso prova cold-boot lab com uma release de `player-runtime` em `/data`, mas
ainda nao prova corte de energia fisico no meio de apply/rollback nem soak.

Follow-up repo-side apos a promocao da `1t`:

- novas evidencias decisorias de cold-boot devem incluir
  `pre-state-public.json` (`dadooh.c18.coldboot_pre_state.v1`) antes do reboot e
  `boot-state-public.json` depois do reboot, coletados por
  `scripts/board/c18_coldboot_state_collect.py` e validados por
  `scripts/qa/c18_coldboot_evidence_gate.py --require-pre-state`;
- o post-state deve referenciar o pre-state por `sha256` e nonce. O gate pode
  exigir `--expect-transition-flow`, `--expect-mechanical-action` e
  `--forbid-controlled-reboot` quando a rodada quiser afirmar uma acao fisica,
  e nao apenas reboot controlado;
- esses arquivos devem trazer discriminadores de boot (`boot_id` hasheado,
  `btime`, uptime), identidade da imagem via marker em `/etc/dadooh`, estado de
  mount de `/` e `/data`, contrato systemd (`RequiresMountsFor=/data`,
  `After=local-fs.target`, `ExecStartPre` de reconcile), fonte candidata do
  launcher (`fallback` ou `/data`) e flags de privacidade; nao devem persistir
  journal bruto, UUID/particao em claro, IP, MAC, SSID, URL ou segredo;
- manifestos de novas evidencias de trial devem registrar identidade de repo
  (`repo_commit`, `repo_tree`, `repo_dirty=false`, tag se houver) para reduzir
  drift entre checkout, imagem e placa; para `player-runtime`, o gate exige que
  `repo_commit` case com o `source_commit` do pacote e que o manifesto traga
  `image_tag`/`image_sha256`/marker `/etc/dadooh`; em rodadas decisivas, o gate
  tambem deve comparar esses campos com a golden esperada via `--expect-image-*`;
- evidencias cold-boot que selecionam ou demonstram `/data` nao podem usar o
  caminho fraco: o gate deriva `/data` de `selected_source`, do adoption probe
  ou de marker verificado, e falha fechado sem `--require-pre-state` e sem uma
  identidade de imagem esperada (`--expect-image-tag` ou
  `--expect-image-marker-sha256`);
- a golden atual e sua evidencia ficam em uma unica fonte canonica,
  `docs/evidence/c18-update-validation/current-golden.json`; novos bumps de
  golden devem atualizar essa fonte e deixar os gates compararem contra ela;
- o release gate possui modo explicito de evidencia: `baseline` (default,
  apenas baseline/fallback historico) e `decisive` (M-6). Em `decisive`,
  `--player-runtime-data-coldboot-evidence-dir` e
  `--player-runtime-data-evidence-dir` sao obrigatorios, os gates rodam com
  `/data`, pre-state e imagem golden pinada, e o release gate cruza
  version/tree/kiosk do marker entre a evidencia warm e a cold-boot;
- em placa minima sem `git`, a fase `resume` do wrapper pode usar
  `--defer-release-gate`: isso permite concluir os checks M6 no board, mas
  continua `final_authorization=false` ate a evidencia ser copiada e o
  `c18_ota_release_gate.py --player-runtime-evidence-mode decisive` passar no
  host em arvore limpa;
- quando a evidencia reivindicar `/data` como fonte adotada pelo servico, ela
  tambem precisa incluir `launcher-adoption.json` do probe de adocao real,
  provando processo em execucao, marker valido e hash do `kiosk.py` rodando
  batendo com o marker;
- os subdiretorios de deep-health do M6 devem ser escritos primeiro em um
  diretorio temporario local ao evidence-root e promovidos por rename somente
  depois de o coletor terminar e a arvore estabilizar. O diretorio final pode
  conter apenas metadado preexistente do probe (`launcher-adoption.json`); se
  qualquer artefato de health ja existir, a rodada deve falhar fechado. Isso
  evita assinar manifestos sobre amostras ainda em escrita ou sobre uma rodada
  concorrente/reusada;
- o harness M6 deve usar lock exclusivo de processo para impedir duas fases
  `arm`/`resume`/`rollback-only` concorrentes na mesma placa. Concorrencia deve
  virar `m6_lock_busy`, nao dois coletores escrevendo no mesmo evidence-root;
- o updater tem fault-injection offline no caminho real de apply/rollback de
  `player-runtime`; isso prova fronteiras de crash em codigo real, mas ainda
  nao e prova fisica de corte de energia;
- reconcile de `player-runtime` deve falhar fechado para `/opt` se `state.json`
  estiver corrompido e deve limpar releases invalidas/orfas quando nao forem
  `current`/`previous` verificados.

## Gates Antes De Stable

Antes de qualquer stable ou batch:

- promocao explicita `lab -> homologation -> stable`;
- homologacao fisica na placa-alvo;
- policy stable com `allow_prerelease=false`;
- evidencia `dadooh.c18.stable_promotion.v1` aprovada;
- para `player-runtime`, evidencia
  `dadooh.c18.player_runtime.thaw_decision.v1` aprovada;
- H2 readiness verde, incluindo server-side/signature, trust anchor,
  power-loss 17/17, soak 24h e decisao formal de thaw;
- rollback testado e documentado;
- deep-health aprovado apos update;
- soak de endurance aprovado quando a mudanca tocar player/runtime/imagem;
- decisao humana explicita sobre imagem final;
- auditoria de privacidade das evidencias.

CI ampliado, bridge de updater, A/B de imagem e auto-pull sao hardening futuro.
Assinatura/attestation ja e requisito H2/server-side para producao, mas nao e
requisito do piloto manual imediato.
