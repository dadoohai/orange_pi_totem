# C12.1.7 - Overlayroot Activation Diagnose

Data: 2026-05-07

## Objetivo

Diagnosticar por que a imagem-lab C12.1.6 contem `overlayroot` configurado,
mas o boot real ainda monta root como `ext4 rw`.

Esta rodada foi somente diagnostica:

- nao alterou a placa;
- nao remountou root;
- nao reiniciou;
- nao chamou writer;
- nao alterou config real;
- nao alterou Wi-Fi/NetworkManager;
- nao publicou logs brutos nem secrets.

## Sistema Bootado

A placa com a imagem C12.1.6 permaneceu acessivel por SSH e em estado de
produto esperado para imagem sem config real:

- `public_state=config_missing`;
- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `session.lock=false`;
- `request=false`;
- `systemctl_failed_count=1`, categorizado como `console_setup`.

Read-only continuou inativo:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_fstype=ext4`;
- `root_write_blocked=false`;
- `/data`, `/tmp` e `/run` gravaveis por politica.

## Achado Principal

A inspecao offline da imagem C12.1.6 mostrou:

- `/etc/overlayroot.conf` esta presente e efetivo como `overlayroot="tmpfs"`;
- o pacote `overlayroot` esta listado;
- `/boot/initrd.img-6.12.58-current-sunxi64` existe;
- esse `initrd.img` contem `scripts/init-bottom/overlayroot`;
- esse `initrd.img` contem modulo `overlay`;
- o boot script carrega `/boot/uInitrd`;
- `/boot/uInitrd` no artefato da imagem esta vazio.

Na placa ja bootada, `/boot/uInitrd` aparece nao vazio, mas isso nao prova que
ele estava valido no primeiro boot. O estado atual mostra que o primeiro boot
nao ativou overlayroot.

## Classificacao

```text
UINITRD_NOT_UPDATED
```

Interpretacao: o build gerou ou preservou `initrd.img` com overlayroot, mas nao
entregou um `uInitrd` valido antes do primeiro boot, embora o boot script use
`uInitrd`.

## Fix Recomendado

C12.1.8 deve reconstruir a imagem-lab garantindo uma destas saidas:

- gerar `/boot/uInitrd` nao vazio a partir do initramfs que contem overlayroot;
- ou ajustar de forma controlada o boot para usar o initramfs correto;
- e endurecer a validacao offline para falhar se `boot_uses_uinitrd=true` e
  `uInitrd` estiver ausente/vazio.

A validacao C12.1.8 deve provar no artefato:

- `uinitrd_size_category=nonempty`;
- `uinitrd_contains_overlayroot=true`, se tecnicamente inspecionavel;
- `boot_uses_uinitrd=true`;
- `overlayroot_config_present=true`;
- `initrd_img_contains_overlayroot=true`.

Depois disso, uma nova gravacao/boot deve validar:

- `read_only_enabled=true`;
- `overlay_active=true`;
- `root_write_blocked=true`;
- `/data`, `/tmp` e `/run` gravaveis;
- `config_missing` visual sem shell;
- F10 abre/cancela sem deixar lock.

## Decisao

C12.4 continua bloqueado. O proximo passo correto e:

```text
C12.1.8 - rebuild image-lab com uInitrd valido para overlayroot
```

## Atualizacao C12.1.8

C12.1.8 implementou o rebuild recomendado. A validacao offline foi endurecida
para seguir o symlink `/boot/uInitrd`, extrair o payload U-Boot com
`dumpimage`, comparar esse payload com `initrd.img` e verificar que ambos
contem:

- hook `scripts/init-bottom/overlayroot`;
- modulo `overlay`;
- marker seguro `etc/dadooh/c12-overlayroot-initramfs-marker`.

Resultado do artefato C12.1.8:

- `uinitrd_nonempty=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `uinitrd_generated_after_overlayroot=true`;
- `uinitrd_generated_after_initrd_img=true`;
- `effective_boot_initramfs_valid=true`.

C12.4 segue bloqueado ate a nova imagem ser gravada e validada em placa.
