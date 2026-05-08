# C12.1.10 - Rebuild Image-Lab Overlay Dynamic Path

Data: 2026-05-08

## Objetivo

Reconstruir a imagem-lab corrigindo a tensao entre C12.3.10 e C12.3.11:

- C12.3.10 indicou que o fallback `insmod` foi tentado;
- C12.3.11 refinou que, no runtime do initramfs, `overlay.ko` nao ficou
  resolvivel e o `insmod` nao chegou a executar naquela coleta.

A interpretacao atual e:

```text
OVERLAY_MODULE_PATH_MISMATCH
```

Nenhuma placa foi tocada, nenhum cartao foi gravado, nenhum writer foi chamado
e nenhum secret foi publicado.

## Correcao

O hook `init-top` `dadooh-force-overlay` agora usa resolucao dinamica de caminho
para o modulo `overlay`:

- detecta o kernel com `uname -r`;
- tenta caminhos estaticos em `/lib/modules/<kernel>` e
  `/usr/lib/modules/<kernel>`;
- consulta `modules.dep` para derivar o caminho relativo real;
- faz fallback por `find` em `usr/lib/modules` e `lib/modules`;
- registra somente categorias sanitizadas:
  `overlay_module_path_found`, `overlay_module_path_source`,
  `modprobe_rc`, `insmod_rc` e `overlay_in_proc`;
- nao publica logs brutos.

Isso evita depender de um unico path hardcoded em um initramfs usr-merged onde
`/lib` pode ser symlink para `usr/lib`.

## Artefato

Imagem C12.1.10:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-10_minimal.img
```

SHA256:

```text
c7e3e2af5e2cfa52db0a1cb73141b941a239471940020953d6debfbb0133e4b2
```

Build log:

```text
/home/builder/totem-os/armbian-build-v25.11/output/logs/log-build-184d666e-e1a1-4586-a52b-7f9c54a1945e.log
```

## Validacao Offline

Validado nos artefatos:

- `overlayroot_included=true`;
- `uinitrd_nonempty=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `boot_script_uses_uinitrd=true`;
- `overlay_module_discoverable_in_initramfs=true`;
- `overlay_module_discovery_method=static`;
- `fallback_hook_dynamic_path=true`;
- `modules_dep_references_overlay=true`;
- `modprobe_present_in_initramfs=true`;
- `insmod_present_in_initramfs=true`;
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

C12.2.6 pode gravar a imagem C12.1.10 em cartao novo/descartavel.

C12.4 continua bloqueado ate uma validacao em placa provar:

- `read_only_enabled=true`;
- `overlay_active=true`;
- `root_write_blocked=true`;
- `/data`, `/tmp` e `/run` gravaveis;
- SSH e UI Dadooh funcionais.

## Resultado em Placa C12.3.12

A imagem C12.1.10 foi gravada e bootada na placa lab. O SSH ficou disponivel,
mas a observacao humana foi tela preta.

O objetivo read-only ainda nao passou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- `root_fstype=ext4`.

A correcao de path dinamico entrou no boot: `overlay_module_path_found=true` e
`overlay_module_path_source=static_fallback`. O novo bloqueio e:

```text
DYNAMIC_PATH_FOUND_INSMOD_FAILED
```

Separadamente, a UI ficou classificada como:

```text
CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE
```

C12.4 continua bloqueado. O proximo passo recomendado e C12.3.13 para
diagnosticar a categoria do erro do `insmod` usando o path dinamico encontrado.
