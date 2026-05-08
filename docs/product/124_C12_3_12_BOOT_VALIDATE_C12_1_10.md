# C12.3.12 - Boot Validate C12.1.10

Data: 2026-05-08

## Objetivo

Validar o boot real da imagem-lab C12.1.10 apos gravacao em cartao e classificar
o resultado observado: tela preta no HDMI com SSH disponivel.

Nao houve uso da dev, placa teste antiga, wizard, writer, config real,
Wi-Fi/NetworkManager, instalacao de pacotes, reboot extra, poweroff ou corte
seco.

## Boot

A placa lab bootou e ficou acessivel por SSH:

- `image_version=c12.1.10`;
- `ssh_available=true`;
- `firstboot_marker_present=false`;
- `public_state=config_missing`;
- `config_real_present=false`;
- `session_lock_present=false`;
- `request_present=false`.

O estado `config_missing` continua esperado para image-lab sem config privada do
player.

## Read-only

O objetivo principal ainda nao passou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- `root_fstype=ext4`;
- `/data writable=true`;
- `/tmp writable=true`;
- `/run writable=true`.

C12.4 permanece bloqueado.

## Overlayroot

A correcao C12.1.10 entrou no boot:

- `overlayroot=tmpfs` chegou ao cmdline;
- status do hook `dadooh-force-overlay` esta presente;
- `overlay_module_path_found=true`;
- `overlay_module_path_source=static_fallback`;
- `modprobe_rc=0`;
- `insmod_rc=1`;
- `overlay_in_proc=false` no initramfs;
- `overlay` aparece em `/proc/filesystems` depois do boot normal.

Classificacao:

```text
DYNAMIC_PATH_FOUND_INSMOD_FAILED
```

Isso reconcilia C12.1.10 com C12.3.11: a resolucao dinamica de path agora
funciona no initramfs, mas o carregamento por `insmod` ainda falha. O proximo
diagnostico precisa capturar categoria de erro do `insmod` usando o path
dinamico que foi encontrado.

## Tela Preta

Observacao humana:

```text
tela_preta=true
```

Diagnostico sanitizado:

- `public_state=config_missing`;
- `status.svg` existe;
- `status.svg` contem SVG valido;
- `status.svg` contem texto/categoria de config_missing;
- `renderer_process_count=1`;
- `MPV_process_count=1`;
- `splash_process_count=0`.

Classificacao:

```text
CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE
```

Isso indica que o artefato visual publico existe, mas nao apareceu no HDMI. O
problema visual fica separado do bloqueio read-only. Nao foi feita correcao de
UI nesta rodada.

## Status

- `ready_for_c12_4=false`;
- `read_only_validated=false`;
- `c12_4_blocked=true`;
- `next_step=C12.3.13_DYNAMIC_PATH_INSMOD_ERROR_DIAGNOSTICS`.
