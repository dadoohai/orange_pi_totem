# ADR-0011 - Root Read-only Overlay Mechanism

Data: 2026-05-06

Status: aceito para bloquear C11.4 e mover o proximo experimento para imagem/base.

## Contexto

O produto precisa de root filesystem protegido contra escrita comum antes de
qualquer teste de corte seco. A politica do projeto continua sendo:

- imagem gerada por codigo;
- kernel/DTB/U-Boot/BSP congelados;
- sem `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`;
- estado mutavel em `/data`, `/tmp` e `/run`;
- read-only com overlay como meta antes de corte seco.

C11.3 detectou que o caminho oficial do Armbian usa `module_overlayfs`, mas o
pacote `overlayroot` nao estava instalado. C11.3.1 instalou o prerequisito de
forma controlada na dev. C11.3.2 tentou habilitar na dev, mas o overlay nao
ativou. C11.3.3 repetiu em laboratorio na placa teste, preservando a dev, e
obteve o mesmo resultado.

## Tentativas

C11.3.1:

- pacote exato identificado: `overlayroot`;
- dry-run apt seguro: zero upgrades, zero removals;
- pacote instalado na dev com `--no-upgrade --no-install-recommends`;
- `overlayroot-chroot` e script initramfs ficaram presentes.

C11.3.2:

- primeira falha contaminada por fonte USB da TV;
- reteste com fonte dedicada voltou por SSH;
- `read_only_enabled=false`;
- `overlay_active=false`;
- root continuou `ext4` gravavel;
- rollback executado.

C11.3.3:

- dev usada somente para sanity check;
- placa teste usada como laboratorio;
- pacote instalado na teste apos dry-run seguro;
- enable + reboot voltaram por SSH;
- `read_only_enabled=false`;
- `overlay_active=false`;
- rollback executado.

## Diagnostico

A classificacao sanitizada do laboratorio foi:

```text
initramfs_log_driver_lookup_failed=true
```

Achados relevantes:

- o pacote `overlayroot` esta instalado na placa teste;
- `overlayroot-chroot` existe;
- o script initramfs do pacote existe;
- o initramfs contem o hook `overlayroot`;
- o initramfs contem modulo `overlay`;
- o runtime do kernel suporta `overlay`;
- `uInitrd` existe e e usado pelo boot;
- `/etc/overlayroot.conf` foi rollbackado para desabilitado;
- `overlayroot.local.conf` nao existe;
- kernel cmdline e `armbianEnv.txt` nao contem override `overlayroot`;
- o erro ocorre na fase initramfs, antes de montar o overlay.

Portanto, a causa provavel nao e ausencia simples do pacote. O bloqueio esta na
integracao entre o hook `overlayroot`, initramfs/uInitrd e a base Armbian atual.
O pacote e necessario, mas nao suficiente nesta imagem instalada.

## Opcoes Avaliadas

### A. Corrigir overlayroot atual na imagem instalada

Possivel, mas arriscado na dev funcional. Exigiria investigar initramfs/uInitrd,
ordem de hooks, modprobe e parametros de boot em midia ja provisionada. Deve
ocorrer somente em laboratorio separado se for retomado.

### B. Incluir e validar o mecanismo na imagem base C12

Preferida. A imagem base deve incluir o pacote `overlayroot`, gerar initramfs e
uInitrd no processo de build, e validar o boot read-only antes de tratar a base
como candidata. Isso preserva reprodutibilidade e evita enablement artesanal em
placa ja configurada.

### C. Criar mecanismo overlay proprio

Rejeitada por enquanto. Um overlay proprio em boot/rootfs aumentaria risco de
recuperacao, divergiria do Armbian e exigiria matriz de testes maior.

### D. Adiar root read-only ate nova base

Aceitavel como consequencia operacional, mas nao como decisao de longo prazo. O
produto nao deve ir para corte seco ou release final sem read-only validado.

## Decisao

Manter C11.4 bloqueado e mover o proximo experimento permitido para imagem/base:

```text
root_read_only_mechanism_decision=c12_image_integrated_overlay_lab_required
next_allowed_step=C12.0-prep
ready_for_c11_4=false
```

Nao tentar novo enable direto na dev. A dev permanece referencia funcional.
Nova tentativa de `overlayroot` so deve ocorrer em laboratorio descartavel ou
em imagem C12 gerada por codigo, com rollback/recuperacao offline definidos.

## Consequencias

- `read_only=false` permanece no manifest.
- `power_cut_tested=false` permanece.
- C11.4 nao pode iniciar.
- C12 deve tratar `overlayroot` como prerequisito da imagem, nao como conserto
  manual de campo.
- O instalador pode manter `--install-readonly-prereqs`, mas isso nao libera
  read-only nesta base instalada.

## Proximo Experimento Permitido

C12.0-prep deve gerar ou preparar uma base de laboratorio que:

- inclua `overlayroot` no build;
- gere initramfs/uInitrd com o mecanismo ja presente;
- valide `read_only_enabled=true`;
- valide `/data`, `/tmp` e `/run` gravaveis;
- valide rollback offline;
- so depois considere habilitar corte seco em rodada posterior.
