# C12.1.5 - Firstboot Autoconfig Image Inspection

Data: 2026-05-07

## Objetivo

Auditar offline a imagem C12.1.4, explicar por que o autoconfig de laboratorio
nao foi efetivo no boot e corrigir build/validacao para preparar uma nova
imagem C12.1.6.

Nenhuma placa foi tocada e nenhum cartao foi gravado nesta auditoria.

## Achado Principal

A imagem C12.1.4 continha o arquivo privado de firstboot no rootfs:

```text
rootfs_firstboot_autoconfig_proven=true
```

Mas ela nao continha um servico autonomo de bootstrap lab:

```text
rootfs_lab_bootstrap_proven=false
ready_for_card_write_by_rootfs=false
```

O arquivo Armbian `/root/.not_logged_in_yet` e consumido pelo
`armbian-firstlogin`, que depende de login interativo. Ele nao aplica rede,
senha e usuario sozinho antes da UI Dadooh. Como o `totem-firstboot-gate` bloqueia
os servicos Dadooh enquanto esse marcador existe, a placa ficou no fallback de
bootstrap tecnico pendente.

## Correcao

Foi adicionado um bootstrap lab especifico para image-lab:

- `totem_lab_firstboot_autoconfig.sh`;
- `totem-lab-firstboot-autoconfig.service`;
- ordenacao antes de `totem-firstboot-gate.service`;
- aplicacao local de senha/usuario/rede de laboratorio a partir do arquivo
  privado;
- remocao do marcador `/root/.not_logged_in_yet` apos bootstrap;
- status sanitizado sem publicar valores.

## Validacao Endurecida

Foi criado `scripts/build/inspect_c12_image_rootfs.py` para inspecionar a imagem
offline. O validador de artefatos agora falha se nao provar no rootfs real:

- arquivo privado de firstboot presente;
- placeholders ausentes;
- campos obrigatorios presentes;
- gate presente;
- servico lab presente e enabled;
- servico lab ordenado antes do gate;
- `overlayroot` configurado;
- `/data`, `/tmp` e `/run` continuam politica de writable a validar no boot.

Validacao por manifest/flags sem rootfs nao basta mais para liberar gravacao.

## C12.1.6

A imagem C12.1.6 foi gerada com a correcao:

```text
rootfs_firstboot_autoconfig_proven=true
rootfs_lab_bootstrap_proven=true
ready_for_card_write_by_rootfs=true
```

SHA256:

```text
b64808a7ce23d7c19422c816ca558605d39b495019ecac0bb480345bff711a67
```

## Guardrails

- nenhum secret foi publicado;
- o conteudo do `firstboot.conf` privado nao entrou no Git;
- nenhuma placa foi tocada;
- nenhum cartao foi gravado;
- config real do player nao foi embutida;
- writer nao foi chamado;
- imagem final de producao continua bloqueada.

## Proximo Passo

C12.2.3 pode gravar a imagem C12.1.6 em cartao novo/descartavel para nova
validacao de boot.
