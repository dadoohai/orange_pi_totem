# C12.3.13 - Insmod And Black Screen Triage

Data: 2026-05-08

## Objetivo

Classificar dois bloqueios da image-lab C12.1.10:

- por que `insmod overlay` retorna erro no initramfs;
- por que `config_missing` fica com HDMI preto mesmo com SVG valido, renderer
  ativo e MPV ativo.

Nao houve uso da dev, da placa teste antiga, writer, config real,
Wi-Fi/NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Metodo

Foi criado o runner:

```text
scripts/remote/run_c12_3_13_insmod_and_black_screen_triage.sh
```

Modos usados:

- `--prepare-only`;
- `--inspect-current`;
- `--triage-config-missing-visual`;
- `--install-insmod-diagnostic-hook`, com confirmacao explicita;
- `--reboot-insmod-diagnostic`, com confirmacao explicita;
- `--rollback-diagnostic-hook`.

O hook temporario registrou apenas categorias sanitizadas. Nao foram publicados
stderr bruto, dmesg bruto, secrets, config real, SSID, senha ou dados de rede.

## Resultado Read-only

O boot continua sem read-only:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continua `ext4`;
- `/data`, `/tmp` e `/run` continuam gravaveis.

O hook dinamico da C12.1.10 chegou a resolver um caminho para `overlay.ko`, mas
o diagnostico C12.3.13 mostrou:

- `overlay_ko_path_resolved=true`;
- `overlay_ko_file_type=plain_ko`;
- `overlay_ko_size_bucket=empty`;
- `modules_dep_exists=true`;
- `modules_dep_references_overlay=false`;
- `modprobe_overlay_rc=zero`;
- `overlay_in_proc_after_modprobe=false`;
- `insmod_overlay_attempted=true`;
- `insmod_overlay_rc=nonzero`;
- `insmod_error_category=unknown`;
- `dmesg_category=no_message`.

Classificacao acionavel:

```text
OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS
```

O runner preservou tambem a categoria generica `OVERLAY_INSMOD_OTHER`, porque
nao houve stderr/dmesg sanitizavel mais especifico. A interpretacao de produto
e mais precisa: o artefato resolvido no initramfs esta vazio e `modules.dep` nao
o referencia.

## Resultado Visual

Triagem visual sem screenshot:

- `public_state=config_missing`;
- `status.svg` existe;
- `status.svg` e valido;
- `status.svg` contem texto visivel;
- `renderer_process_count=1`;
- `MPV_process_count=1`;
- `drm_status_category=connected_present`;
- `mpv_vo_context_category=gpu`;
- `getty_visible_active=false`.

Classificacao:

```text
SVG_VALID_BUT_NOT_PRESENTED_BY_MPV
```

Isso substitui a classificacao mais ampla C12.3.12
`CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE`.

Atualizacao humana posterior: a tela preta foi causada por problema de hardware
da tela e foi resolvida fora do software do produto. Portanto, a classificacao
visual acima fica apenas como evidencia do estado observado antes da correcao
fisica e nao abre uma frente obrigatoria de patch visual.

## Rollback

Depois da coleta:

- `rollback_executed=true`;
- `diagnostic_hook_present_after=false`;
- `update_initramfs_ok=true`;
- `uinitrd_regenerated=true`;
- `uinitrd_nonempty_after=true`.

## Proximos Passos

Read-only:

```text
C12.1.11_REBUILD_WITH_NONEMPTY_OVERLAY_MODULE_AND_COHERENT_MODULES_DEP
```

O build deve provar offline que o `overlay.ko` efetivo no initramfs nao esta
vazio e que `modules.dep` referencia `overlay` no mesmo layout que o boot usa.

Visual:

```text
HARDWARE_DISPLAY_ISSUE_RESOLVED
```

Sem proxima acao de produto obrigatoria para a tela preta nesta rodada.

## Status

- `ready_for_c12_4=false`;
- `read_only_validated=false`;
- `c12_4_blocked=true`.
