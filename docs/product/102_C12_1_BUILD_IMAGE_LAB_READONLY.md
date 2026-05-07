# C12.1 - Build Image-Lab Read-only

Data: 2026-05-06

## Objetivo

Gerar a primeira imagem-lab com root read-only integrado no build, sem gravar
cartao e sem tocar nas placas dev/teste.

## Build

Ambiente usado:

- Armbian Build: `v25.11`
- commit Armbian Build: `e172058`
- board: `orangepizero3`
- release: `bookworm`
- branch: `current`
- kernel: `6.12.58-current-sunxi64`
- U-Boot: `2025.04`
- build: minimal, sem desktop
- network stack: NetworkManager

O runner criado foi:

```text
scripts/build/run_c12_1_build_image_lab_readonly.sh
```

Ele prepara userpatches locais, valida o pin do `kiosky-player`, copia apenas
arquivos allowlisted do appliance e executa o Armbian Build sem acessar placas.

## Userpatches

Foram versionados em:

```text
scripts/build/userpatches-c12-image-lab/
```

Conteudo principal:

- `overlayroot` incluido como pacote de imagem;
- `mpv`, `ffmpeg`, `python3-requests` e NetworkManager presentes;
- policy de journald volatil;
- layout `/data`;
- scripts/units do appliance via instalador;
- trigger F10 e splash/wizard existentes;
- `kiosky-player` fixado em `c71318a64c08e47b8426f1388b95f21364d57123`;
- sem config real, secrets, SSID/senha, media cache ou logs brutos.

## Artefatos

Imagem gerada:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img
```

SHA256:

```text
1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2
```

Artefatos relacionados:

- checksum: imagem `.sha256`;
- build log: `log-build-29bced66-eed1-4f2c-8d0e-d2ad34f794b5.log`;
- package manifest: `releases/image-lab-readonly/package-manifest-c12-1.txt`;
- integration manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1.txt`.

## Read-only Integrado

O build confirmou:

- `overlayroot_included=true`;
- `initramfs_generated_after_overlayroot=true`;
- `card_written=false`;
- `boards_touched=false`;
- `final_image=false`.

O primeiro build abortou por falta de memoria ao usar rootfs em tmpfs. A
configuracao foi ajustada para `FORCE_USE_RAMDISK=no`, e a imagem foi gerada
com sucesso em disco.

## O Que Ainda Falta

C12.1 nao valida boot em placa. O proximo passo e C12.2:

1. preparar cartao de teste;
2. gravar somente a imagem-lab;
3. bootar na placa teste;
4. validar `read_only_enabled`, `overlay_active`, root protegido, `/data`,
   `/tmp` e `/run` gravaveis;
5. validar player e F10 open/cancel.

Corte seco e imagem final continuam bloqueados.

## C12.1.2

Em 2026-05-07, a imagem foi reconstruida como C12.1.2 apos o bloqueio C12.3.
A nova imagem incorpora cleanup da sessao F10, gate de firstboot e assert
explicito de read-only:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img
```

SHA256:

```text
a398399c139c3fee1b05860b216db7facfddd0ae1a57f681b229228390b7abd9
```

Esta nova imagem substitui a C12.1 para a proxima gravacao de cartao
C12.2.1. A imagem antiga permanece apenas como historico/superseded.
