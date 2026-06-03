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
validado na imagem `c18-hwdecode-lab-1i` e segue validado na golden `1l`:
upstream `dadoohai/kiosky-player` em `c25659aff200d9aac1720e60e60794c432c79393`
mais o patch C18 de `DEFAULT_CONFIG.mpv_path` para
`/opt/totem/bin/totem-mpv-hwdecode`.

Esse snapshot e fonte governada para imagem/gate, nao pacote OTA. Mudancas nele,
no launcher/drop-in do player ou em outros arquivos fixos por imagem devem
bloquear o gate OTA comum de `totem-core` e exigir gate separado de
`player-runtime`, nova imagem ou homologacao.

Qualquer pacote futuro de `player-runtime` deve passar antes por
`scripts/qa/c18_player_runtime_release_gate.py`. Esse gate abre o payload,
confere o SHA do manifest, rejeita path traversal, symlink/hardlink, config,
seed, marker pre-forjado, arquivos de controle/imagem e arquivos com cara de
segredo, e exige `kiosk.py` compilavel preservando o wrapper e o HW decode C18
nos defaults, em `build_mpv_args` e no caminho efetivo ate
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
boot. A fonte da proxima imagem tambem executa esse reconcile como
`ExecStartPre=-...` nao-fatal antes do player, preservando o launcher como
barreira primaria.

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
- manifest com contrato C18 completo;
- payload com SHA correto e sem path traversal, symlink, hardlink ou segredo;
- release GitHub publicada a partir do `source_commit` declarado no manifest,
  nunca do default branch implicito do `gh`;
- policy/service/timer C18 coerentes;
- freeze de `kiosky-player` preservado;
- scripts historicos de release de `kiosky-player` falhando por padrao, salvo
  override explicito para release `player-runtime` C18-aware homologada;
- diff OTA comum sem arquivos `player-runtime` fixos por imagem;
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
- `time-pos` ou `estimated-frame-number` avancando;
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
O harness `scripts/qa/c18_player_runtime_lab_apply.py` e o unico caminho
repo-side para exercitar apply local de candidato antes do thaw publico: exige
`--lab-only-apply` e `C18_PLAYER_RUNTIME_LAB_APPLY=1`, aceita somente
manifest/payload locais, roda o gate de release, injeta o runner de health como
hook interno e confirma ao final que o CLI publico continua congelado com
`rc=44`. Por padrao usa `data_root` temporario em sandbox; tocar `/data` exige
tambem `--allow-device-data-root` e `C18_PLAYER_RUNTIME_ALLOW_DEVICE_DATA_ROOT=1`.
Ele nao usa GitHub, timer, auto-pull nem policy permanente do device.
O `scripts/board/kiosky_service_observer_probe.sh` continua como diagnostico de
referencia mais amplo, mas para validacao de update ele e intrusivo porque para
o servico ao final da observacao. O probe manual de playback continua sendo
diagnostico auxiliar e nao substitui a validacao do servico.

O builder local `scripts/deploy/build_player_runtime_release_package.sh` cria
um pacote lab-only de `player-runtime` a partir do snapshot governado e roda
`scripts/qa/c18_player_runtime_release_gate.py` antes de promover payload e
manifest ao diretorio final. Ele nao publica, nao toca a placa e nao descongela
o `rc=44` do updater. Por construcao, esse builder nao gera canal `stable`; um
manifest `player-runtime` com `channel=stable` tambem e rejeitado pelo gate.

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
reproducao legada/lab, nao aprovacao de release C18-aware. Um pacote
`player-runtime` C18-aware exige contrato, gate e homologacao novos.

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
`dadooh.c18.stable_promotion.v1`. O publisher de `totem-core` deve preservar
`c18-ota-release-gate.json` junto da release para manter a trilha de auditoria.

CI, assinatura/attestation, bridge de updater e A/B de imagem sao hardening
futuro; nao fazem parte do OTA manual imediato.
