# C12.3.10 - Boot Validate C12.1.9

Data: 2026-05-08

## Objetivo

Validar em boot real se a imagem-lab C12.1.9 ativa root read-only/overlay.

Nao houve uso da dev, da placa teste antiga, wizard, writer, config real,
alteracao de Wi-Fi/NetworkManager, instalacao de pacotes, reboot, poweroff ou
corte seco.

## SHA Confirmado

O SHA real da imagem C12.1.9 foi confirmado pelo arquivo local, pelo `.sha256`,
manifest e evidencia:

```text
f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c
```

## Boot

A placa lab bootou a imagem C12.1.9:

- `image_version_confirmed=true`;
- `ssh_available=true`;
- `firstboot_lab_complete=true`;
- `public_state=config_missing`;
- `config_real_present=false`;
- `config_missing_visual_ok=true`.

O estado `config_missing` continua esperado para image-lab sem config privada do
player.

## Read-only

O objetivo principal nao passou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- `root_fstype=ext4`;
- `/data writable=true`;
- `/tmp writable=true`;
- `/run writable=true`;
- `journald_volatile=true`.

C12.4 permanece bloqueado.

## Diagnostico

A correcao C12.1.9 entrou no boot:

- `overlayroot=tmpfs` chegou ao cmdline;
- o boot script usa `uInitrd`;
- `uInitrd` foi inspecionado;
- o hook `overlayroot` esta presente;
- o hook Dadooh de carga de `overlay` esta presente;
- `overlay_module_present_in_initramfs=true`;
- `overlay_module_effective_path_present=true`;
- `modules_dep_references_overlay=true`;
- `modprobe overlay` retornou zero;
- fallback `insmod` foi tentado.

A falha atual e mais especifica:

```text
INSMOD_FALLBACK_FAILED
```

O hook encontrou o caminho efetivo do modulo, mas `insmod` retornou nonzero no
runtime do initramfs. Depois do boot normal, `overlay` aparece em
`/proc/filesystems`, indicando que o driver fica disponivel tarde demais para o
`overlayroot`.

## Proximo Passo

```text
C12.3.11_INITRAMFS_INSMOD_FAILURE_DIAGNOSTICS
```

A proxima rodada deve diagnosticar por categoria por que o `insmod` falha no
initramfs, sem logs brutos. Exemplos de categorias esperadas:

- dependencia de modulo ausente;
- simbolo/kernel mismatch;
- parametro/fase initramfs inadequada;
- modulo comprimido/formato nao carregavel naquele estagio;
- outro erro de compatibilidade do kernel/initramfs.

## Status

- `ready_for_c12_4=false`;
- `read_only_validated=false`;
- `c12_4_blocked=true`;
- `next_step=C12.3.11_INITRAMFS_INSMOD_FAILURE_DIAGNOSTICS`.

## Atualizacao C12.3.11

C12.3.11 instalou hook temporario de diagnostico no initramfs com backup,
reboot controlado e rollback. A classificacao foi refinada de
`INSMOD_FALLBACK_FAILED` para:

```text
OVERLAY_MODULE_PATH_MISMATCH
```

No runtime do initramfs, o hook nao conseguiu resolver `overlay.ko` no caminho
efetivo, entao `insmod` nao chegou a executar nesta coleta. O proximo passo e
`C12_1_10_REBUILD_WITH_EFFECTIVE_MODULE_PATH`. C12.4 continua bloqueado.
