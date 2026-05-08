# C12.3.11 - Initramfs Insmod Error Classification

Data: 2026-05-08

## Objetivo

Classificar por que o fallback `insmod overlay` nao ativa `overlay` no runtime
do initramfs da imagem-lab C12.1.9.

Nao houve uso da dev, da placa teste antiga, writer, config real,
Wi-Fi/NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Metodo

Foi instalado um hook temporario de diagnostico no initramfs, com backup,
`update-initramfs`, regeneracao de `uInitrd`, reboot controlado e rollback.

O hook registrou somente categorias e booleans. Nao foram publicados dmesg bruto,
stderr bruto, secrets, config real, SSID, senha ou dados de rede.

## Resultado

Antes do hook, no runtime normal pos-boot:

- `overlay_ko_exists=true`;
- `overlay_ko_file_type=plain_ko`;
- `overlay_ko_size_bucket=small`;
- `vermagic_match=true`;
- `dependencies_detected=[]`;
- `modules_dep_references_overlay=true`;
- `modprobe_overlay_post_boot_works=true`.

No runtime do initramfs, durante o boot diagnostico:

- `modprobe_overlay_result=zero`;
- `proc_filesystems_has_overlay_after_modprobe=false`;
- `overlay_ko_exists=false`;
- `overlay_ko_file_type=missing`;
- `modules_dep_references_overlay=false`;
- `insmod_overlay_attempted=false`;
- `insmod_stderr_category=missing`;
- `dmesg_category=no_message`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`.

O SSH voltou e o rollback removeu o hook temporario:

- `rollback_executed=true`;
- `diagnostic_hook_present_after=false`;
- `update_initramfs_ok=true`;
- `uinitrd_nonempty_after=true`.

## Classificacao

```text
OVERLAY_MODULE_PATH_MISMATCH
```

A rodada C12.3.10 indicava `INSMOD_FALLBACK_FAILED`, mas C12.3.11 refinou esse
resultado: o fallback por `insmod` nao chegou a executar nesta coleta porque o
arquivo `overlay.ko` nao estava resolvivel no path efetivo usado pelo initramfs
naquele estagio.

A causa provavel continua ligada ao layout usr-merged do initramfs. A validacao
offline provou o modulo por meio de `/lib -> usr/lib`, mas o runtime do hook
precisa resolver explicitamente o caminho efetivo antes do `overlayroot` rodar.

## Proximo Passo

```text
C12_1_10_REBUILD_WITH_EFFECTIVE_MODULE_PATH
```

C12.1.10 deve corrigir a imagem/build para:

- resolver `overlay.ko` em `/usr/lib/modules/<kernel>/...` e/ou seguir symlinks;
- garantir que `modules.dep` usado no initramfs aponta para o mesmo layout;
- ajustar o hook de carga para usar path absoluto validado ou busca com symlink
  resolvido;
- endurecer a validacao offline para simular o path efetivo do runtime do
  initramfs, nao apenas a listagem extraida.

C12.4 continua bloqueado ate uma imagem bootar com:

- `read_only_enabled=true`;
- `overlay_active=true`;
- `root_write_blocked=true`.

## Atualizacao C12.1.10

C12.1.10 reconciliou C12.3.10/C12.3.11 endurecendo o hook e a validacao:

- o hook nao depende mais de um unico path hardcoded;
- ele tenta `/lib/modules`, `/usr/lib/modules`, `modules.dep` e busca dinamica;
- a validacao offline exige `fallback_hook_dynamic_path=true`;
- a imagem C12.1.10 valida `overlay_module_discoverable_in_initramfs=true` e
  `effective_boot_initramfs_overlay_resolvable=true`.

C12.2.6 pode gravar a nova imagem. C12.4 segue bloqueado ate validacao em placa.

## Atualizacao C12.3.13

A imagem C12.1.10 provou que a resolucao dinamica do path passou a funcionar,
mas o diagnostico seguinte ainda nao ativou `overlay`. A classificacao refinada
e:

```text
OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS
```

Campos relevantes:

- `overlay_ko_path_resolved=true`;
- `overlay_ko_file_type=plain_ko`;
- `overlay_ko_size_bucket=empty`;
- `modules_dep_references_overlay=false`;
- `insmod_overlay_attempted=true`;
- `insmod_overlay_rc=nonzero`;
- `dmesg_category=no_message`.

O proximo passo e C12.1.11, garantindo modulo `overlay.ko` nao vazio e
`modules.dep` coerente no initramfs efetivo.
