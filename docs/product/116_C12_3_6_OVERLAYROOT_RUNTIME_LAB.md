# C12.3.6 - Overlayroot Runtime Lab

Data: 2026-05-08

## Objetivo

Usar a placa descartavel com imagem C12.1.8 como laboratorio runtime para
descobrir por que `overlayroot` nao ativa no boot, sem rebuild completo para
cada hipotese.

Nao houve uso da dev, da placa teste antiga, writer, config real, Wi-Fi,
NetworkManager, instalacao de pacotes, poweroff ou corte seco.

## Hipoteses

Foram testadas duas hipoteses com backup e rollback:

- `H1`: adicionar `overlayroot=tmpfs` ao `extraargs` de `/boot/armbianEnv.txt`;
- `H2`: regenerar `initramfs` e `uInitrd` localmente para o kernel atual.

`H1` foi util: depois do reboot, `overlayroot=tmpfs` chegou ao cmdline e o hook
do `overlayroot` passou a rodar no initramfs.

`H2` executou `update-initramfs` com sucesso e manteve `uInitrd` nao vazio, mas
nao alterou o resultado final.

## Resultado

O overlay nao ativou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_write_blocked=false`;
- root continua `ext4 rw`;
- `/data`, `/tmp` e `/run` continuam gravaveis;
- SSH voltou apos os reboots;
- `systemctl_failed_count=0`;
- rollback permanece disponivel.

## Causa Classificada

A falha agora esta melhor localizada:

```text
OVERLAY_DRIVER_UNAVAILABLE_IN_INITRAMFS_RUNTIME
```

O modulo `overlay` existe no sistema e aparece como filesystem depois do boot
normal, mas dentro do initramfs o script do `overlayroot` carrega o modulo e
mesmo assim nao encontra `overlay` em `/proc/filesystems`. Por isso o root
continua montado como `ext4 rw`.

## Decisao

Nao testar H3/H4 nesta rodada. Elas tratam caminho/normalizacao de config, mas
H1 ja provou que a configuracao chega ao cmdline. O blocker atual e a
disponibilidade do driver `overlay` no runtime do initramfs.

## Build Naming

O script de build agora exige `C12_IMAGE_TAG` explicito para novos builds e
falha se ja existir uma imagem com o mesmo marcador. Isso evita sobrescrever
artefatos antigos silenciosamente.

## Proximo Passo

C12.1.9 deve reconstruir a image-lab com dois ajustes:

- manter `overlayroot=tmpfs` no boot args/`extraargs`;
- garantir que o driver `overlay` esteja carregavel e registrado no initramfs
  antes do `overlayroot` executar.

C12.4 permanece bloqueado.
