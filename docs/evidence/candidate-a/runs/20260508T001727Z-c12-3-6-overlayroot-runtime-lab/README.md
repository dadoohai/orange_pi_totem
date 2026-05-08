# C12.3.6 Overlayroot Runtime Lab

Data: 2026-05-08

## Escopo

Laboratorio runtime na placa descartavel com imagem C12.1.8 ja acessivel por SSH.
A dev e a placa teste antiga nao foram tocadas. Nao houve writer, config real,
alteracao de Wi-Fi/NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Hipoteses Testadas

- `H1`: adicionar `overlayroot=tmpfs` ao `extraargs` de `/boot/armbianEnv.txt`.
- `H2`: regenerar `initramfs` e `uInitrd` localmente para o kernel atual.

`H1` foi aplicada com backup e rollback. Depois do reboot, `overlayroot=tmpfs`
chegou ao cmdline e o hook `overlayroot` passou a rodar.

`H2` executou `update-initramfs` com retorno `0`, manteve `uInitrd` nao vazio e
nao precisou de fallback manual com `mkimage`.

## Resultado

- hypotheses_tested: `H1,H2`
- winning_hypothesis: `none`
- reboot_count: `2`
- read_only_enabled: `false`
- overlay_active: `false`
- root_write_blocked: `false`
- writable_paths_ok: `/data,/tmp,/run=true`
- rollback_available: `true`
- systemctl_failed_count: `0`

## Causa Classificada

A falha mudou de "hook nao visivel no boot" para falha dentro do initramfs:

- cmdline_overlayroot_present: `true`
- overlayroot_log_seen: `true`
- initramfs_overlay_driver_lookup_failed: `true`
- loaded_overlay_but_no_proc_filesystems: `true`

Classificacao:

```text
OVERLAY_DRIVER_UNAVAILABLE_IN_INITRAMFS_RUNTIME
```

O modulo existe no sistema bootado e aparece em `/proc/filesystems` depois do
boot normal, mas no momento em que o `overlayroot` roda dentro do initramfs ele
nao fica registrado como filesystem disponivel.

## Decisao

Nao testar H3/H4 nesta rodada: ambas mudam caminhos/normalizacao de config, mas
H1 ja provou que a configuracao chegou ao cmdline e o blocker atual e driver no
runtime do initramfs, nao caminho de config.

## Proximo Fix

C12.1.9 deve corrigir a imagem/base para garantir que o driver `overlay` esteja
carregavel e registrado no initramfs antes do `overlayroot` executar. Possiveis
frentes:

- ajustar ordem/modulos do initramfs para `overlay`;
- forcar preload do modulo `overlay` no initramfs antes do script `overlayroot`;
- avaliar se `overlayroot` desta base precisa de patch/hook complementar no
  initramfs;
- manter `overlayroot=tmpfs` em `extraargs` no build, pois H1 foi necessario.

Nenhum secret, config real, SSID/senha, IP/MAC/DNS ou log bruto foi publicado.
