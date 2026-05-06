# C11.3.1 - Overlayroot Prerequisite

Data: 2026-05-06

Status: pacote identificado, dry-run validado e instalacao real executada na
dev. Read-only ainda nao foi habilitado.

## Objetivo

C11.3 bloqueou o enablement read-only porque o mecanismo oficial do Armbian
existe, mas `overlayroot` e `overlayroot-chroot` nao estavam presentes. Esta
rodada valida o prerequisito sem inventar overlay proprio e sem habilitar
read-only.

## Resultado

- mecanismo detectado: `armbian_config_module_overlayfs`;
- pacote exato: `overlayroot`;
- pacote conhecido pelo apt cache: `true`;
- dry-run seguro: `true`;
- pacotes novos previstos: `3`;
- upgrades previstos: `0`;
- remocoes previstas: `0`;
- pacotes kernel/DTB/U-Boot/BSP tocados: `false`;
- pacotes kernel/DTB/U-Boot/BSP em hold: `true`;
- instalado nesta rodada: `true`;
- `overlayroot-chroot` disponivel apos instalacao: `true`;
- script initramfs do pacote presente: `true`;
- comando `overlayroot` no PATH: `false` (o pacote Debian entrega
  `overlayroot-chroot` e scripts initramfs, nao um binario `overlayroot`);
- `can_enable_without_package_install=true`;
- `ready_for_c11_3_2_enablement=true`;
- read-only habilitado: `false`;
- placa teste tocada: `false`.

## Politica de Instalacao

O pacote `overlayroot` entra como prerequisito de read-only, nao como runtime
normal do player.

O instalador passa a expor a flag:

```bash
scripts/board/install_totem_appliance.sh --apply --install-readonly-prereqs
```

Politica:

- pacote exato somente;
- `apt-get install --no-upgrade --no-install-recommends`;
- sem `apt upgrade`;
- sem `apt full-upgrade`;
- sem `apt dist-upgrade`;
- sem `armbian-upgrade`;
- sem habilitar read-only durante a instalacao do prerequisito.

## Imagem Final

A imagem C12 deve incluir `overlayroot` para que o enablement read-only nao
dependa de rede/apt em campo.

## Proximo Passo

C11.3.2 pode repetir o enablement read-only controlado na dev usando o pacote
ja instalado. C11.4 continua bloqueado ate o reboot read-only passar.

## Resultado Posterior em C11.3.2

O pacote `overlayroot` permaneceu como prerequisito identificado, mas o reteste
C11.3.2 com fonte dedicada mostrou que o mecanismo atual nao ativou o overlay na
placa dev. O pacote nao deve ser considerado suficiente para liberar C11.4 sem
nova estrategia de enablement.
