# C11.3.4 - Decisao do Mecanismo Root Read-only

Data: 2026-05-06

Status: decisao registrada. Read-only continua bloqueado.

## Objetivo

Entender por que `overlayroot` nao ativou em C11.3.2/C11.3.3 e decidir o
caminho correto para root read-only/overlay sem fazer nova tentativa de enable.

## Estado das Placas

Dev:

- usada somente para sanity check;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `overlayroot` desabilitado;
- servicos principais `active/enabled`;
- `public_state=player_running`;
- playback `running`;
- `systemctl_failed_count=0`.

Teste:

- usada somente para inspecao depois do rollback;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `overlayroot` desabilitado;
- pacote `overlayroot` instalado;
- servicos principais `active/enabled`;
- `public_state=display_missing` porque o HDMI estava na dev;
- `systemctl_failed_count=0`.

Nenhuma placa recebeu enable, reboot, poweroff, writer, alteracao de Wi-Fi ou
alteracao de config real nesta rodada.

## Diagnostico Tecnico

Achados sanitizados na placa teste:

- pacote `overlayroot` instalado;
- `overlayroot-chroot` existe;
- script initramfs do pacote existe;
- o initramfs contem o hook `overlayroot`;
- o initramfs contem modulo `overlay`;
- runtime do kernel suporta `overlay`;
- `uInitrd` existe e e usado pelo boot;
- `overlayroot.local.conf` nao existe;
- kernel cmdline nao contem `overlayroot`;
- `armbianEnv.txt` nao contem `overlayroot`;
- classificacao anterior persiste:

```text
initramfs_log_driver_lookup_failed=true
```

Interpretacao: o pacote e necessario, mas nao suficiente. O bloqueio esta na
integracao initramfs/uInitrd/boot desta base, nao em uma falta simples de pacote.

## Decisao

Nao repetir tentativa igual de enablement. Nao tentar novo enable na dev.

Decisao recomendada:

```text
root_read_only_mechanism_decision=c12_image_integrated_overlay_lab_required
next_allowed_step=C12.0-prep
ready_for_c11_4=false
```

O mecanismo aprovado continua sendo overlay/read-only, mas deve ser validado em
imagem/base de laboratorio C12, com pacote e initramfs gerados por codigo. Um
overlay proprio fica rejeitado por enquanto.

## O Que Continua Bloqueado

- C11.4;
- root read-only em placa funcional;
- corte seco;
- imagem final;
- power cut test.

## Proximo Passo

C12.0-prep deve preparar uma base de laboratorio com `overlayroot` integrado no
build e validar boot read-only antes de qualquer nova rodada em placa de
produto.
