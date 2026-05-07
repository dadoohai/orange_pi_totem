# C12.0-prep - Image-integrated Read-only Lab

Data: 2026-05-06

Status: plano criado. Nenhuma placa foi tocada, nenhuma imagem foi gerada e
nenhum cartao foi gravado.

## Objetivo

Transformar a decisao C11.3.4 em um plano de imagem-lab: validar root read-only
como parte da base/imagem gerada por codigo, em vez de tentar ativar
`overlayroot` depois que a placa ja esta provisionada.

## HEAD Auditado

O repo estava limpo e no HEAD:

```text
49778f6 Add C12.0 image read-only lab prep
```

## Por Que C11.3 Pos-instalacao Bloqueou

C11.3.1 provou que o pacote `overlayroot` pode ser instalado de forma controlada
sem upgrades/remocoes e sem tocar kernel/DTB/U-Boot/BSP. C11.3.2 e C11.3.3
provaram outro ponto: pacote instalado em placa ja provisionada nao basta.

Achados consolidados:

- `overlayroot` instalado;
- `overlayroot-chroot` presente;
- hook initramfs presente;
- modulo `overlay` presente;
- runtime do kernel suporta overlay;
- `uInitrd` presente;
- SSH voltou apos reboot de laboratorio;
- `read_only_enabled=false`;
- `overlay_active=false`;
- erro publico: `initramfs_log_driver_lookup_failed=true`.

Interpretacao: o bloqueio esta na integracao initramfs/uInitrd/boot desta base
instalada. O caminho correto volta para a estrategia original: imagem gerada por
codigo, com mecanismo read-only integrado durante o build.

## Plano C12.0-prep

C12.0-prep nao gera imagem. Ele define o alvo da imagem-lab:

1. recuperar ou preparar Armbian Build v25.11;
2. reproduzir a base conhecida do Candidato A;
3. criar `userpatches` de produto/read-only;
4. incluir `overlayroot` no build;
5. gerar initramfs e `uInitrd` ja com o mecanismo presente;
6. embutir scripts/units do appliance sem secrets;
7. manter config real fora da imagem;
8. criar manifesto e checklist de validacao;
9. so em C12.1 executar build.

## Como Armbian Build Deve Integrar o Mecanismo

Base esperada:

```text
Armbian Build v25.11
BOARD=orangepizero3
RELEASE=bookworm
BRANCH=current
BUILD_MINIMAL=yes
BUILD_DESKTOP=no
NETWORKING_STACK=network-manager
BSPFREEZE=yes
```

Integracao esperada:

- adicionar `overlayroot` como pacote de imagem, nao como conserto de placa;
- garantir que `update-initramfs`/geracao de `uInitrd` ocorra depois do pacote;
- versionar a configuracao de read-only da imagem-lab;
- incluir policy de journald volatil;
- criar `/data` e subpaths persistentes;
- instalar scripts/units do appliance;
- manter `kiosky-player` pelo pin ja definido;
- nao embutir `/data/config/config.json`, private-values, SSID, senha, API key,
  API URL real, environment real, midias/cache ou logs brutos.

## Manifesto Criado

Foi criado:

```text
releases/image-lab-readonly/manifest.md
```

Status principal:

- `image_built=false`;
- `card_written=false`;
- `boards_touched=false`;
- `read_only_enabled_on_installed_board=false`;
- `ready_for_c12_1_build=true`;
- `ready_for_c12_2_board_validation=false`;
- `ready_for_c11_4=false`.

## Runner/Checklist Futuro

Foi criado um runner local de checklist:

```text
scripts/remote/run_c12_1_image_lab_readonly_validation.sh
```

Ele nao acessa placas. Em C12.1/C12.2, deve ser expandido ou usado como gate
para validar:

- artefatos de imagem;
- checksum;
- build log;
- manifest de pacotes;
- ausencia de secrets;
- checklist de boot read-only em placa de teste.

## O Que Sera Necessario em C12.1

C12.1 deve preparar ambiente de build e produzir a primeira imagem-lab:

1. recuperar ou clonar Armbian Build v25.11;
2. confirmar commit/base do build;
3. criar `userpatches` versionados para appliance/read-only;
4. incluir pacote `overlayroot` no build;
5. incluir policy C11.2 de journald volatil;
6. incluir layout `/data`;
7. incluir appliance scripts/units sem secrets;
8. gerar imagem e checksums;
9. gerar log e manifest de pacotes;
10. nao gravar cartao ainda sem gate separado.

## Atualizacao C12.1

C12.1 executou o plano de imagem-lab sem tocar placas e sem gravar cartao.

Resultado:

- Armbian Build v25.11 em `e172058`;
- userpatches versionados em `scripts/build/userpatches-c12-image-lab/`;
- imagem gerada com sufixo `c12-ro-lab`;
- `overlayroot` incluido na imagem;
- `update-initramfs` executado depois da instalacao de `overlayroot`;
- checksum, build log, package manifest e integration manifest gerados;
- `card_written=false`;
- `boards_touched=false`;
- `final_image=false`.

O primeiro build encontrou pressao de memoria por rootfs em tmpfs. A solucao
foi desabilitar ramdisk para esta imagem-lab (`FORCE_USE_RAMDISK=no`) e repetir
o build em disco.

O proximo passo passa a ser C12.2: preparar e gravar um cartao de teste com a
imagem-lab para validar boot, overlay ativo, root protegido, `/data`, `/tmp` e
`/run` gravaveis, player e F10.

## Resposta Operacional

Neste momento, a acao correta e:

```text
A. preparar ambiente de build
C. recuperar scripts Armbian Build antigos
```

Tambem sera necessario preparar cartao de teste, mas apenas depois que C12.1
produzir uma imagem-lab e seus checksums. Nao ha bloqueio novo antes de C12.1,
alem de localizar/preparar o ambiente Armbian Build e transformar os scripts de
instalacao atuais em `userpatches` de imagem.

## Guardrails Mantidos

- placas dev/teste nao tocadas;
- nenhuma imagem final gerada;
- nenhum cartao gravado;
- read-only nao habilitado em placa instalada;
- nenhuma tentativa nova de `overlayroot` pos-instalacao;
- config real, writer, Wi-Fi e NetworkManager nao alterados;
- sem secrets ou logs brutos publicados.
