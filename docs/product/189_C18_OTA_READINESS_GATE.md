# 189 — C18.OTA-READINESS-GATE

Rodada de proteção do OTA C18. Objetivo: permitir evolução rápida do wizard/core
sem criar um caminho acidental para regredir o playback/hwdecode validado na
baseline `1d`.

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
- Validação offline da próxima imagem (`1g`) deve comprovar policy presente, timer
  desligado e service apontando para `totem-core`.

## Contrato futuro de OTA

Toda release C18 nova de `totem-core` deve declarar no manifest:

- `requires.base_image_min="c17.4.2"` para esta linha;
- `requires.device_track="c18-hwdecode"`;
- `requires.updater_features` contendo `c18-freeze-kiosky-player-v1`,
  `c18-rollback-reapply-v1`, `c18-safe-payload-v1` e `c18-track-v1`.

Updater `1g+` que nao encontrar esses campos, nao entender uma chave nova em
`requires`, encontrar track diferente, base incompatível, feature ausente ou
feature desconhecida deve rejeitar a release. Se uma mudanca futura precisar
novo updater, nova unit, novo pacote do sistema, player/MPV/hwdecode ou reboot
para se tornar verdadeira, ela nao pertence ao OTA normal de `totem-core`; deve
vir como nova imagem ou release ponte explicitamente homologada.

## Estado live da 1e + OTA smoke (2026-06-02)

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
- Build offline subsequente gerou `c18-hwdecode-lab-1g`.
  - Arquivo:
    `/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c18-hwdecode-lab-1g_minimal.img`
  - `sha256=e6c59038f6141454261e8313ef9dc028782fec13ffcbf42331a23464548defa1`
  - Tamanho: `1971322880` bytes.
  - `OFFLINE_VALIDATION_PASSED=True`; `totem_core_ota_ready=true`; policy
    presente; timer desligado; service apontando para `totem-core`; sem config
    real embutida.
  - Ainda nao foi validada em hardware como flash limpo.

## Continuidade pos-compactacao

1. Revisar o diff OTA `1g` como um lote unico e manter fora do stage o WIP
   alheio `scripts/qa/generate_ui_ux_gallery.py`.
2. Rodar novamente os gates antes de commit:
   `PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json`.
3. Se o diff continuar limpo, commitar a frente como C18 OTA readiness/1g.
4. Proxima frente funcional do projeto: fluxo OTA manual de `totem-core`
   (publicacao/seleção/aplicacao controlada do wizard/core), mantendo auto-pull
   desligado e `kiosky-player` congelado.
5. Depois disso, abrir as frentes separadas: compatibilidade HDMI/resolucao por
   display e melhorias do wizard (cursor, rede aberta, UX de entrada).

## Fora de escopo

- Ligar auto-pull.
- OTA de `kiosky-player`/MPV/hwdecode.
- Soak 24h.
- Rotação 270.
- Read-only/C12.
- Kernel/U-Boot/DTB/BSP, pacotes NetworkManager e `apt upgrade`.
