# C12.1.1 - Artifact Preservation + Hardware Incident

Data: 2026-05-07

## Objetivo

Preservar o resultado C12.1 e registrar o incidente fisico observado no cartao
da placa dev, sem tocar nas placas e sem gravar novo cartao.

## Artefato C12.1

Imagem-lab preservada no caminho local:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img
```

SHA256 revalidado:

```text
1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2
```

Checks:

- `image_exists=true`;
- `checksum_ok=true`;
- `build_log_exists=true`;
- `package_manifest_exists=true`;
- `overlayroot_included=true`;
- `initramfs_generated_after_overlayroot=true`;
- `card_written=false`;
- `boards_touched=false`.

## Incidente Fisico

O cartao da placa dev apresentou fumaca/aquecimento e depois boot anormal com
mensagem envolvendo `/dev/mtdblock4`. Esse incidente deve ser tratado como
midia/hardware ate prova contraria, nao como falha de software do C12.1.

Politica imediata:

- nao usar o cartao danificado;
- tratar o cartao dev como perdido ou nao confiavel;
- considerar a placa dev nao confiavel ate reteste com cartao novo;
- nao tentar bootar novamente esse cartao;
- nao usar a placa dev como alvo C12.2.

## Interpretacao

C12.1 nao tocou placas, nao gravou cartao e nao alterou estado operacional da
dev/teste. O erro `/dev/mtdblock4` sugere rota de boot por MTD/NOR ou ausencia
da midia principal esperada, coerente com incidente fisico de cartao/contato/
alimentacao, nao com o artefato C12.1.

## Proximo Passo

C12.2 deve usar cartao novo ou descartavel e placa teste como alvo. A validacao
de read-only deve partir da imagem-lab preservada, nunca do cartao dev
danificado.
