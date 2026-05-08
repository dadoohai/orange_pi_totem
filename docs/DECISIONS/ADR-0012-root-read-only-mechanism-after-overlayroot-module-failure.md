# ADR-0012 - Root Read-only After Overlayroot Module Failure

Data: 2026-05-08

Status: aceito para proximo experimento de imagem-lab.

## Contexto

O projeto continua exigindo root read-only/overlay validado antes de C12.4,
provisionamento real, corte seco ou imagem final. A decisao ADR-0011 moveu o
experimento para imagem/base gerada por codigo e manteve `overlayroot` como
mecanismo esperado do Armbian.

Entre C12.3.6 e C12.3.15, a linha investigada foi:

```text
overlayroot oficial + overlay.ko carregado como modulo dentro do initramfs
```

Essa linha foi explorada em placa lab descartavel, sem tocar a dev, sem
provisionar config real e sem publicar logs brutos.

## Resumo das Tentativas

C12.3.6 provou que `overlayroot=tmpfs` precisa chegar ao cmdline para o hook
rodar, mas o root continuou `ext4`.

C12.3.7 adicionou `overlay` a `/etc/initramfs-tools/modules` e depois um hook
`init-top` com `modprobe overlay`; ambos entraram no initramfs, mas o overlay
nao registrou.

C12.3.8 confirmou que o `uInitrd` efetivo continha `overlayroot`, `overlay.ko`,
`modules.dep`, `modules.alias`, `modprobe` e hook auxiliar, mas `overlay` nao
aparecia em `/proc/filesystems`.

C12.3.9 a C12.3.11 refinaram o problema para caminho efetivo de modulo e
falhas de `insmod`.

C12.1.10 corrigiu resolucao dinamica de path no artefato. C12.3.12 ainda
falhou em boot real.

C12.3.13 mostrou que o modulo podia aparecer vazio/stub no initramfs.

C12.3.14 provou que `overlay.ko` real e `modules.dep` coerente entram no
initramfs, mas isso ainda nao ativa o overlay.

C12.3.15 confirmou que, mesmo com modulo real, nao vazio, sem dependencias
declaradas e `vermagic` compativel no ambiente pos-boot, `modprobe overlay`
retorna zero no initramfs sem registrar `overlay`; `insmod overlay.ko` retorna
nonzero sem stderr/dmesg categorizavel.

## Decisao

Encerrar a linha incremental de carregar `overlay.ko` como modulo no
initramfs.

Manter `overlayroot` como mecanismo oficial/esperado, mas o proximo experimento
de imagem-lab deve compilar o kernel com:

```text
CONFIG_OVERLAY_FS=y
```

Isso torna `overlayfs` built-in no kernel e remove a dependencia de
`modprobe`, `insmod` e `modules.dep` exatamente na fase em que a linha anterior
falhou.

Essa decisao vale apenas para image-lab. Nao marca imagem final, nao libera
C12.4 e nao autoriza provisionamento real.

## Consequencias

- C12.4 permanece bloqueado.
- C12.1.11 deve gerar uma nova image-lab com userpatch de kernel completo.
- O userpatch esperado pelo Armbian Build e `linux-sunxi64-current.config`.
- O arquivo deve ser completo, derivado de
  `config/kernel/linux-sunxi64-current.config`, nao fragmento parcial.
- O build deve manter `overlayroot=tmpfs`, firstboot lab autoconfig, journald
  volatil, layout `/data` e ausencia de secrets.
- A validacao nao deve mais exigir `root_write_blocked=true` no merged root.

## Criterios de Sucesso

Boot real da image-lab deve provar:

- `overlay_active=true`;
- root montado como `overlay` ou equivalente;
- `overlay` listado em `/proc/filesystems`;
- lower/root fisico protegido ou read-only quando detectavel;
- escrita de teste fora de `/data` pode ser criada, mas nao persiste apos
  reboot;
- escrita de teste em `/data` persiste apos reboot;
- `/data`, `/tmp` e `/run` continuam gravaveis;
- `journald_volatile=true`;
- `readonly_semantics_valid=true`.

## Rollback

O rollback e por imagem/cartao, nao por patch em placa instalada: se o boot da
image-lab com kernel built-in falhar, gravar novamente a imagem anterior
conhecida ou recuperar offline o cartao de laboratorio. A dev funcional
continua fora desta rodada.

## Proximo Passo Permitido

```text
next_allowed_step=C12.1.11_BUILD_IMAGE_LAB_WITH_CONFIG_OVERLAY_FS_BUILTIN
ready_for_c12_4=false
```
