# C18 - Autorizacao De Update E Health Gates

Nota operacional curta para dev/IA retomar a linha C18 sem abrir caminho
acidental para update inseguro. Em caso de divergencia, o contrato vigente esta
em `docs/UPDATE_CONTRACT.md`; o baseline live fica em
`docs/product/189_C18_OTA_READINESS_GATE.md`.

## Modelo De Classes

| Classe | Inclui | Caminho de update |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, validadores, helpers de Wi-Fi/config, settings | OTA C18 manual, operador presente |
| `player-runtime` | `kiosk.py`, launchers do player, logica de start, flags de MPV, timing/sync/duracao/playlist | congelado no fluxo publico; so imagem ou thaw lab explicito |
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
`ALLOW_C18_STABLE_PROMOTION=1`. Isso nao substitui homologacao fisica.

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

Baseline de laboratorio/delivery registrado em 2026-06-05:

- imagem golden: `c18-hwdecode-lab-1t`;
- sha256:
  `7ab5a582f2ce51f13338be8ad4a68a15cb736007f617a49456704c5c45cefec6`;
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
- evidencia auditavel da 1t:
  `docs/evidence/c18-update-validation/20260605T093008Z-1t-coldboot-deep-health/`.
- a `1t` valida tambem `RequiresMountsFor=/data`, `After=local-fs.target`,
  reconcile de boot explicitamente autorizado e nao fatal, boot-state com
  discriminadores pre/post, timer off, policy restrita a `totem-core`,
  ausencia de `/data/player-runtime/current` e `player-runtime` publico
  congelado com `rc=44` em apply, rollback e reconcile.
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

## Gates Antes De Thaw Do Player-Runtime

Antes de qualquer thaw de laboratorio:

- `scripts/qa/c18_player_runtime_release_gate.py` precisa passar no pacote real;
- pacote nao pode ser `stable`;
- payload nao pode tocar config, seed, arquivos de imagem/controle, paths
  absolutos, symlinks, hardlinks, traversal ou arquivos com cara de segredo;
- `kiosk.py` precisa compilar e preservar wrapper/HW decode no caminho efetivo
  ate `subprocess.Popen(args, ...)`;
- apply lab-only deve usar
  `scripts/qa/c18_player_runtime_lab_apply.py` com flags e env vars lab-only;
- rollback/reconcile lab-only deve usar
  `scripts/qa/c18_player_runtime_lab_rollback.py` com flags e env vars
  lab-only (`C18_PLAYER_RUNTIME_LAB_ROLLBACK=1` + `--lab-only-rollback`) antes
  de qualquer ensaio persistente em `/data`;
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

Os proximos gates de laboratorio antes de qualquer thaw publico sao cold-boot
adoption com `/data/player-runtime/current` real, comportamento sob
interrupcao/power-loss durante apply/rollback e decisao explicita de como o
fluxo sera promovido para homologacao sem publicar stable nem ligar auto-pull.

A imagem `1t` ja embarca e valida em cold-boot do baseline/fallback:

- `RequiresMountsFor=/data` no drop-in do `kiosky-player.service`, para o
  reconcile de boot nao operar contra `/data` ausente;
- fsync estrito da arvore de release antes de marker/current de
  `player-runtime`;
- deep-health falhando fechado tambem para segmento final curto sem progresso
  comprovado;
- evidencias com non-claims explicitos para server-side gate, power-loss e soak.

Isso ainda nao prova cold-boot com uma release de `player-runtime` em `/data`
nem corte de energia no meio de apply/rollback.

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
  drift entre checkout, imagem e placa;
- quando a evidencia reivindicar `/data` como fonte adotada pelo servico, ela
  tambem precisa incluir `launcher-adoption.json` do probe de adocao real,
  provando processo em execucao, marker valido e hash do `kiosk.py` rodando
  batendo com o marker;
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
- rollback testado e documentado;
- deep-health aprovado apos update;
- soak de endurance aprovado quando a mudanca tocar player/runtime/imagem;
- decisao humana explicita sobre imagem final;
- auditoria de privacidade das evidencias.

CI, assinatura/attestation, bridge de updater, A/B de imagem e auto-pull sao
hardening futuro. Nao assumir que existem na linha C18 atual.
