# C11.3 - Read-only Enablement Dev

Data: 2026-05-06

Status: enablement bloqueado de forma segura. Root read-only nao foi
habilitado.

## Objetivo

Habilitar root read-only/overlay na placa dev com mecanismo oficial, rollback e
reboot controlado, sem corte seco e sem tocar a placa teste.

## Inspecao

A dev possui suporte no `armbian-config` para a acao de read-only via
`module_overlayfs`. Esse modulo configura `overlayroot`.

Resultado detectado:

- `mechanism_detected=armbian_config_module_overlayfs`;
- `overlayroot_available=false`;
- `overlayroot_chroot_available=false`;
- `package_install_required=true`;
- `can_enable_without_package_install=false`;
- `risk_level=blocked_missing_overlayroot_package`.

## Decisao

C11.3 nao deve inventar um overlay proprio frágil nem instalar pacotes, porque
as regras desta rodada proibem instalacao de pacotes e `apt upgrade`.

Portanto:

- `enable_executed=false`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `ready_for_c11_4=false`.

## Validacao

Rodado na dev:

- `--prepare-only`;
- `--inspect`;
- `--dry-run-enable`.

Resultado:

- `public_state=player_running`;
- playback `playing`;
- servicos principais `active/enabled`;
- `systemctl_failed_count=0`;
- `/data`, `/tmp` e `/run` gravaveis;
- root ainda gravavel, como esperado antes de read-only;
- placa teste nao tocada.

## Nao Alterado

- root read-only nao habilitado;
- reboot nao executado nesta rodada;
- corte seco nao executado;
- poweroff nao executado;
- config real nao lida/escrita;
- writer nao chamado;
- Wi-Fi/NetworkManager nao alterados;
- perfis NetworkManager nao alterados;
- `kiosky-player` nao alterado;
- pacotes nao instalados.

## Runner

Foi criado:

```text
scripts/remote/run_c11_3_read_only_enablement_dev.sh
```

O runner suporta:

- `--prepare-only`;
- `--inspect`;
- `--dry-run-enable`;
- `--enable-read-only`;
- `--verify`;
- `--reboot-check`;
- `--rollback-read-only`;
- `--summary`.

`--enable-read-only` aborta se o pacote `overlayroot`, `overlayroot-chroot` ou
o script initramfs do pacote estiverem ausentes, mesmo com confirmacao.

## Proximo Passo

C11.3.1 deve ser uma decisao de mecanismo:

- aprovisionar `overlayroot` de forma controlada e sem `apt upgrade`;
- ou mover esse requisito para a imagem base C12;
- ou desenhar outro mecanismo read-only/overlay em uma rodada separada.

Enquanto isso, C11.4 nao deve iniciar porque read-only nao foi habilitado.

## Follow-up C11.3.1

C11.3.1 validou o prerequisito oficial em vez de criar overlay proprio:

- pacote exato: `overlayroot`;
- dry-run seguro: `would_upgrade_count=0`, `would_remove_count=0`;
- nenhum pacote kernel/DTB/U-Boot/BSP seria tocado;
- pacote instalado na dev apos confirmacao humana separada;
- `overlayroot-chroot` e o script initramfs do pacote ficaram disponiveis;
- o pacote Debian nao fornece comando `overlayroot` no PATH, e a deteccao foi
  ajustada para o artefato real;
- instalador e manifest passam a declarar `--install-readonly-prereqs`.

C11.3.2 pode tentar habilitar root read-only novamente na dev, ainda com
rollback e reboot controlado. A imagem base C12 deve incluir esse pacote.

## Follow-up C11.3.2

C11.3.2 repetiu o enablement depois de recuperar a placa dev offline e mover a
alimentacao para fonte dedicada.

A falha anterior foi classificada como `POWER_SUPPLY_CONFOUNDED`, pois a placa
estava alimentada pela USB da TV e a TV desligou. No reteste com fonte dedicada,
o SSH voltou e o player permaneceu operacional, mas `overlayroot` nao ativou:

- `enable_executed=true`;
- `reboot_executed=true`;
- `ssh_returned=true`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `public_state=player_running`;
- playback `playing`;
- rollback final executado.

Classificacao final da rodada: `OVERLAYROOT_ENABLE_DID_NOT_ACTIVATE`.

C11.4 continua bloqueado. O proximo passo de read-only deve ocorrer em cartao
separado ou na imagem/base C12, nao em nova tentativa direta na placa de produto.
