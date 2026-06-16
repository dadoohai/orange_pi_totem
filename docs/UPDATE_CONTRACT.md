# C18 Update Contract

Este e o contrato vigente para atualizacoes da linha C18. Documentos C14/C15/C17
sao historicos quando divergirem daqui.

Estado live/baseline validado deve ser consultado em
`docs/product/189_C18_OTA_READINESS_GATE.md`. Este contrato define regras; o 189
registra qual imagem/release esta em laboratório em cada rodada.

## Regra Principal

OTA C18 e manual/operator-triggered e restrito a `totem-core` operacional.
Mudancas em player, runtime de midia, sistema, updater, units ou imagem base
nao entram no OTA comum.

## Classes De Mudanca

| Classe | Exemplos | Caminho permitido | Rollback/fallback |
| --- | --- | --- | --- |
| `totem-core` operacional | wizard, splash, status, writer, Wi-Fi helper, config contract, settings session | OTA manual `totem-core` | `current`/`previous` em `/data/core/totem` e fallback em `/opt/totem/core-fallback/bin` |
| `player-runtime` | `kiosk.py`, `kiosky_service_launcher.sh`, logica de start do player, flags de MPV, timing/sync/duracao/playlist | nova imagem ou pacote C18-aware explicitamente homologado | imagem/cartao known-good; nao OTA comum |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, HDMI/display, kernel, DTB, U-Boot, BSP | nova imagem + homologacao | imagem/cartao known-good; sem A/B nesta linha |
| `field-data` | config real, seed, midia, playlist/cache, estado operacional | fluxo operacional em `/data`; nao release de software | writer/backup/re-sync conforme o dado |

`field-data` pode gerar fotografia publica/sanitizada de estado operacional,
mas isso nao torna config, midia, cache ou playlist parte de um release de
software. O snapshot governado atual e
`scripts/board/totem_appliance_status_snapshot.py`, com
`c18_governance.schema=dadooh.c18.appliance_public_state.governance.v1` e
`result_claim=read_only_appliance_public_state_collected`. Ele le somente
status publico, campos allowlisted do status do player e metadados da config
por `stat`; nao abre config real, nao copia status bruto, nao le midia/rede ou
journal, nao executa comandos e escreve apenas em `/tmp`. Ele e evidencia
operacional, nao payload OTA comum, nao release `player-runtime`, nao imagem,
nao H2/stable/producao e nao substitui power-loss, soak ou thaw.

O retrato macro de governanca C18 e validado por
`scripts/qa/c18_ota_macro_governance_gate.py`. Esse gate e apenas agregador
offline pre-H2: confere H1, pilot readiness, H2 bloqueado e diagnostico
read-only ja versionados. Ele nao substitui H2, nao reabre janela operacional
expirada, nao publica, nao promove `stable`, nao habilita auto-pull e nao thaw
`player-runtime`.

## Roots De Artefatos

| Classe | Root canonico | Observacao |
| --- | --- | --- |
| `totem-core` | `releases/core-updates` | Pacotes core C18 devem ser gerados de novo e passar `c18_ota_release_gate.py --package-manifest ... --package-payload ...`; artefatos C17/C14 antigos nesse root sao historicos se falharem o gate atual. |
| `player-runtime` | `releases/player-runtime` | Root do pacote C18-aware e da familia server-side do `player-runtime`; nao e OTA comum e continua atras dos gates de homologacao/H2. |
| `totem-core` | `releases/totem-core` | Nao e root canonico nesta linha; nao usar para C18. |
| `kiosky-player` legado | `releases/app-updates` | Historico C14/kiosky; nao usar como C18 OTA, `player-runtime`, `stable` ou producao. |
| `system-image` | `releases/image-lab-readonly`, `releases/installable-rc` | Artefatos de imagem/lab nao sao OTA comum; qualquer uso corrente precisa seguir a trilha de imagem/homologacao. |

## Contrato De Config C18

`field-data` nao pode escolher outro binario de MPV na linha C18. Esse campo
parece dado operacional, mas muda diretamente o runtime de midia e ja causou
regressao na 1h.

Para `device_track="c18-hwdecode"`:

- `mpv_path` deve estar ausente; ou
- `mpv_path` deve ser exatamente `/opt/totem/bin/totem-mpv-hwdecode`.

Qualquer outro valor, incluindo `mpv`, `/usr/bin/mpv`, caminho relativo ou
string vazia, deve ser rejeitado pelo contrato de config antes de gravar
`/data/config/config.json`.

O writer, o handoff privado, seeds de homologacao e exemplos usados em C18
devem passar pelo mesmo contrato. Mudancas em MPV, wrapper, flags de decode ou
stack `/opt/totem/hwdecode` continuam sendo `media-system` e exigem imagem.

## Fronteira Do Player

`kiosky-player` OTA esta congelado na C18. O congelamento tambem vale para
mudancas indiretas no runtime do player.

O snapshot governado do player C18 fica em
`player-runtime/kiosky-player/kiosk.py`, com provenance em
`player-runtime/kiosky-player/SOURCE.json`. Esse arquivo nasceu do `kiosk.py`
validado na imagem `c18-hwdecode-lab-1i` e segue validado na golden `1u`:
upstream `dadoohai/kiosky-player` em `c25659aff200d9aac1720e60e60794c432c79393`
mais o patch C18 de `DEFAULT_CONFIG.mpv_path` para
`/opt/totem/bin/totem-mpv-hwdecode`.

Esse snapshot e fonte governada para imagem/gate, nao pacote OTA. Mudancas nele,
no launcher/drop-in do player ou em outros arquivos fixos por imagem devem
bloquear o gate OTA comum de `totem-core` e exigir gate separado de
`player-runtime`, nova imagem ou homologacao.

Qualquer pacote futuro de `player-runtime` deve passar antes por
`scripts/qa/c18_player_runtime_release_gate.py`. Esse gate abre o payload,
confere o SHA do manifest e aplica allowlist exata: o payload governado de
`player-runtime` contem somente `kiosk.py`. Extras como cache, playlist, estado,
MPV/ffmpeg, modulos de kernel, helpers genericos, config, seed, marker
pre-forjado, arquivos de controle/imagem e arquivos com cara de segredo devem
falhar fechados. O gate tambem rejeita path traversal, symlink/hardlink e exige
`kiosk.py` compilavel preservando o wrapper e o HW decode C18 nos defaults, em
`build_mpv_args` e no caminho efetivo ate
`subprocess.Popen(args, ...)`. O gate rejeita argumentos MPV perigosos, inclusive
construcao dinamica simples, builder alternativo, mutacao de `args` depois do
builder e mutacao de `cfg["hwdec"]` fora do caminho controlado. Passar nesse
gate nao habilita apply: o componente continua congelado ate thaw explicito.

Uma release de `player-runtime` so pode ser adotada se o updater escrever, dentro
do diretorio da release, `.release_verified.json` com schema
`dadooh.c18.player_runtime.verified.v1`. O marker precisa amarrar `version`,
`payload_sha256`, `kiosk_py_sha256`, `tree_sha256` e um deep-health aprovado. O
launcher deve recomputar os hashes antes de adotar `/data/player-runtime/current`.
Marker ausente, corrompido, divergente ou identidade quarentenada fecha para
`/opt/totem/kiosky-player`.

No boot, a decisao de adocao e do launcher: ele e o reconcile fail-closed entre
`/data/player-runtime/current` e `/opt`. O subcomando `reconcile` do updater
serve para higiene de `state.json`/symlink drift e nao substitui essa decisao de
boot. Por poder mexer em symlink/state de `player-runtime`, ele nao e comando
publico livre: precisa de `--allow-player-runtime-maintenance` e
`C18_PLAYER_RUNTIME_RECONCILE=1`. A fonte da proxima imagem executa esse
reconcile como `ExecStartPre=-...` nao-fatal e explicitamente autorizado antes
do player, preservando o launcher como barreira primaria.

O sandbox `scripts/sim/run_player_runtime_sandbox.py` prova a mecanica offline
necessaria antes de descongelar usando as primitivas reais do updater:
verify-then-promote, apply A/B, `current`/`previous`, rollback roundtrip,
marker corrompido caindo para imagem, health que observa fallback rejeitado,
falha com rollback para previous, falha sem previous caindo para a imagem, e CLI
real ainda congelado (`rc=44`). Essa prova e de fluxo/estado com health hook
injetavel; ela nao prova decode real em hardware nem durabilidade sob corte de
energia. Esses continuam gates de homologacao. O slot governado de runtime e
`/data/player-runtime/current`; o launcher C18 deve procurar esse caminho antes
do fallback de imagem e nao deve sombrear o player validado pelo caminho legado
`/data/apps/kiosky-player/current`.

`kiosky_service_launcher.sh` e arquivo de `player-runtime`: a imagem deve
fornece-lo como arquivo fixo em `/opt/totem/bin`, e releases OTA de
`totem-core` nao devem inclui-lo em `bin/`.

Uma release `totem-core` que precisa alterar como o player sobe deve ser tratada
como frente de `player-runtime`, com imagem/homologacao ou pacote C18-aware
proprio. Nao publicar como core comum.

## Contrato De Manifest

Toda release C18 de `totem-core` deve usar `dadooh.totem.update.v1` e declarar:

- `component="totem-core"`;
- `channel` correto (`lab`, `homologation` ou `stable`);
- `created_at_utc` ISO-8601 com timezone UTC;
- `payload_sha256`;
- `requires.device="orangepizero3"`;
- `requires.base_image_min="c17.4.2"` para esta linha;
- `requires.device_track="c18-hwdecode"`;
- `requires.updater_features` contendo:
  - `c18-freeze-kiosky-player-v1`;
  - `c18-rollback-reapply-v1`;
  - `c18-safe-payload-v1`;
  - `c18-track-v1`.

Updater C18 deve rejeitar manifest sem esses campos, com track errado, feature
desconhecida, feature ausente, canal incompatível, policy ausente/invalida ou
payload inseguro.

O payload C18 de `totem-core` tambem e allowlist exata no gate e no device-side:
diretorios raiz, `bin`, `health` e `manifest-fragment`; arquivos
`bin/<TOTEM_CORE_REQUIRED_BIN>`, `health/totem-core-health.json` e
`manifest-fragment/totem-core.json`. O `totem_updatectl.py` valida essa allowlist
antes de extrair/promover o release. Portanto um pacote com SHA correto mas com
launcher de player, arquivos de midia/dados, `/opt`, systemd, extras de health ou
extras de manifest deve falhar fechado no proprio device, alem de falhar no
release gate.

## Policy Do Device

Policy C18 deve existir em `/data/updates/policy.json` e restringir:

```json
{
  "schema": "dadooh.totem.update.policy.v1",
  "device_track": "c18-hwdecode",
  "allowed_components": ["totem-core"],
  "allow_downgrade": false
}
```

`device_channel` e `allow_prerelease` variam por ambiente. Policy sem
`allowed_components` valido deve falhar fechada, nao assumir componente por
default.

## Sistema De Autorizacao De Update

A autorizacao C18 tem duas camadas:

- **device/gate:** manifest valido, policy local, canal exato,
  `allowed_components`, `device_track`, `updater_features`, SHA do payload,
  gate offline e dry-run selecionando a release esperada;
- **operacao humana:** decisao explicita de janela, componente, canal e
  rollback antes de qualquer apply real, regravacao, publish stable, auto-pull
  ou thaw de `player-runtime`.

Lab-only flags, bypasses historicos e harnesses de bancada nao sao autorizacao
de campo. `kiosky-player` e `player-runtime` devem seguir retornando `rc=44` em
apply/rollback publicos ate thaw explicito. Auto-pull permanece desligado nesta
linha.

Guia operacional curto: `docs/UPDATE_AUTHORIZATION_HEALTH.md`.

## Gates Minimos

Antes de publicar ou promover OTA C18:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json
```

Para pacote especifico:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py \
  --package-manifest <release-dir>/dadooh-totem-core-<version>.manifest.json \
  --package-payload <release-dir>/dadooh-totem-core-<version>.tar.gz \
  --json
```

Em PR/branch ou antes de publish, usar tambem `--base-ref <ref>` (ou
`C18_OTA_BASE_REF=<ref>`) para que o guard compare o conjunto commitado contra
a base, nao apenas o worktree local. O publisher de `totem-core` deve falhar
fechado se a base nao for declarada e deve publicar o JSON de evidencia do gate
junto ao manifest/payload.

O gate deve provar, no minimo:

- `totem-core` sem `bin/kiosky_service_launcher.sh` no payload;
- `totem-core` sem `bin/totem-kiosky-launcher.sh` no payload;
- manifest com contrato C18 completo;
- payload com SHA correto, allowlist estrita de conteudo `totem-core`, e sem
  path traversal, symlink, hardlink, segredo, config real ou field-data;
- device-side `totem_updatectl.py` recusando pacote `totem-core` fora da mesma
  allowlist antes de trocar `current`/`previous`;
- release GitHub publicada a partir do `source_commit` declarado no manifest,
  nunca do default branch implicito do `gh`;
- policy/service/timer C18 coerentes;
- freeze de `kiosky-player` preservado;
- scripts historicos de release de `kiosky-player` falhando por padrao; qualquer
  bypass legado exige flag explicito, continua boundary-scanned e nao aprova
  release/thaw `player-runtime` C18-aware;
- diff OTA comum sem arquivos de frentes fora de `totem-core` operacional
  (`player-runtime`, `system-image`, `media-system` ou `field-data`);
- sandbox apply/rollback de `totem-core` passando.

## Deep-Health De Playback

O health-check de `systemd active + NRestarts` nao prova playback nem decode.
Qualquer pacote C18-aware de `player-runtime` deve ter um deep-health antes de
persistir como sucesso. O resumo deve ser sanitizado e conter somente
contadores/estados, nunca URLs de midia, SSID, IP, MAC, DNS, config real ou
tokens.

Contrato minimo para uma janela curta:

- `kiosky-player.service` ativo;
- `NRestarts_delta=0`;
- um unico MPV real observado;
- MPV executando a stack C18 (`/opt/totem/hwdecode/bin/mpv` ou wrapper
  `/opt/totem/bin/totem-mpv-hwdecode`);
- `hwdec-current=v4l2request-copy`;
- `vo-configured=true`;
- `estimated-frame-number` presente e avancando; `time-pos` sozinho nao aprova
  playback C18;
- pelo menos duas transicoes ou dois aliases de midia observados quando houver
  playlist suficiente;
- `media_load_failed=0`;
- `mpv_restart=0`;
- `ipc_timeout=0`;
- `panfrost_faults=0`;
- `mmc_timeout_reset=0`.

Os probes `kiosky_playback_observer_probe.sh` e
`kiosky_service_observer_probe.sh` ja produzem um resumo sanitizado com
`c18_decode_health_passed`. Uma falha nesse campo torna o probe nao-verde. Esse
campo cobre o subconjunto de decode/runtime (`hwdec-current`, `vo-configured`,
progresso e falhas sanitizadas do status); nao substitui o deep-health completo
necessario para descongelar OTA de player.

O contrato completo deve passar por `scripts/board/c18_playback_health_summary.py`
e pelos fixtures de `scripts/qa/c18_playback_deep_health_fixture_test.py`.
Esse avaliador consome apenas artefatos sanitizados (`playback-samples.tsv` e
sidecars de systemd/processo/kernel/contadores) e emite
`dadooh.c18.playback.deep_health.v1`.
O coletor nao destrutivo preferencial e
`scripts/board/c18_playback_health_collect.py`: ele observa o servico real por
IPC/status/systemd/proc/journal, escreve os sidecars `deep-health-*.json` e o
`playback-deep-health-public.json`, e nao chama stop/start/restart do servico.
Para candidato `player-runtime`, o mesmo coletor tem modo `candidate`: ele
filtra o processo MPV pelo `--input-ipc-server` do candidato e permite coexistir
com o MPV do servico vivo sem reprovar por contagem global de processos. O
runner `scripts/board/c18_player_runtime_candidate_health.py` e somente de
laboratorio: exige `--lab-only-candidate-runner` e
`C18_PLAYER_RUNTIME_CANDIDATE_HEALTH_LAB_ONLY=1`, cria config temporaria
sanitizada, desliga UI/telemetria/segredos, usa IPC/status/log/cache isolados e
devolve os hashes observados do release testado. Esse runner nao altera o CLI
publico do updater, nao liga auto-pull e nao autoriza thaw de producao.
Quando o candidato nao deve usar API real, o runner pode receber
`--canary-media` apontando para um video local explicito sob `/tmp` ou
`/data/media`; ele cria uma playlist offline no state temporario do candidato e
publica apenas `canary_media_used=true/false`, nao o path da midia.
O harness `scripts/qa/c18_player_runtime_lab_apply.py` e o unico caminho
repo-side para exercitar apply local de candidato antes do thaw publico: exige
`--lab-only-apply` e `C18_PLAYER_RUNTIME_LAB_APPLY=1`, aceita somente
manifest/payload locais, roda o gate de release, injeta o runner de health como
hook interno e confirma ao final que o CLI publico continua congelado com
`rc=44` para apply e plain reconcile. Por padrao usa `data_root` temporario em
sandbox; tocar `/data` exige tambem `--allow-device-data-root` e
`C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1`.
Ele nao usa GitHub, timer, auto-pull nem policy permanente do device.
O escape simetrico de laboratorio e
`scripts/qa/c18_player_runtime_lab_rollback.py`: exige
`--lab-only-rollback` e `C18_PLAYER_RUNTIME_LAB_ROLLBACK=1`, confirma que o CLI
publico de apply/rollback/reconcile continua congelado com `rc=44`, e so toca
`/data` com `--allow-device-data-root` +
`C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1`.
Qualquer ensaio persistente em `/data/player-runtime/current` deve provar esse
rollback/reconcile antes de promover o proximo degrau de homologacao.
Em hardware com DRM, o candidato pode precisar de uma janela de laboratorio com
o `kiosky-player.service` parado para adquirir DRM master. Essa pausa deve ser
controlada, reversivel e seguida de novo deep-health do servico real; nao e
permissao para auto-pull nem para thaw publico.
O `scripts/board/kiosky_service_observer_probe.sh` continua como diagnostico de
referencia mais amplo, mas para validacao de update ele e intrusivo porque para
o servico ao final da observacao. O probe manual de playback continua sendo
diagnostico auxiliar e nao substitui a validacao do servico.

O deep-health C18 deve falhar fechado quando a evidencia de progresso de frame
estiver ausente ou congelada. `time_pos` e diagnostico util, mas nao pode aprovar
sozinho uma janela de playback com `estimated_frame_number` travado, pois esse e
o modo de falha que a linha C18 precisa barrar antes de qualquer thaw de player.
Em janela multi-item, o avaliador deve exigir progresso em todos os segmentos
avaliaveis; nao basta o ultimo segmento passar depois de um stall anterior.
No modo `candidate`, `last_poll_error` so pode ser tolerado quando o status
sanitizado indicar explicitamente `polling_disabled`; erro generico presente
continua falha de health.

Evidencia de ensaio `player-runtime` precisa ser inspecionavel e sanitizada.
Antes de versionar qualquer rodada, rodar
`scripts/qa/c18_player_runtime_evidence_gate.py --run-dir <dir>`. O gate aceita
somente README, manifest/gate JSON, JSONs dos harnesses, marker verificado e os
artefatos publicos de deep-health (`playback-samples.tsv`,
`status-samples.ndjson`, sidecars `deep-health-*.json` e
`playback-deep-health-public.json`). Ele rejeita tarballs, logs, config/seed,
playlist com path de canario, `raw/`, `extracted/`, paths de midia/config e
padroes de segredo/URL/IP/MAC.

Evidencia que reivindica cold-boot precisa trazer um discriminador de boot
auditavel. Para as proximas rodadas, incluir `pre-state-public.json` antes do
reboot e `boot-state-public.json` depois do reboot, ambos gerados por
`scripts/board/c18_coldboot_state_collect.py` e validados por
`scripts/qa/c18_coldboot_evidence_gate.py`. O pre-state deve ser artefato
mecanico: schema `dadooh.c18.coldboot_pre_state.v1`, nonce, hash sanitizado do
`boot_id`, `btime`, identidade de imagem via marker em `/etc/dadooh`, mount de
`/` e `/data`, contrato systemd, fonte do launcher e flags de privacidade. O
post-state deve referenciar esse pre-state por `sha256` e nonce. O gate forte
para uma evidencia nova deve usar `--require-pre-state` e, quando a rodada
reivindicar acao fisica especifica, `--expect-transition-flow`,
`--expect-mechanical-action` e/ou `--forbid-controlled-reboot`. Com
`--require-pre-state`, o gate tambem precisa falhar fechado se o pre-state nao
estiver temporalmente proximo ao reboot, se o marker de imagem estiver ausente
ou divergir entre pre/post, ou se o fallback `/opt` nao estiver presente.

O cold-boot gate prova consistencia interna e cadeia de handoff dos artefatos,
nao autenticidade criptografica contra operador malicioso. Sem pre-state
mecanico, a evidencia pode continuar util como smoke de servico, mas nao deve
ser usada como prova decisoria de cold-boot ou de adocao por `/data`.
Evidencia que seleciona ou demonstra `/data` deve falhar fechado se tentar
passar pelo modo fraco: o gate deriva essa condicao de `selected_source=data`,
do probe de adocao ou de `data_current_marker_verified=true`, mesmo quando a
chamada usa `--expect-selected-source=any`. Nesse caso, o gate exige pre-state
forte e uma identidade de imagem esperada (`--expect-image-tag` ou
`--expect-image-marker-sha256`) antes de aceitar a evidencia. Essa mesma
evidencia cold-boot `/data` tambem deve trazer `source_commit`, `repo_commit`,
`repo_tree` e `repo_dirty=false` no `evidence-manifest.json`; `repo_commit`
deve casar com `source_commit`.

Se a evidencia reivindicar adocao de `/data/player-runtime/current`, ela tambem
precisa incluir `launcher-adoption.json` do probe de adocao real, com processo
em execucao, marker valido e identidade rodando batendo com o marker. A
evidencia tambem deve registrar identidade do repo (`repo_commit`, `repo_tree`,
`repo_dirty=false`, tag quando houver) e identidade da imagem/marker do device
para reduzir drift entre repo, imagem gerada e placa validada. Em trials novos,
`repo_commit` deve casar com o `source_commit` do pacote sob teste; o gate de
evidencia de `player-runtime` exige esses campos e tambem exige
`image_tag`/`image_sha256`/marker `/etc/dadooh`. Em rodadas decisivas, o mesmo
gate deve ser invocado com `--expect-image-tag`, `--expect-image-sha256` e/ou
`--expect-image-marker-sha256` pinados a golden esperada; presenca/shape de
imagem serve apenas para leitura historica ou trial warm nao decisivo.
O registro canônico da golden atual fica em
`docs/evidence/c18-update-validation/current-golden.json`; gates e testes devem
ler essa fonte em vez de duplicar tag/sha da imagem. O
`c18_ota_release_gate.py` separa `--player-runtime-evidence-mode baseline`
(default; valida baseline/fallback historico e declara non-claims de `/data`) de
`--player-runtime-evidence-mode decisive` (M-6). No modo `decisive`,
`--player-runtime-data-coldboot-evidence-dir` e
`--player-runtime-data-evidence-dir` sao obrigatorios; o primeiro roda o
coldboot gate com `--expect-selected-source=data` e `--require-pre-state`, o
segundo roda o gate de evidencia `player-runtime` com `--expect-image-*` pinado
a identidade de imagem esperada da invocacao (por default a golden corrente,
mas sobrescrevivel por uma tripla explicita), e o release gate cruza o
marker/version/tree/kiosk entre as duas evidencias. Sem modo `decisive`, o
release gate nao prova cold-boot `/data`.
No modo `decisive`, os diretorios de evidencia de coldboot/data tambem passam
por git-guard: precisam estar dentro do repo, rastreados, sem arquivos
ignorados/untracked e com `evidence-manifest.json` apontando apenas para
entradas rastreadas. O H2 readiness gate aplica a mesma regra ao bundle de
entrada completo e exige arvore limpa, para evitar que evidencia local ou
mutada fora do HEAD sustente uma conclusao de readiness.

O registro `current-golden.json` e a autorizacao decisiva de `player-runtime`
podem divergir durante H1/H2: hoje a golden de recovery/delivery permanece
`c18-hwdecode-lab-1u`, enquanto a evidencia decisiva lab de `player-runtime`
esta pinada explicitamente ao bundle `c18-hwdecode-lab-1x`. Essa divergencia
nao promove a `1x` como baseline/fallback geral e nao abre thaw; ela apenas
exige que invocacoes decisivas usem a tripla explicita da imagem validada
(`--expect-image-tag`, `--expect-image-sha256`, `--expect-image-marker-sha256`)
em vez de depender do default da golden corrente. A tripla H1 atual e
`c18-hwdecode-lab-1x`,
`1a853f569b5da9e856439897c95612d719fd3059f12349fa1040a6350c3df2f2`,
`59739f57cdb3f79ac4c8ce5e5e1f9c4aa6d9dae58f704010f8423e66abe2bb9e`.
Promover/unificar a golden requer evidencia propria de baseline/fallback e
atualizacao de `current-golden.json`.

Interrupcao/power-loss durante apply/rollback de `player-runtime` deve ser
provada em duas camadas. A camada offline usa fault-injection no caminho real do
updater para matar apply/rollback em fronteiras conhecidas e exigir que
reconcile termine em `current` verificado ou fallback `/opt`, nunca em release
nao verificada. A camada fisica de power-cut continua gate de homologacao e nao
fica satisfeita apenas pelo teste offline.
Antes de rodar a camada fisica, o preflight H2
`c18_player_runtime_h2_powerloss_preflight_collect.py` +
`c18_player_runtime_h2_powerloss_preflight_gate.py` deve validar placa, bundle,
imagem, policy/timer e topologia contra o plano da matriz; ele e preparatorio e
nao substitui evidencia de corte real.

Para uma evidencia A->B->A ser aceita como rollback para `previous` real, ela
precisa declarar `rollback_expectation=data-previous`, conter
`service-before-apply`, provar que A estava ativa e verificada em `/data`,
provar que B tem `tree_sha256` distinto de A, registrar `previous_link`/state
apontando para A apos o apply de B, e registrar rollback com
`expected_rolled_to=A`, `rolled_back_to=A` e servico readotando A por marker
valido. Retorno para `image_fallback` e sucesso operacional, mas nao conta como
A->B->A.

O builder local `scripts/deploy/build_player_runtime_release_package.sh` cria
um pacote lab-only de `player-runtime` a partir do snapshot governado e roda
`scripts/qa/c18_player_runtime_release_gate.py` antes de promover payload e
manifest ao diretorio final. O mesmo diretorio tambem preserva
`c18-player-runtime-release-gate.json`, validado como verde antes da promocao
local, para que a etapa server-side futura tenha artefato real a assinar. Ele
nao publica, nao toca a placa e nao descongela o `rc=44` do updater. Por
construcao, esse builder nao gera canal `stable`; um manifest `player-runtime`
com `channel=stable` tambem e rejeitado pelo gate.

Sem esse gate, update de player fica restrito a imagem/homologacao manual.

## Quando Gerar Imagem

Gerar nova imagem quando a mudanca tocar:

- `kiosk.py`;
- `kiosky_service_launcher.sh`;
- MPV/ffmpeg/hwdecode/libplacebo/wrapper de MPV;
- kernel, DTB, U-Boot, BSP, display/HDMI;
- updater `totem-updatectl`;
- systemd units/timers;
- policy de update de fabrica;
- qualquer mudanca que exige reboot ou alteracao fora de `/data/core/totem`.

## Scripts Bypass E Historicos

Scripts de SSH/rsync/hotfix direto sao ferramentas de bancada ou evidência
histórica. Eles nao sao caminho de update C18, nao substituem release GitHub e
nao devem ser usados para campo/producao.

Exemplos de bypass/lab-only:

- `scripts/remote/push_and_run.sh`;
- `scripts/remote/deploy_kiosky_player.sh`;
- `scripts/remote/apply_c15_1_1_session_hotfix.sh`;
- scripts antigos `run_c*` que copiam/aplicam mudanças diretamente na placa.

Scripts historicos de release de `kiosky-player` tambem nao liberam OTA de
player na C18. `ALLOW_C18_FROZEN_PLAYER_RELEASE=1` e apenas bypass de
reproducao legada/lab, nao aprovacao de release C18-aware. Mesmo com esse bypass,
os scripts historicos nao podem gerar nem publicar `channel=stable`, e o
publisher deve exigir `source_commit` completo e `created_at_utc` valido. Um
pacote `player-runtime` C18-aware exige contrato, gate e homologacao novos.

Scripts remotos historicos que alteram player, `/opt`, systemd ou estado fora
do OTA comum devem falhar fechados por padrao. Excecoes de bancada exigem uma
variavel explicita, como `ALLOW_LEGACY_C14_UPDATE_BYPASS=1` para fluxo C14 ou
`ALLOW_LEGACY_C18_REMOTE_BYPASS=1` para hotfix/bootstrap remoto historico.
Esses flags nao aprovam uso de campo nem substituem release OTA.

Todo comando C18 de update operacional deve declarar `--component totem-core`.
Comandos sem `--component` preservam default historico/legado do updater e nao
devem ser copiados para procedimentos C18.

## Stable E Producao

`stable` nao e apenas `channel=stable`. Antes de stable/batch, exigir gate de
promocao proprio, homologacao fisica, policy stable, `allow_prerelease=false`,
rollback definido, evidencia sanitizada e decisao explicita sobre imagem final.
Os builders/publishers C18 devem falhar fechados para `stable` sem
`ALLOW_C18_STABLE_PROMOTION=1` e uma evidencia JSON aprovada
`dadooh.c18.stable_promotion.v1` validada por
`scripts/qa/c18_stable_promotion_gate.py`. Esse gate exige H2 readiness,
power-loss 17/17, semantica power-loss completa, soak 24h, governanca
server-side, release gate, operador, rollback owner e hashes das evidencias; um
JSON minimo com `approved=true` nao e suficiente. Quando consumido pelo H2,
o gate e componente-amarrado: `player-runtime` exige
`expected_component=player-runtime`, e evidencia `totem-core` nao satisfaz thaw
de `player-runtime`. Tambem fora do H2, a CLI aceita `--expected-component` e
mantem `totem-core` como default para os fluxos atuais. Nessa avaliacao,
esses hashes devem bater com os arquivos de evidencia efetivamente passados ao
avaliador (`release_gate`, server-side, trust anchor server-side, soak, matriz
power-loss e bundle H2 pre-stable); hashes arbitrarios ou stale nao fecham a
promocao. O publisher de
`totem-core` deve preservar `c18-ota-release-gate.json` junto da release para
manter a trilha de auditoria. O release gate de `player-runtime` tambem emite
um bloco `package` portavel (`manifest`, `payload`, `payload_sha256`,
`source_commit`, `component`, `channel`) para ser consumido por
assinatura/attestation server-side; o builder de `player-runtime` preserva esse
JSON junto do payload e manifest no diretorio da release. O stable gate tambem
aceita esses caminhos como argumentos para validar os hashes em modo
artifact-bound fora do H2. No caminho CLI/build/publish de `stable`, esses
argumentos sao obrigatorios; chamar o gate somente com `--evidence` falha
fechado para impedir promocao baseada em hashes declarados sem arquivos reais.
O gate tambem valida a semantica dos artefatos
recebidos nesse caminho: release gate precisa estar verde, matriz power-loss
precisa estar completa e passar seus subgates, soak precisa cobrir 24h,
server-side precisa passar com chave publica confiavel externa + trust anchor, e
a decisao do operador precisa estar aprovada.
No publish de `totem-core` stable, o release gate final gerado deve manter o
mesmo SHA do `--stable-release-gate-summary` validado pela stable evidence, e o
publisher deve anexar a familia server-side validada: evidence JSON,
manifest/payload/release-gate/audit-log apontados por `release_assets`, provas
ou assinaturas apontadas por `asset_attestations`, e a trust-anchor evidence
externa. A chave publica confiavel continua entrada externa de validacao; ela
nao e promovida como payload de updater. A lista final de assets entregue ao
GitHub Release e montada por `scripts/qa/c18_totem_core_publish_asset_list.py`
apos esses gates, exigindo `c18-stable-promotion-evidence.json` e ao menos um
asset server-side em `stable`, rejeitando anexos stable em canais nao-stable e
deduplicando sem remover os artefatos obrigatorios.

Para `player-runtime`, a leitura H2 antes de qualquer thaw publico deve passar
por `scripts/qa/c18_player_runtime_h2_readiness_gate.py`. Esse avaliador e
off-board e falha fechado enquanto faltar qualquer familia requerida: bundle H1
decisivo, matriz fisica power-loss 17/17, semantica implementada para cada
checkpoint da matriz, soak 24h, governanca server-side com
assinatura/attestation, evidencia de promocao stable e decisao explicita do
operador. Ele nao altera o freeze `rc=44` e nao publica releases.

A decisao explicita do operador para thaw publico de `player-runtime` deve ser
um artefato proprio `dadooh.c18.player_runtime.thaw_decision.v1`, validado por
`scripts/qa/c18_player_runtime_thaw_decision_gate.py`. O artefato deve estar em
`channel=stable`, `component=player-runtime`, trazer operador, rollback owner,
janela UTC ativa de no maximo 4h, pacote/source/payload alvo, hashes das
familias H2/stable requeridas, `auto_pull_enabled=false`,
`thaw_execution_performed=false` e
non-claims explicitos. Esse gate nao executa thaw, nao publica release, nao
habilita auto-pull e nao substitui H2 verde; ele apenas torna a autorizacao
auditavel e artifact-bound.

Para reduzir erro operacional quando os testes fisicos terminarem, o scaffold
fail-closed dos artefatos finais deve ser gerado por
`scripts/qa/c18_player_runtime_stable_decision_draft_build.py`. O builder e
offline, calcula os hashes dos artefatos reais e deriva pacote/source/payload da
evidencia server-side, mas escreve `approved=false`, campos de operador vazios e
janela de thaw invalida. A saida deve falhar nos gates ate que H2 esteja verde e
um operador preencha a decisao real; o script nao publica release, nao habilita
auto-pull, nao executa thaw e nao remove o freeze publico `rc=44`. `passed=true`
nesse builder significa apenas que os rascunhos foram escritos e continuam
fail-closed; nao significa autorizacao de stable, thaw ou publish.
O diretorio final de evidencia deve versionar, no minimo,
`c18-stable-promotion-evidence.json`, `c18-player-runtime-thaw-decision.json`,
`h2-readiness-final.json` e README com non-claims/hashes.
No desenho atual, a decisao `stable` para `player-runtime` continua apontando
para o pacote homologation hash-bound validado em `releases/player-runtime`;
nao se cria um manifest `player-runtime channel=stable` para contornar o freeze.

A familia de governanca server-side deve ser validada antes de entrar no H2 por
`scripts/qa/c18_server_side_publish_governance_gate.py`, com schema
`dadooh.c18.server_side_publish_governance.v1`. Esse gate exige publish gate,
assets verificaveis, assinatura ou attestation, politica de auto-pull definida
mas desabilitada por padrao, canais exatos, promocao stable obrigatoria,
allowlist, staged rollout, rollback, trilha de auditoria, escopo exato
`totem-core` + `player-runtime` e escopos proibidos explicitos para
`kiosky-player`, `media-system` e `field-data`. A evidencia nao pode ser apenas
um conjunto de flags: deve apontar para manifest, payload, resumo do release
gate, provas de assinatura/attestation e log de auditoria existentes no
diretorio da release, sem symlink/out-of-dir, com hashes conferidos contra os
arquivos; o log de auditoria tambem precisa ser hash-bound/attested. Para
assinatura real, o gate verifica uma prova JSON canonica assinada por OpenSSL
RSA-SHA256, com fingerprint SHA256 do SPKI DER da chave publica, `release_set`
hash-bound cobrindo manifest, payload, release gate e audit-log, chave publica
passada explicitamente por `--trusted-key-pem` fora do diretorio da release, e
evidencia operacional separada `dadooh.c18.server_side_trust_anchor.v1`
passada por `--trust-anchor-evidence`. Essa evidencia registra
`trusted_key_spki_sha256`, algoritmo, escopo de componentes/canais,
`selected_by`, `selected_at_utc`, ausencia de material privado e non-claim de
cadeia PKI; ela tambem deve ficar fora do diretorio da release. Caminhos de
trust key e trust anchor nao podem conter symlink em nenhum componente, e o JSON
de trust anchor e fechado a campos conhecidos: claims PKI extras, mesmo
positivos, bloqueiam a evidencia. H2 e stable carregam
`server_side_trust_anchor_evidence_sha256` para impedir troca silenciosa da
chave entre readiness e promocao.
Quando consumido pelo H2 de `player-runtime`, esse gate e invocado com
`expected_component=player-runtime`: manifest/release gate de `totem-core` nao
satisfazem thaw de `player-runtime`, mesmo que a politica global server-side
tenha escopo para ambos os componentes.
Tambem deve trazer politica de canal, auto-pull, allowlist, rollout, rollback e
eventos de auditoria obrigatorios. Fora de self-test, fixture e evidencia sem
trust anchor/signature verificada continuam bloqueadas; o gate nao publica
release, nao habilita auto-pull, nao promove stable e nao faz thaw de
`player-runtime`.
Para produzir essa familia a partir de uma release ja existente, use
`scripts/qa/c18_server_side_publish_evidence_build.py`: o gerador e offline,
exige chave privada de assinatura, chave publica confiavel e trust-anchor fora
do diretorio da release, escreve `audit-log.ndjson`, provas JSON canonicas,
assinaturas destacadas e `c18-server-side-publish-governance.json`, e em seguida
reroda o gate real. Ele tambem nao publica release, nao habilita auto-pull, nao
promove stable e nao faz thaw.
Para materializar o inventario dos assets que seriam anexados, use
`scripts/qa/c18_server_side_publish_asset_collect.py --relative-to . --json`.
A saida `dadooh.c18.server_side_publish_asset_list.v1` deve conter paths
repo-relative, bytes e SHA256; ela e evidencia de inventario, nao publicacao.

Entre H1 e H2 existe somente um caminho intermediario controlado:
`scripts/qa/c18_player_runtime_pilot_readiness_gate.py`, para piloto assistido
com `channel=homologation` e `ring=pilot`. Esse gate exige autorizacao formal,
preflight da placa com public freeze `rc=44`, pacote homologation alvo, H1
decisivo image-bound e P0 power-loss seletivo. Ele nao autoriza producao,
`stable`, auto-pull, thaw publico, soak 24h, power-loss 17/17 ou
assinatura/attestation.

CI ampliado, bridge de updater e A/B de imagem sao hardening futuro. Ja
assinatura/attestation operacional nao e futuro para producao: continua requisito
H2/server-side antes de `stable`; apenas fica fora do piloto manual imediato.
