# 189 — C18.OTA-READINESS-GATE

Rodada de proteção do OTA C18. Objetivo: permitir evolução rápida do wizard/core
sem criar um caminho acidental para regredir o playback/hwdecode validado na
baseline `1d`.

## Decisão

- OTA C18 imediato = `totem-core` **manual/operator-triggered**.
- `kiosky-player`, MPV e `/opt/totem/hwdecode` ficam **congelados fora do OTA**.
- Imagem C18 nova deve nascer com `/data/updates/policy.json` restritivo:
  `allowed_components=["totem-core"]`, `allow_downgrade=false`.
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
  regra conservadora de downgrade e limpa staging em `incoming`.

## Gates

- Testes estáticos de policy/service/timer.
- Testes unitários de freeze, downgrade e GC de staging.
- Sandbox `totem-core` apply/rollback/settings-lock.
- Validação offline da imagem `1e` deve comprovar policy presente, timer
  desligado e service apontando para `totem-core`.

## Estado live da 1e (2026-06-02)

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

## Continuidade pos-compactacao

1. Revisar o diff OTA `1e` como um lote unico e manter fora do stage o WIP
   alheio `scripts/qa/generate_ui_ux_gallery.py`.
2. Rodar novamente os gates antes de commit:
   `py_compile`, `c18_ota_policy_static_test.py`,
   `c18_updatectl_freeze_downgrade_gc_test.py`,
   `c17_9_update_channel_policy_test.py`,
   `c18_runtime_3_release_perms_test.py`,
   `run_totem_core_sandbox.py --json`, `git diff --check`.
3. Se o diff continuar limpo, commitar a frente como C18 OTA readiness/1e.
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
