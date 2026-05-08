# C12.3.15 - Initramfs Overlay Load Failure

Data: 2026-05-08

## Objetivo

Classificar por que o modulo `overlay` real, presente no `initramfs/uInitrd` e
nao vazio, ainda nao carrega nem registra `overlay` no runtime do initramfs.

Nao houve uso da dev, da placa teste antiga, writer, config real,
Wi-Fi/NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Runner

Foi criado:

```text
scripts/remote/run_c12_3_15_initramfs_overlay_load_failure.sh
```

Modos principais:

- `--prepare-only`;
- `--inspect`;
- `--install-load-diagnostic-hook`;
- `--reboot-check`;
- `--collect-diagnostic`;
- `--rollback`;
- `--summary`.

O hook exigiu a confirmacao:

```text
CONFIRMO DIAGNOSTICO LOAD OVERLAY C12.3.15
```

O reboot exigiu a confirmacao:

```text
CONFIRMO REBOOT DIAGNOSTICO LOAD OVERLAY C12.3.15
```

## Inspect Antes de Alterar

Estado sanitizado antes do hook:

- `read_only_enabled=false`;
- `overlay_active=false`;
- root `ext4`;
- `overlay.ko` real presente no rootfs;
- `overlay.ko` presente e nao vazio no `initrd/uInitrd`;
- `modules.dep` referencia `overlay` no artefato inspecionado;
- `vermagic_match=true` no ambiente pos-boot;
- dependencias declaradas: nenhuma;
- assinatura/signature: ausente;
- `overlay` aparece em `/proc/filesystems` depois do boot normal.

## Diagnostico no Initramfs

O hook temporario foi instalado no initramfs, o `uInitrd` foi regenerado e a
placa passou por um reboot controlado. SSH voltou.

Resultado do hook:

- `proc_mounted=true`;
- `overlay_ko_exists=true`;
- `overlay_ko_nonempty=true`;
- `overlay_ko_file_type=plain_ko`;
- `module_path_kernel_matches=true`;
- `modprobe_overlay_exit=zero`;
- `overlay_in_proc_after_modprobe=false`;
- `insmod_overlay_exit=nonzero`;
- `insmod_error_category=unknown`;
- `dmesg_category=no_message`;
- `overlay_in_proc_after_insmod=false`;
- `mount_overlay_attempted=false`.

O estado apos boot continuou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root `ext4`;
- `/data`, `/tmp` e `/run` gravaveis;
- `public_state=config_missing`;
- `systemctl_failed_count=0`.

## Rollback

Depois da coleta:

- `rollback_executed=true`;
- `diagnostic_hook_present_after=false`;
- `update_initramfs_exit_code_bucket=zero`;
- `uinitrd_regenerated=true`.

## Classificacao

A linha de investigacao de empacotamento foi encerrada: o modulo nao esta mais
vazio nem ausente no artefato. Mesmo assim, no runtime do initramfs:

- `modprobe overlay` retorna sucesso, mas nao registra `overlay`;
- `insmod overlay.ko` falha;
- nao ha categoria mais especifica em stderr/dmesg;
- o teste de mount overlay nao pode ser tentado porque o filesystem nao aparece.

Classificacao principal:

```text
INITRAMFS_MODULE_LOADING_UNSUPPORTED
```

Essa categoria indica que o caminho `overlayroot` via modulo carregado no
initramfs nao deve receber outra tentativa incremental sem decisao de mecanismo.

## Decisao

Nao iniciar C12.4.

Nao iniciar C12.1.11 como rebuild simples de empacotamento/dependencias. O
proximo passo deve reabrir a decisao do mecanismo read-only:

```text
ADR_UPDATE_READONLY_MECHANISM_DECISION
```

Opcoes a avaliar:

- kernel/base com overlay built-in;
- mecanismo read-only alternativo aprovado;
- nova base Armbian/kernel onde `overlay` registre corretamente no initramfs;
- manter root read-only bloqueado nesta linha.

## Status

- `read_only_validated=false`;
- `ready_for_c12_4=false`;
- `ready_for_c12_1_11_rebuild=false`;
- `read_only_overlayroot_path_blocked=true`;
- `next_decision_required=true`.

## Atualizacao C12.3.16

A decisao posterior foi registrada na ADR-0012:

- a linha `overlayroot` via `overlay.ko` carregado como modulo no initramfs esta
  encerrada;
- `overlayroot` continua sendo o mecanismo esperado;
- o proximo experimento e imagem-lab com `CONFIG_OVERLAY_FS=y`, ou seja,
  overlayfs built-in no kernel;
- C12.4 continua bloqueado ate boot real provar a semantica read-only correta.

Tambem foi corrigido o criterio de sucesso: com `overlayroot`, o root aparente
pode ser gravavel por overlay volatil. O teste correto e provar root montado
como overlay, escrita fora de `/data` nao persistente apos reboot, e escrita em
`/data` persistente.
