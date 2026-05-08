# C12.1.9 - Rebuild Image-Lab Overlay Module Path

Data: 2026-05-08

## Objetivo

Reconstruir a imagem-lab com `overlay.ko` resolvivel no initramfs/uInitrd
efetivo, corrigindo a causa C12.3.9:

```text
OVERLAY_MODULE_PATH_INVALID
```

Nenhuma placa foi tocada, nenhum cartao foi gravado, nenhum writer foi chamado
e nenhum secret foi publicado.

## Correcao

O build C12 agora garante:

- `overlayroot=tmpfs` nos argumentos de boot da imagem-lab;
- hook `init-top` Dadooh para tentar `modprobe overlay`;
- fallback por `insmod` usando `/lib/modules/<kernel>/kernel/fs/overlayfs`;
- marker seguro de caminho de modulo no initramfs;
- validacao offline do `uInitrd` efetivo, nao apenas do rootfs.

O initramfs da base e usr-merged:

```text
/lib -> usr/lib
```

Por isso a validacao C12.1.9 considera o caminho efetivo resolvido por symlink:
`/lib/modules/...` e valido quando `lib` aponta para `usr/lib` e o modulo esta
presente em `usr/lib/modules/...`.

## Artefato

Imagem C12.1.9:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-9_minimal.img
```

SHA256:

```text
f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c
```

Build log:

```text
/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-818fa15d-f012-40ea-bf17-0a66f10f15be.log
```

## Validacao Offline

Validado nos artefatos:

- `overlayroot_included=true`;
- `initramfs_generated_after_overlayroot=true`;
- `initrd_contains_overlayroot_hook=true`;
- `uinitrd_contains_overlayroot_hook=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `overlay_module_effective_path_present=true`;
- `modules_dep_effective_path_present=true`;
- `modules_dep_references_overlay=true`;
- `modprobe_present_in_initramfs=true`;
- `insmod_present_in_initramfs=true`;
- `overlay_load_hook_uses_effective_path=true`;
- `effective_boot_initramfs_overlay_resolvable=true`;
- `effective_boot_initramfs_valid=true`;
- `rootfs_firstboot_autoconfig_proven=true`;
- `rootfs_ready_for_card_write=true`.

O runner de validacao retornou:

```text
c12_1_image_lab_artifacts=ok
```

## Guardrails

- placas tocadas: `false`;
- cartao gravado: `false`;
- config real embutida: `false`;
- writer chamado: `false`;
- Wi-Fi/NetworkManager de placa alterado: `false`;
- imagem final de producao: `false`;
- secrets publicados: `false`.

## Proximo Passo

C12.2.5 pode gravar a imagem C12.1.9 em cartao novo/descartavel.

C12.4 continua bloqueado ate uma validacao em placa provar:

- `read_only_enabled=true`;
- `overlay_active=true`;
- `root_write_blocked=true`;
- `/data`, `/tmp` e `/run` gravaveis;
- SSH e UI Dadooh funcionais.

## Resultado em Placa C12.3.10

A imagem C12.1.9 foi gravada e bootada na placa lab. O SHA real foi confirmado:

```text
f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c
```

O boot passou, SSH ficou disponivel, o firstboot lab concluiu e o produto ficou
em `config_missing`, esperado para image-lab sem config real. O read-only,
porem, ainda nao ativou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- `root_fstype=ext4`.

C12.3.10 mostrou que a correcao de caminho entrou no boot: `overlayroot=tmpfs`
chegou ao cmdline, o hook Dadooh foi executado, o caminho efetivo do modulo foi
encontrado e o fallback `insmod` foi tentado. A nova classificacao e:

```text
INSMOD_FALLBACK_FAILED
```

C12.4 continua bloqueado. O proximo passo recomendado e C12.3.11 para
diagnosticar a falha do `insmod` no initramfs por categoria, sem logs brutos.
