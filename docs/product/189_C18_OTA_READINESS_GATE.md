# 189 — C18.OTA-READINESS-GATE

Rodada de proteção do OTA C18. Objetivo: permitir evolução rápida do wizard/core
sem criar um caminho acidental para regredir o playback/hwdecode validado na
golden atual `1l`.

## Decisão

- OTA C18 imediato = `totem-core` **manual/operator-triggered**.
- `kiosky-player`, MPV e `/opt/totem/hwdecode` ficam **congelados fora do OTA**.
- Imagem C18 nova deve nascer com `/data/updates/policy.json` restritivo:
  `device_track="c18-hwdecode"`, `allowed_components=["totem-core"]`,
  `allow_downgrade=false`.
- `totem-update-agent.timer` nasce desabilitado; auto-pull fica fora de escopo
  até hardening posterior.
- O service de update aponta para
  `apply-github-latest --component totem-core --repo dadoohai/orange_pi_totem`
  e exige policy presente.

## Golden atual (2026-06-03)

Marco de referência para continuidade C18/delivery:

- **Imagem gravável golden:** `c18-hwdecode-lab-1l`;
- **Arquivo:**
  `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1l_minimal.img`;
- **sha256:**
  `146b430972b61523cf943f467b94ccf56697843a48147ec5b1839db3583b1ad3`;
- **Tamanho:** `1971322880` bytes;
- **Estado:** golden de laboratorio/delivery, ainda `final_image=false` e nao
  `stable`/batch de producao;
- **Estado runtime esperado apos aplicar OTA de homologacao atual:**
  `totem-core` em
  `c18.ota-core-config-missing-20260603T150429Z-2a7a327`, com `previous` no
  embed `c17.6-environment-input-20260514T211247Z`;
- **Player/runtime esperado:** fallback de imagem, sem `/data/player-runtime/current`
  e sem `/data/apps/kiosky-player/current`; `hwdec-current=v4l2request-copy`,
  `vo-configured=true`, `NRestarts=0`;
- **Update posture:** OTA manual somente para `totem-core`; auto-pull desligado;
  `kiosky-player` e `player-runtime` bloqueados com `rc=44` ate thaw explicito.

Ou seja: para regravar uma placa de laboratorio hoje, partir da imagem `1l`.
Depois, se a validacao desejada for o marco mais recente de delivery, aplicar a
release OTA de homologacao acima. Nao substituir essa golden por uma imagem nova
sem nova validacao offline + hardware + registro neste doc.

Nota: `1k` permanece como golden historica anterior. A `1l` valida em hardware
o fechamento das dividas pre-thaw imediatas: gate semantico endurecido,
`reconcile` no boot e deriver que so promove imagem apos `offline_ok`. O
`player-runtime` continua congelado no fluxo publico (`rc=44`).

## Implementação no repo

- `scripts/board/totem_update_policy.json`: policy canônica C18 lab/homologation.
- `scripts/board/systemd/totem-update-agent.service`: alvo `totem-core`, com
  `ConditionPathExists=/data/updates/policy.json`.
- `scripts/board/totem_appliance_manifest.json`: timer manifestado como
  `enabled=false`.
- `scripts/build/totem_core_image_embed.py`: escreve policy/service/timer e
  remove o symlink `timers.target.wants/totem-update-agent.timer` na rootfs.
- `scripts/board/totem_updatectl.py`: bloqueia apply de `kiosky-player`, aplica
  regra conservadora de downgrade, limpa staging em `incoming`, pagina releases
  do GitHub, falha fechada sem policy e rejeita manifests/payloads com contrato
  C18 incompleto ou tipos de tar inseguros.
- `scripts/qa/c18_ota_release_gate.py`: gate offline unico para merge/publicacao
  de `totem-core`, incluindo pacote real quando informado.

## Gates

- Testes estáticos de policy/service/timer.
- Testes unitários de freeze, downgrade e GC de staging.
- Sandbox `totem-core` apply/rollback/settings-lock.
- Validacao offline + hardware da imagem corrente deve comprovar policy
  presente, timer desligado, service apontando para `totem-core`, sem config
  real embutida, `player-runtime` ainda congelado e launcher adotando `/data`
  apenas com marker verificado.

## Contrato futuro de OTA

Toda release C18 nova de `totem-core` deve declarar no manifest:

- `requires.base_image_min="c17.4.2"` para esta linha;
- `requires.device_track="c18-hwdecode"`;
- `requires.updater_features` contendo `c18-freeze-kiosky-player-v1`,
  `c18-rollback-reapply-v1`, `c18-safe-payload-v1` e `c18-track-v1`.

Updater `1h+` que nao encontrar esses campos, nao entender uma chave nova em
`requires`, encontrar track diferente, base incompatível, feature ausente ou
feature desconhecida deve rejeitar a release. Se uma mudanca futura precisar
novo updater, nova unit, novo pacote do sistema, player/MPV/hwdecode ou reboot
para se tornar verdadeira, ela nao pertence ao OTA normal de `totem-core`; deve
vir como nova imagem ou release ponte explicitamente homologada.

## Estado live, imagens e OTA smoke (2026-06-02)

- Imagem gerada: `c18-hwdecode-lab-1e`
  (`sha256=b782421c684783bdeba029c90b014f3a469888d34d69caf524e5a69d88dff211`),
  ainda `final_image=false` / lab privada.
- Base C17.4.2 lida de `/mnt/d/images_orange`; symlink local mantido em
  `armbian-build-v25.11/output/images/` para o deriver continuar reprodutivel.
- Validação offline da rootfs: policy presente, timer sem wants symlink,
  service apontando para `totem-core`, `totem-core` current/fallback presentes,
  `state.json` com `manifest_created_at_utc`, fsck limpo.
- Validação em placa limpa apos flash:
  - marker `c18-hwdecode-lab-1e` presente;
  - `totem-update-agent.timer` `disabled`/`inactive`;
  - `totem-update-agent.service` aponta para
    `--component totem-core --repo dadoohai/orange_pi_totem`;
  - `/data/updates/policy.json` permite somente `totem-core`;
  - `/data/apps/kiosky-player/current` ausente; player usa fallback C18 em
    `/opt/totem/kiosky-player`.
- Config real aplicada via seed de homologacao local, sem publicar valores
  privados: `/data/config/config.json` criado pelo writer guardado; artefatos
  temporarios privados removidos.
- Player pos-config: `player_running`, `playback=playing`, display conectado,
  `NRestarts=0`.
- MPV pos-config: processo em `/opt/totem/hwdecode/bin/mpv` via wrapper C18,
  `--vo=gpu --gpu-context=drm --hwdec=v4l2request-copy`,
  `hwdec-current=v4l2request-copy`, `vo-configured=true`.
- Amostra curta de playback pos-config: 2 trocas de item, `failures=0`,
  `NRestarts=0`, RSS ~118 MB, CPU ~45% de um core nos itens amostrados.
- Guarda de regressao confirmada: `apply-local --component kiosky-player`
  falha com `rc=44` (`component_frozen_for_ota`), independente da policy.
- Residuo conhecido fora do escopo C18: `console-setup.service` falhado no boot
  por setup de fonte/keymap; nao afetou player/OTA e nao deve abrir frente agora.
- Release homologation publicada para smoke manual:
  `totem-core-c18.ota-core-smoke-20260602T190718Z-8a1d640`.
  Manifest: `component=totem-core`, `channel=homologation`,
  `source_branch=foundation-v0.1`, `source_commit=8a1d640...`,
  `source_dirty=false`, `payload_sha256=a8e67c3112fb31e6f4718ac97e4c7a39f5a56e72bf8bf833febcd62f25d09674`.
- `apply-github-latest --dry-run` selecionou exatamente essa release e nao
  mudou estado.
- `apply-github-latest` manual passou: `current` virou
  `c18.ota-core-smoke-20260602T190718Z-8a1d640`, `previous` virou o embed
  `c17.6-environment-input-20260514T211247Z`, policy continuou somente
  `totem-core`, timer continuou desligado, player continuou `active`,
  `NRestarts=0`.
- Rollback real passou para o embed C17.6. A primeira tentativa de reapply
  encontrou bug real no guard de downgrade (`rc=45`) porque a release mais nova
  estava em `previous`.
- Hotfix do updater aplicado in-place na placa lab (backup preservado em
  `/opt/totem/bin/totem-updatectl.pre-c18fix-*`) e incorporado ao repo:
  - reapply de `previous` e mais novo que `current` e permitido com
    `allow_downgrade=false`;
  - versoes/payloads de manifest agora rejeitam `.`/`..`, path traversal,
    path absoluto/subdiretorio e payload fora do nome esperado.
- Repeticao apos hotfix: rollback para C17.6 + reapply GitHub da release C18
  passou com `allow_downgrade=false`; placa terminou em `current=C18 smoke`,
  `previous=C17.6 embed`, player `active`, `NRestarts=0`, timer `disabled`.
- Build offline subsequente gerou `c18-hwdecode-lab-1f` (nao reusar o nome
  `1e`, pois o conteudo do updater mudou apos a imagem `1e` ja ter sido
  gravada/validada).
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1f_minimal.img`
  - `sha256=bbcf59950324f6629db56c0d542ce03f25bd8f6ad3b38fb60127d2d219da793f`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Ainda nao foi validada em hardware como flash limpo.
- Auditoria independente pos-1f apontou P1 de endurecimento antes de campo:
  manifest sem track/features ainda passava no device, `base_image_min` era
  apenas tipado, policy ausente permitia default e tar aceitava links. Esses
  pontos foram tratados no lote `1g`; por isso `1f` fica como validação limpa de
  config/playback, nao como proxima base de campo.
- Build offline subsequente gerou `c18-hwdecode-lab-1g` como endurecimento
  intermediario. A auditoria de governanca seguinte apontou uma fronteira ainda
  porosa: `kiosky_service_launcher.sh` estava no payload/fallback de
  `totem-core`, permitindo que uma OTA de core alterasse o start do player. Por
  isso `1g` foi supersedida antes de validacao em hardware.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1g_minimal.img`
  - `sha256=e6c59038f6141454261e8313ef9dc028782fec13ffcbf42331a23464548defa1`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Ainda nao foi validada em hardware como flash limpo.
- Build offline subsequente gerou `c18-hwdecode-lab-1h` como fechamento da
  fronteira `totem-core`/`player-runtime`. A validação em placa limpa mostrou
  que a imagem estava correta no contrato OTA, mas o seed de homologacao ainda
  continha `mpv_path="mpv"`; ao gravar a config real, isso sobrescrevia o
  wrapper C18 e fazia o player subir com `/usr/bin/mpv` e
  `hwdec-current=no`. Por isso `1h` foi supersedida antes de virar baseline.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1h_minimal.img`
  - `sha256=778b60b86ea7487e1d4661c3f53f17c598894274fdf76b629d671c80865f8393`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`
    e `totem_core_release_excludes_kiosky_service_launcher.sh=true`.
  - Validada em hardware somente ate o achado do seed; nao usar como proxima
    base de campo.
- Build offline subsequente gerou `c18-hwdecode-lab-1i`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1i_minimal.img`
  - `sha256=5944f284fec4025b021413608a7bc98034a088046d742c09496e634a37074c4e`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`
    e `totem_core_release_excludes_kiosky_service_launcher.sh=true`.
  - Seed de homologacao preserva HW decode:
    `homologation_seed_mpv_path_points_to_wrapper=true`.
  - Validada em hardware como flash limpo:
    - marker `c18-hwdecode-lab-1i` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `kiosky_service_launcher.sh` fixo na imagem, fora do payload
      `totem-core`;
    - `/data/apps/kiosky-player/current` ausente.
  - Config real aplicada via writer a partir do seed local de homologacao, sem
    publicar valores privados. A config ativa preservou
    `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`.
  - Player pos-config:
    - processo MPV em `/opt/totem/hwdecode/bin/mpv`;
    - `hwdec-current=v4l2request-copy`;
    - `media_load_failed=0`;
    - `NRestarts=0`;
    - sem erros panfrost na amostra curta.
  - OTA local de `totem-core` validado na placa com pacote gerado do commit
    `e56fddb`: apply, rollback e reapply passaram; o player permaneceu ativo e
    com HW decode apos cada etapa.
  - Release GitHub de homologacao publicada e validada end-to-end:
    `totem-core-c18.ota-core-1i-github-smoke-20260603T012036Z-09ba8d1`.
    - Manifest: `component=totem-core`, `channel=homologation`,
      `source_commit=09ba8d15154b15ff83569ce0acbab50258121366`,
      `source_dirty=false`.
    - Payload SHA256:
      `e57dd720d21e429fae8271a153913ee96db5c0576e38df97be74f94a8a436254`.
    - Dry-run na placa selecionou exatamente essa release e retornou
      `state_changed=false`.
    - Apply GitHub, rollback e reapply GitHub passaram; ao final a placa ficou
      em `current=c18.ota-core-1i-github-smoke-20260603T012036Z-09ba8d1` e
      `previous=c17.5-core-mvp-20260602-231123-e56fddb`.
    - O player permaneceu `active`, `NRestarts=0`, MPV em
      `/opt/totem/hwdecode/bin/mpv`, `hwdec-current=v4l2request-copy`,
      `media_load_failed=0`, sem erros panfrost/mmc na janela de validacao.
  - Tentativa de OTA de `kiosky-player` continuou bloqueada com
    `rc=44` (`component_frozen_for_ota`).
- Build offline subsequente gerou `c18-hwdecode-lab-1j`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1j_minimal.img`
  - `sha256=995d0a90e6449f8f8e8e58f788fb38ba9196dacb4312cb28ecbd6041cda1c152`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Delta sobre `1i`: `totem-kiosky-launcher.sh` tambem e arquivo fixo de
    imagem/player-runtime, fora do payload `totem-core`; o default do launcher
    agora usa `/data/player-runtime/current`, e o caminho legado
    `/data/apps/kiosky-player/current` nao sombreia mais o player validado.
  - Contrato de fronteira validado offline:
    `image_fixed_player_kiosky_service_launcher.sh_not_totem_core_wrapper=true`,
    `image_fixed_player_totem-kiosky-launcher.sh_not_totem_core_wrapper=true`,
    `totem_core_release_excludes_kiosky_service_launcher.sh=true` e
    `totem_core_release_excludes_totem-kiosky-launcher.sh=true`.
  - Validada em hardware como flash limpo:
    - marker `c18-hwdecode-lab-1j` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `totem-kiosky-launcher.sh` fixo na imagem, usando
      `/data/player-runtime/current` e sem default para
      `/data/apps/kiosky-player/current`;
    - `/data/player-runtime/current` ausente e
      `/data/apps/kiosky-player/current` ausente, portanto player usa fallback
      validado da imagem;
    - config real escrita via writer guardado a partir do seed local de
      homologacao, sem publicar valores privados; config ativa ficou
      `0640 root:totem` e preservou
      `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`;
    - player pos-config em playback `playing`, IPC ativo,
      `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`;
    - deep-health de playback passou em hardware:
      `hwdec_no_unexpected=true`, `media_load_failed_zero=true`,
      `panfrost_faults_zero=true`, `mmc_timeout_reset_zero=true`,
      `single_mpv=true`, `playback_progressed=true`,
      `transitions_observed_when_required=true`;
    - probes temporarios de deep-health foram removidos da placa apos a coleta.
  - Contrato OTA pos-flash:
    - `apply-local --component kiosky-player` bloqueado com `rc=44`;
    - `apply-local --component player-runtime` bloqueado com `rc=44`;
    - antes da nova publicacao, `apply-github-latest --component totem-core
      --dry-run` retornou `rc=0` e selecionou a release de homologacao 1i, sem
      aplicar mudanca.
- Release GitHub de homologacao publicada a partir do HEAD `1e040c0` e validada
  end-to-end na placa `1j`:
  `totem-core-c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`.
  - Manifest: `component=totem-core`, `channel=homologation`,
    `source_branch=foundation-v0.1`,
    `source_commit=1e040c0672d08606717b8048313194afc50d8c86`,
    `source_dirty=false`.
  - Payload SHA256:
    `d3073d2e3756b9ae102be216831ad3b6b363ba7d7b580e852e46d7d4f7c92856`.
  - Gate de release passou com o pacote antes da publicacao; a release foi
    publicada como prerelease e a tag aponta para o `source_commit`.
  - Dry-run na placa selecionou exatamente essa release e retornou
    `state_changed=false`.
  - Apply GitHub passou: `current` virou
    `c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`, `previous` ficou
    `c17.6-environment-input-20260514T211247Z`, player permaneceu `playing`,
    `hwdec-current=v4l2request-copy`, `NRestarts=0`, `media_load_failed=0`.
  - Rollback passou para o embed C17.6; `previous` virou a release 1j, player
    permaneceu `playing`, `hwdec-current=v4l2request-copy`, `NRestarts=0`,
    `media_load_failed=0`.
  - Reapply GitHub passou; ao final a placa ficou em `current` na release 1j e
    `previous` no embed C17.6, com player `playing`,
    `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`,
    `media_load_failed=0`.
- Release GitHub de homologacao com mudanca funcional pequena de `totem-core`
  publicada a partir do HEAD `2a7a327` e validada end-to-end na placa `1j`:
  `totem-core-c18.ota-core-config-missing-20260603T150429Z-2a7a327`.
  - Escopo: somente status preview publico de `config_missing` em
    `totem_status_render_preview.py`, com self-test novo no pacote/gate. Nao
    toca player, launchers, MPV/hwdecode, updater, units, policy, Wi-Fi real ou
    field-data.
  - Manifest: `component=totem-core`, `channel=homologation`,
    `source_branch=foundation-v0.1`,
    `source_commit=2a7a3272cd49a2e0742d2a4ad070de588771877d`,
    `source_dirty=false`.
  - Payload SHA256:
    `908bb4dc38e2b19f94cdf1f9cdacbaa6e7f2a5d546e21747882bc93d5eed9d4d`.
  - Gate de release passou com o pacote antes da publicacao; a release foi
    publicada como prerelease e a tag aponta para o `source_commit`.
  - Dry-run na placa selecionou exatamente essa release e retornou
    `state_changed=false`.
  - Apply GitHub passou: `current` virou
    `c18.ota-core-config-missing-20260603T150429Z-2a7a327`, `previous` ficou
    `c18.ota-core-1j-github-smoke-20260603T142540Z-1e040c0`;
    o arquivo ativo em `/data/core/totem/current/bin` continha a nova copia
    publica de `config_missing`, `totem_status_render_preview.py --self-test`
    passou, player permaneceu `active`, `hwdec-current=v4l2request-copy`,
    `vo-configured=true`, `NRestarts=0`.
  - Rollback passou para a release 1j; a copia nova saiu do slot `current`,
    player permaneceu `active`, `hwdec-current=v4l2request-copy`,
    `vo-configured=true`, `NRestarts=0`.
  - Reapply GitHub passou; ao final a placa ficou em `current` na release
    `c18.ota-core-config-missing-20260603T150429Z-2a7a327` e `previous` na
    release 1j, timer `disabled/inactive`, player `active`,
    `hwdec-current=v4l2request-copy`, `vo-configured=true`, `NRestarts=0`.
  - Tentativas de apply de `kiosky-player` e `player-runtime` continuaram
    bloqueadas com `rc=44`.
- Build offline subsequente gerou `c18-hwdecode-lab-1k` como candidata da
  fundacao de thaw seguro do `player-runtime`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1k_minimal.img`
  - `sha256=d0aae1e0dc234be1d9071b7f88d913b1dfb0f89d980904e9c2dc9291e648ac5e`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`;
    `player_runtime_release_gate_passed=true`;
    `player_runtime_sandbox_passed=true`.
  - Delta sobre `1j`: imagem inclui launcher com marker `.release_verified.json`
    sha-bound, `kiosk_py_sha256`, `tree_sha256`, `deep_health.passed`,
    quarentena, fallback fail-closed para `/opt`, reconcile/state hygiene,
    lab-thaw guard e primitivas verify-then-promote para homologacao futura.
  - Checks offline adicionais: service `kiosky-player` roteado pelo
    `totem-kiosky-launcher.sh`; sem `/data/player-runtime/current`; sem
    `/data/apps/kiosky-player/current`; sem marker pre-forjado em `/data`;
    `player-runtime` e `kiosky-player` continuam congelados no fluxo publico
    (`rc=44`).
  - Validada em hardware como flash limpo em 2026-06-03:
    - marker `c18-hwdecode-lab-1k` presente;
    - policy presente e restrita a `totem-core`;
    - `totem-update-agent.timer` `disabled`/`inactive`;
    - service de update apontando para
      `--component totem-core --repo dadoohai/orange_pi_totem`;
    - `kiosky-player.service` roteado por `totem-kiosky-launcher.sh`;
    - `/data/player-runtime/current` e `/data/apps/kiosky-player/current`
      ausentes; player usa fallback validado da imagem;
    - config real escrita via writer guardado a partir do seed local de
      homologacao, sem publicar valores privados; config ativa ficou
      `0640 root:totem` e preservou
      `mpv_path=/opt/totem/bin/totem-mpv-hwdecode`;
    - player pos-config em playback `playing`, playlist com 9 itens,
      `hwdec-current=v4l2request-copy`, `vo-configured=true`,
      `video-codec=H.264`, `NRestarts=0`;
    - contadores da janela: `media_load_failed=0`, `mpv_restart=0`,
      panfrost fault real `0`, `mmc_timeout/reset=0`, erros EXT4/IO `0`;
    - `apply-github-latest`/rollback/reapply de `totem-core` passaram na placa;
      ao final `current=c18.ota-core-config-missing-20260603T150429Z-2a7a327`
      e `previous=c17.6-environment-input-20260514T211247Z`;
    - tentativas de apply de `kiosky-player` e `player-runtime` continuaram
      bloqueadas com `rc=44`.

## Continuidade pos-compactacao

1. Tratar `c18-hwdecode-lab-1l` como baseline de laboratorio validada para a
   frente OTA/manual, ainda `final_image=false`.
2. Fluxo manual de release GitHub `totem-core` validado na 1l com mudanca real
   de aplicacao, rollback e reapply. Proximas mudancas de wizard/core devem
   seguir este gate antes de aplicar em placa, mantendo auto-pull desligado e
   `kiosky-player`/`player-runtime` congelados ate thaw explicito.
3. Proxima frente da jornada de delivery: preparar a liberacao controlada de
   `player-runtime` sem descongelar producao. Frentes de display, Wi-Fi aberta,
   cursor/UX de wizard e acesso de manutencao ficam adiadas ate o delivery estar
   pleno.

## Marco 2026-06-03 — Fundacao De Thaw Seguro Do Player-Runtime

- O `player-runtime` continua congelado no CLI publico (`rc=44`), mas o repo
  agora contem primitivas reais e testaveis para um thaw futuro de laboratorio:
  verify-then-promote, marker `.release_verified.json` sha-bound, fallback
  fail-closed para `/opt`, quarentena por identidade de conteudo e rollback
  interno de `player-runtime`.
- O launcher de player nao adota mais `/data/player-runtime/current` apenas por
  existir `kiosk.py`: ele recomputa `kiosk_py_sha256` e `tree_sha256`, valida o
  marker escrito pelo updater e recusa identidade quarentenada. Qualquer duvida
  volta para `/opt/totem/kiosky-player`.
- O gate de `player-runtime` passou a rejeitar `hwdec="no"`, `mpv_path`
  inseguro, args MPV perigosos literais dentro de `build_mpv_args`
  (`--script`, config externo, YTDL, IPC/hwdec hard-coded inseguro), marker
  pre-forjado, paths de controle/imagem e payload SHA adulterado.
- O sandbox de `player-runtime` deixou de provar uma copia da mecanica e passou
  a chamar as primitivas reais do updater com health hook injetavel. Ele valida:
  apply A/B, rollback roundtrip, marker corrompido -> `/opt`, health que observa
  fallback rejeitado, falha com previous e sem previous, hygiene/reconcile de
  `state.json`, `/data` sem marker caindo para `/opt`, e freeze preservado.
- O boot adoption seguro fica no launcher: ele valida marker/hash/quarentena no
  momento de escolher `/data` ou `/opt`. O `reconcile` do updater e higiene
  explicita para state/symlink drift, nao a barreira primaria de boot.
- Ja existe builder local lab-only de `player-runtime`
  (`scripts/deploy/build_player_runtime_release_package.sh`) e collector real
  nao destrutivo (`scripts/board/c18_playback_health_collect.py`). Ainda nao ha
  publisher, thaw em hardware nem health hook de candidato isolado. O sandbox
  prova fluxo/estado com health hook injetavel; nao prova decode real de uma
  release candidata em hardware nem durabilidade sob corte de energia. Esses sao
  os proximos gates antes de qualquer release real de player.
- Auditoria adversarial pos-1k confirmou dividas pre-thaw que **nao afetam a
  golden enquanto `rc=44` estiver ativo**, mas bloqueiam qualquer thaw real:
  validar os args efetivos entregues ao `Popen` (nao so strings literais em
  `build_mpv_args`), impedir mutacao de `cfg["hwdec"]`/`args` fora do caminho
  controlado, ligar `reconcile` em boot ou documentar formalmente o launcher
  como reconcile primario, e fazer o deriver abortar/limpar artefato se a
  validacao offline falhar.
- Rodada repo-side pos-1k fechou essas tres dividas imediatas sem descongelar o
  componente: o gate de `player-runtime` agora valida o caminho efetivo
  `build_mpv_args -> subprocess.Popen(args, ...)` e cobre bypasses de args/cfg;
  o drop-in do player executa `reconcile --component player-runtime` como
  `ExecStartPre=-...` nao-fatal; e o deriver constroi em arquivo temporario,
  promovendo `.img/.sha256` final apenas depois de `offline_ok`. Por mudar
  conteudo de imagem, a proxima candidata passa a ser `c18-hwdecode-lab-1l`; a
  `1k` permanece golden validada.
- Build offline da candidata `c18-hwdecode-lab-1l` passou:
  `OFFLINE_VALIDATION_PASSED=True`, `artifact_promoted=true`,
  `sha256=146b430972b61523cf943f467b94ccf56697843a48147ec5b1839db3583b1ad3`.
  Validacao em hardware como flash limpo tambem passou: marker `1l`, drop-in
  com `reconcile` efetivo, policy restrita a `totem-core`, timer desligado,
  config real escrita pelo writer, playback em HW decode
  `v4l2request-copy`, `media_load_failed=0`, `mpv_restart=0`, faults
  panfrost/mmc/ext4 `0`, OTA GitHub `totem-core`
  dry-run/apply/rollback/reapply aprovado, e `kiosky-player`/`player-runtime`
  ainda bloqueados com `rc=44`. A `1l` substitui a `1k` como golden atual de
  laboratorio/delivery.
- Rodada seguinte de entrega adicionou e validou em hardware o collector
  nao-destrutivo de deep-health sobre a `1l`, sem alterar servico/config:
  janela curta de 45s com `45/45` amostras IPC bem-sucedidas,
  `hwdec-current=v4l2request-copy`, `vo-configured=true`, 3 aliases observados,
  `NRestarts_delta=0`, `media_load_failed=0`, `mpv_restart=0`,
  panfrost/mmc/ext4 `0`, servico ainda `active` apos a coleta. Tambem adicionou
  limpeza de release candidata rejeitada no fluxo interno de `player-runtime`,
  guard contra sobrescrever releases ja ligadas como `current`/`previous`, e
  builder local lab-only de pacote `player-runtime` que so promove artefatos
  apos o gate passar, mantendo o CLI publico congelado com `rc=44`.
- Rodada de governanca seguinte manteve o foco em velocidade segura: o gate
  C18 ganhou `--base-ref` para pegar mudanca commitada em paths
  `player-runtime`/image-fixed, `stable` passou a falhar fechado sem evidencia
  de promocao aprovada, o publisher de `totem-core` preserva
  `c18-ota-release-gate.json` como evidencia, o builder/gate de
  `player-runtime` rejeitam canal `stable`, e o sandbox de `player-runtime`
  agora aceita um pacote real gerado pelo builder alem dos pacotes sinteticos.
  Auditoria subsequente fechou dois pontos load-bearing desse publish: o
  publisher agora exige `--base-ref`/`C18_OTA_BASE_REF` em vez de tratar como
  recomendacao, e compara o SHA da evidencia stable publicada com
  `stable_promotion_evidence_sha256` declarado no manifest.

## Fora de escopo

- Ligar auto-pull.
- OTA de `kiosky-player`/MPV/hwdecode.
- Soak 24h.
- Rotação 270.
- Read-only/C12.
- Kernel/U-Boot/DTB/BSP, pacotes NetworkManager e `apt upgrade`.
