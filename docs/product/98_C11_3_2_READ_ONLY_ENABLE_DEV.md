# C11.3.2 - Read-only Enable Dev

Data: 2026-05-06

Status: bloqueado de forma segura. A placa dev voltou operacional, mas
`overlayroot` nao ativou root read-only.

## Objetivo

Habilitar root read-only/overlay na placa dev com `overlayroot`, rollback e
reboot controlado, sem corte seco e sem tocar a placa teste.

## Recuperacao e Reteste

A primeira tentativa terminou com tela preta e sem SSH. Depois foi identificado
um fator externo: a placa estava alimentada pela USB da TV, e a TV desligou.
Por isso, o incidente anterior foi classificado como
`POWER_SUPPLY_CONFOUNDED`, nao como falha conclusiva de overlayroot.

Foi feito rollback offline seguro editando apenas `/etc/overlayroot.conf` do
cartao da dev. Depois, com a dev em fonte dedicada, o fluxo foi repetido.

## Resultado do Reteste

- `previous_failure_confounded_by_power_source=true`;
- `power_source_for_retest=dedicated_psu`;
- `rollback_after_offline_recovery=true`;
- `enable_executed=true`;
- `reboot_executed=true`;
- SSH voltou;
- `read_only_enabled=false`;
- `overlay_active=false`;
- root continuou `ext4` gravavel;
- `/data`, `/tmp` e `/run` ficaram gravaveis;
- `public_state=player_running`;
- playback `playing`;
- servicos principais `active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`;
- rollback final executado para deixar `overlayroot` desabilitado.

## Classificacao

O reteste com fonte dedicada confirmou que a placa nao fica indisponivel por
causa do reboot, mas tambem confirmou que o mecanismo atual nao habilita
read-only. Classificacao:

```text
OVERLAYROOT_ENABLE_DID_NOT_ACTIVATE
```

Nao houve nova tentativa de patch no pacote, novo reboot ou corte seco depois
dessa classificacao.

## Nao Alterado

- placa teste nao tocada;
- config real nao lida/escrita;
- writer nao chamado;
- Wi-Fi/NetworkManager nao alterados;
- `kiosky-player` nao alterado;
- pacotes nao instalados nesta rodada;
- poweroff/corte seco nao executados;
- logs brutos e dados sensiveis nao publicados.

## Decisao

C11.3.2 nao libera C11.4. `read_only=false` e `ready_for_c11_4=false` devem
permanecer.

Read-only deve seguir por uma das rotas abaixo em rodada nova:

- validar o mecanismo oficial em cartao separado;
- mover enablement para imagem/base C12;
- escolher mecanismo overlay/root read-only alternativo com plano de recuperacao
  proprio.

A placa dev deve permanecer em modo normal (`overlayroot` desabilitado) ate nova
decisao.

## Follow-up C11.3.3

C11.3.3 preservou a dev e levou a investigacao para a placa teste. O laboratorio
reproduziu o comportamento: apos instalar `overlayroot`, configurar
`overlayroot=tmpfs` e rebootar, o SSH voltou, mas `read_only_enabled=false` e
`overlay_active=false`. A causa sanitizada foi
`initramfs_log_driver_lookup_failed=true`.

C11.4 segue bloqueado. Nao executar novo enable na dev ate uma estrategia passar
em laboratorio.
