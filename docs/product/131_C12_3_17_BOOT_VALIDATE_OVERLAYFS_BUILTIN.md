# C12.3.17 - Boot Validate Overlayfs Built-in

Data: 2026-05-08

## Objetivo

Validar em boot real a imagem C12.1.12, que passou na validacao offline com:

- `CONFIG_OVERLAY_FS=y`;
- `overlayroot` incluido/configurado;
- `overlayroot=tmpfs`;
- `uInitrd` valido;
- hooks antigos de fallback modular ausentes;
- hooks diagnosticos temporarios ausentes.

A validacao correta para `overlayroot` nao exige `root_write_blocked=true`. O
criterio correto e semantica de persistencia:

- root montado como overlay ou equivalente;
- escrita fora de `/data` nao persiste apos reboot;
- escrita em `/data` persiste apos reboot;
- `/data`, `/tmp` e `/run` gravaveis;
- journald volatil.

## Execucao

Foi criado o runner:

```text
scripts/remote/run_c12_3_17_boot_validate_overlayfs_builtin.sh
```

Modos implementados:

- `--prepare-only`;
- `--inspect`;
- `--persistence-test`;
- `--post-reboot`;
- `--summary`.

O runner limita o teste de persistencia a casos em que o inspect confirma
`overlay_active=true` ou root mount type `overlay`.

## Resultado

A imagem foi informada como gravada manualmente e bootada pelo operador. A
primeira tentativa de SSH deste ambiente nao autenticou com chave, mas a senha
foi usada apenas interativamente, sem ser registrada em docs/evidencia.

O inspect remoto foi executado e classificou:

```text
c12_3_17_status=blocked
c12_3_17_failure_category=IMAGE_LAB_READ_ONLY_NOT_ACTIVE_WITH_BUILTIN_OVERLAYFS
```

Confirmado em runtime:

- `CONFIG_OVERLAY_FS=y` no kernel em execucao;
- `overlay` presente em `/proc/filesystems`;
- `overlayroot=tmpfs` presente no cmdline;
- `/etc/overlayroot.conf` com `overlayroot=tmpfs`;
- NetworkManager ativo;
- `/data`, `/tmp` e `/run` gravaveis;
- produto em `config_missing`, esperado sem config real.

Bloqueio principal:

```text
root_mount_type=ext4
root_mount_source_category=device
overlay_active=false
readonly_semantics_valid=false
```

Como `overlay_active=false`, os marcadores de persistencia nao foram criados e
o reboot controlado nao foi executado.

Pendencias observadas sem tratar como blocker principal:

- `journald_storage_category=volatile`, mas `journald_volatile=false` porque
  `/var/log/journal` ainda existe no boot observado;
- `systemctl_failed_count=1`, categorizado como `console_setup`.

## Guardrails

Nada operacional foi alterado na placa:

- nenhum marcador sintetico foi criado;
- nenhum reboot foi executado;
- nenhum `apt update` ou upgrade foi executado;
- nenhum pacote foi instalado;
- nenhum writer foi chamado;
- nenhuma config real foi lida ou alterada;
- Wi-Fi/NetworkManager nao foram alterados;
- nenhum poweroff ou corte seco foi executado;
- nenhum segredo foi publicado.

## Status

```text
c12_3_17_status=blocked
readonly_semantics_valid=false
ready_for_c12_4=false
c12_4_blocked=true
```

## Proximo Passo

Abrir a proxima rodada para diagnosticar por que `overlayroot=tmpfs` e
`CONFIG_OVERLAY_FS=y` estao presentes no runtime, mas o initramfs/boot flow nao
ativa overlayroot e o root ainda monta como `ext4`.

C12.4 continua bloqueado.
