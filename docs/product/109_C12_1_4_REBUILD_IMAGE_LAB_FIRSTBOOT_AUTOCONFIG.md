# C12.1.4 - Rebuild Image-Lab com Firstboot Autoconfig

Data: 2026-05-07

## Objetivo

Gerar uma nova imagem-lab bootavel em laboratorio com `firstboot.conf` privado
fora do Git, garantindo caminho de SSH/rede/diagnostico no primeiro boot e
evitando o bloqueio de tela preta/console cru observado em C12.3.2.

## Resultado

C12.1.4 passou como build de artefato local.

O arquivo privado foi validado sem imprimir valores:

- `file_exists=true`;
- `file_secure=true`;
- `parent_secure=true`;
- `owner_current_user=true`;
- `is_symlink=false`;
- `outside_repo=true`;
- `placeholders_present=false`;
- `required_fields_present=true`;
- `network_path_present=true`;
- `can_build_with_lab_firstboot=true`.

O build foi executado com:

```text
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF=/tmp/dadooh-c12-lab-firstboot/firstboot.conf
```

O conteudo do arquivo privado nao foi impresso, copiado para o Git ou registrado
em evidencia.

## Artefatos

Imagem C12.1.4:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-4_minimal.img
```

SHA256:

```text
405d4891e62d018862008f3bfdf00e02123b551351655147ec7448b803ccca14
```

Artefatos relacionados:

- checksum: imagem `.sha256`;
- build log: `log-build-7f1e148a-583b-48af-b701-1fc2396d067b.log`;
- package manifest: `releases/image-lab-readonly/package-manifest-c12-1-4.txt`;
- integration manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-4.txt`.

## Integracao

Validado nos artefatos:

- `overlayroot_included=true`;
- `initramfs_generated_after_overlayroot=true`;
- `initramfs_source=cache_hit_with_overlayroot_hooks`;
- `firstboot_gate_included=true`;
- `lab_firstboot_autoconfig=true`;
- `lab_firstboot_boot_validatable=true`;
- `open_settings_cleanup_included=true`;
- `read_only_assertion_required=true`;
- `card_written=false`;
- `boards_touched=false`.

## C12.1.2

A imagem C12.1.2 continua bloqueada/superseded por C12.3.2:

```text
firstboot_bootstrap_missing_or_invalid
```

Ela nao deve ser reutilizada para boot validation.

## Guardrails

- nenhuma placa foi tocada;
- nenhum cartao foi gravado;
- nenhum secret foi publicado;
- o conteudo do `firstboot.conf` privado nao foi impresso;
- config real do player nao foi embutida;
- writer nao foi chamado;
- Wi-Fi/NetworkManager de placa nao foram alterados;
- imagem final de producao continua bloqueada.

## Atualizacao C12.3.3

A C12.1.4 foi gravada e bootada, mas mostrou o fallback:

```text
Bootstrap tecnico pendente
```

Isso reclassifica C12.1.4 como bloqueada para boot validation. A imagem continha
o arquivo privado, mas nao tinha um bootstrap lab autonomo para aplica-lo antes
do `totem-firstboot-gate`.

Classificacao:

```text
lab_firstboot_autoconfig_not_effective
```

## Proximo Passo

C12.1.5 deve corrigir build/validacao e gerar C12.1.6. A C12.1.4 nao deve ser
reutilizada para nova boot validation.

## Atualizacao C12.1.8

C12.1.6 resolveu o bootstrap lab, mas C12.3.4 mostrou root ainda `ext4 rw`.
C12.1.7 classificou a causa como `UINITRD_NOT_UPDATED`. C12.1.8 reconstruiu a
imagem-lab com validacao do initramfs efetivo do boot:

- `uinitrd_nonempty=true`;
- `uinitrd_payload_matches_initrd_img=true`;
- `effective_boot_initramfs_valid=true`.

A imagem C12.1.8 substitui C12.1.6 para a proxima gravacao de cartao.
