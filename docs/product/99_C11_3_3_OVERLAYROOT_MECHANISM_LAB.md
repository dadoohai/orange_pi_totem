# C11.3.3 - Overlayroot Mechanism Lab

Data: 2026-05-06

Status: mecanismo bloqueado em laboratorio. C11.4 continua bloqueado.

## Objetivo

Diagnosticar o enablement `overlayroot` fora da placa dev, preservando a dev
como referencia funcional.

## Contexto

C11.3.2 teve uma primeira falha contaminada por alimentacao via USB da TV. Com
fonte dedicada, a dev voltou por SSH e o player permaneceu operacional, mas o
overlay nao ativou:

- `read_only_enabled=false`;
- `overlay_active=false`;
- root continuou `ext4` gravavel.

Por isso, C11.3.3 moveu a investigacao para a placa teste.

## Dev Preservada

Na dev, C11.3.3 executou somente sanity check read-only:

- `read_only_enabled=false`;
- `overlay_active=false`;
- `overlayroot` desabilitado;
- patches experimentais removidos;
- servicos principais `active/enabled`;
- `systemctl_failed_count=0`;
- filtro sanitizado de kernel retornou `2` na categoria MMC, sem logs brutos publicados.

Nenhum enable foi executado na dev.

## Laboratorio na Placa Teste

A placa teste inicialmente nao tinha o prerequisito `overlayroot`. Foi feito
um dry-run apt antes da instalacao:

- `would_upgrade_count=0`;
- `would_remove_count=0`;
- pacotes kernel/DTB/U-Boot/BSP nao seriam tocados;
- pacotes criticos em hold: `true`.

Depois da confirmacao humana, foi instalado somente o pacote exato
`overlayroot` com:

```bash
apt-get install --no-upgrade --no-install-recommends overlayroot
```

Sem `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`.

## Resultado do Enable na Teste

Na placa teste:

- `overlayroot-chroot=true`;
- script initramfs do pacote presente;
- `/etc/overlayroot.conf` configurado para `overlayroot=tmpfs`;
- reboot controlado executado;
- SSH voltou;
- `read_only_enabled=false`;
- `overlay_active=false`;
- root continuou `ext4` gravavel;
- rollback executado e `overlayroot` ficou desabilitado novamente.

A causa classificada de forma sanitizada foi:

```text
initramfs_log_driver_lookup_failed=true
```

## Decisao

C11.3.3 prova que o pacote instalado nao basta para ativar read-only neste
estado da imagem. O mecanismo atual fica bloqueado:

- `ready_for_c11_3_4_enable_dev=false`;
- `move_to_c12_image=false`;
- `mechanism_blocked=true`;
- `ready_for_c11_4=false`.

Nao tentar novo enable na dev. A proxima rodada deve investigar uma correcao do
mecanismo em laboratorio separado ou escolher outra abordagem de root read-only.

## Nao Alterado

- config real nao lida/escrita;
- writer nao chamado;
- Wi-Fi/NetworkManager nao alterados;
- `kiosky-player` nao alterado;
- corte seco e poweroff nao executados;
- logs brutos e dados sensiveis nao publicados.
