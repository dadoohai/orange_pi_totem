# C12.2 - Gravacao Controlada da Image-Lab

Data: 2026-05-07

## Objetivo

Gravar a imagem-lab C12.1 em um cartao novo ou descartavel usando Armbian
Imager no Windows como ferramenta padrao. Esta rodada nao valida boot em placa,
nao provisiona config real e nao transforma a imagem em release final.

## Artefato Validado

Imagem:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img
```

SHA256 esperado e verificado antes do flash:

```text
1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2
```

Tambem foram confirmados:

- build log presente;
- package manifest presente;
- manifest image-lab atualizado;
- `overlayroot_included=true`;
- `initramfs_generated_after_overlayroot=true`;
- `card_written=true` apos boot inicial C12.3;
- `boards_touched=true` apos boot inicial C12.3.

## Ferramenta Padrao

C12.2 padroniza:

```text
Armbian Imager Windows
```

Fluxo manual:

1. abrir o Armbian Imager no Windows;
2. selecionar imagem local/customizada;
3. escolher o cartao novo ou descartavel correto;
4. confirmar que nao e o cartao dev danificado;
5. executar flash;
6. aguardar a verificacao do imager;
7. registrar o resultado de forma sanitizada.

Se a imagem for copiada para o Windows antes do flash, revalidar o SHA256 no
destino antes de gravar:

```powershell
Get-FileHash .\Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img -Algorithm SHA256
```

O valor deve ser exatamente:

```text
1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2
```

## Cartao Permitido

Usar somente:

- cartao novo; ou
- cartao descartavel de bancada.

Nao usar:

- cartao danificado da dev;
- cartao funcional da nova dev;
- cartao com dados que precisem ser preservados;
- cartao de origem duvidosa.

## Runner de Checklist

Foi criado:

```text
scripts/remote/run_c12_2_card_write_checklist.sh
```

Modos:

- `--prepare-only`;
- `--verify-image`;
- `--record-manual-flash`;
- `--summary`.

O runner nao acessa placas e nao grava cartao. Ele valida o artefato e registra
o resultado manual do Armbian Imager em `/tmp`, sem secrets.

Exemplo de registro depois do flash:

```bash
scripts/remote/run_c12_2_card_write_checklist.sh \
  --record-manual-flash \
  --flash-completed true \
  --imager-verification-completed true \
  --target-card-note "new disposable test card"
```

## Guardrails

- nenhuma placa tocada nesta preparacao;
- nao usar `192.168.18.122`;
- nao contornar KEX SSH legado;
- nao provisionar config real;
- nao gravar secrets;
- nao alterar Wi-Fi;
- nao gerar nova imagem;
- nao habilitar read-only em placa instalada;
- nao fazer corte seco.

## Proximo Passo

C12.3 iniciou apos a gravacao manual do cartao. A verificacao visual do Armbian
Imager nao ficou registrada, e o primeiro boot revelou duas pendencias antes da
validacao read-only: autoconfig/firstrun para remover first-login tecnico e
limpeza/recuperacao da sessao F10 quando o wizard aborta.
