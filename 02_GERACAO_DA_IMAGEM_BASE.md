# Geração da imagem base — Armbian Build v25.11 / Orange Pi Zero 3

**Data da execução:** 2026-04-28  
**Imagem gerada:** Candidato A  
**Status:** gerada, gravada, bootada e aprovada nos testes iniciais de boot/reboot

---

## 1. Objetivo

Gerar uma imagem própria e reproduzível para Orange Pi Zero 3, abandonando o processo antigo de clonagem de cartão.

A imagem deveria atender aos seguintes critérios iniciais:

```text
Armbian Build v25.11
BOARD=orangepizero3
Debian Bookworm
Minimal/IOT
BRANCH=current
Kernel esperado: 6.12.58-current-sunxi64
U-Boot esperado: 2025.04
NetworkManager
BSPFREEZE=yes
sem Desktop
```

---

## 2. Ambiente de geração

### Host

Windows 11 com WSL2.

Versão informada:

```text
Versão do WSL: 2.6.3.0
Versão do kernel: 6.6.87.2-1
Versão do WSLg: 1.0.71
Versão do Windows: 10.0.26100.8246
```

Distro WSL:

```text
Ubuntu 24.04.1 LTS
```

Recursos medidos:

```text
Filesystem: /dev/sdd
Tamanho: 251G
Usado: 36G
Livre: 203G
RAM: 9.7Gi
Swap: 3.0Gi
CPUs: 8
```

Esse ambiente atende ao requisito prático do Armbian Build: Ubuntu 24.04/WSL2, pelo menos 8 GB de RAM e espaço livre suficiente.

---

## 3. Usuário de build

Foi criado usuário dedicado:

```bash
adduser builder
usermod -aG sudo builder
su - builder
```

A partir daí, o build foi conduzido como `builder`, não como root.

---

## 4. Instalação de ferramentas básicas

Foram instalados pacotes básicos:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates xz-utils zstd pv jq nano nodejs npm
```

---

## 5. Instalação e uso do Codex

O Codex foi instalado via npm:

```bash
mkdir -p ~/.npm-global
npm config set prefix ~/.npm-global
echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.bashrc
export PATH="$HOME/.npm-global/bin:$PATH"
npm install -g @openai/codex
codex --version
```

Versão observada:

```text
OpenAI Codex v0.125.0
model: gpt-5.5
```

Uso definido:

- Codex como agente auxiliar de inspeção;
- sem executar comandos destrutivos;
- sem mexer em `/dev/*`;
- sem `dd`, `wipefs`, `mkfs`, `fdisk`, `parted`;
- sem gravar cartão pelo WSL.

---

## 6. Clonagem do Armbian Build

Comando usado:

```bash
mkdir -p ~/totem-os
cd ~/totem-os

git clone --depth=1 --branch=v25.11 https://github.com/armbian/build armbian-build-v25.11
cd armbian-build-v25.11

git status
git rev-parse --short HEAD
```

Resultado:

```text
On branch v25.11
working tree clean
commit: e172058
```

Esse commit ficou registrado no `/etc/armbian-release` da imagem bootada:

```text
BUILD_REPOSITORY_COMMIT=e172058
```

---

## 7. Conferência da configuração com Codex

O Codex foi usado para inspecionar os arquivos do Armbian Build v25.11. Resultado da revisão:

```text
orangepizero3 tem KERNEL_TARGET="current,edge"
BOOTBRANCH="tag:v2025.04"
BOOTPATCHDIR="v2025-sunxi"
extensão enable_extension "uwe5622-allwinner"
BRANCH=current -> KERNELBRANCH="tag:v6.12.58"
BRANCH=legacy -> KERNELBRANCH="tag:v6.6.75"
```

Interpretação:

- `current` é alvo válido para Orange Pi Zero3.
- `legacy` existe na família `sunxi64`, mas não é alvo válido por padrão para essa placa.
- `current` no v25.11 corresponde ao kernel 6.12.58.
- A placa usa U‑Boot v2025.04.
- A extensão Wi‑Fi/Bluetooth UWE5622/AW859A está habilitada.

---

## 8. Tentativa inicial de build nativo e problema encontrado

Primeira tentativa:

```bash
./compile.sh build \
  EXPERT=yes \
  BOARD=orangepizero3 \
  RELEASE=bookworm \
  BRANCH=current \
  BUILD_MINIMAL=yes \
  BUILD_DESKTOP=no \
  KERNEL_CONFIGURE=no \
  NETWORKING_STACK=network-manager \
  BSPFREEZE=yes \
  PREFER_DOCKER=no
```

Erro encontrado:

```text
Detected WSL2 - experimental support
Please use a terminal that supports UTF-8
Problem detected: WSL2 Terminal does not support UTF-8
Exiting with error 43
```

Interpretação:

- Não foi erro da imagem nem do kernel.
- O build foi interrompido antes de compilar, por checagem de terminal/UTF‑8.
- O caminho correto passou a ser ajustar ambiente e usar Docker/UTF‑8.

---

## 9. Ajuste de ambiente

Foram usados exports para garantir ambiente UTF‑8:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export TERM=xterm-256color
```

Também foi decidido usar Docker, alinhado ao método suportado pelo Armbian Build.

Na prática, o build final foi executado com:

```bash
PREFER_DOCKER=yes
```

Embora o método oficialmente descrito também aceite `./compile.sh docker ...`, o resultado final foi uma imagem válida, gerada com o conjunto esperado.

---

## 10. Comando de build usado

Comando final executado:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export TERM=xterm-256color

cd ~/totem-os/armbian-build-v25.11

./compile.sh build \
  EXPERT=yes \
  BOARD=orangepizero3 \
  RELEASE=bookworm \
  BRANCH=current \
  BUILD_MINIMAL=yes \
  BUILD_DESKTOP=no \
  KERNEL_CONFIGURE=no \
  NETWORKING_STACK=network-manager \
  BSPFREEZE=yes \
  PREFER_DOCKER=yes
```

Observação: futuramente, para padronização documental, recomenda-se usar preferencialmente:

```bash
./compile.sh docker \
  EXPERT=yes \
  BOARD=orangepizero3 \
  RELEASE=bookworm \
  BRANCH=current \
  BUILD_MINIMAL=yes \
  BUILD_DESKTOP=no \
  KERNEL_CONFIGURE=no \
  NETWORKING_STACK=network-manager \
  BSPFREEZE=yes
```

---

## 11. Imagem gerada

Saída de `output/images`:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img.sha
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img.txt
```

Tamanho:

```text
1.4G
```

A imagem não foi compactada como `.xz` nesta execução. Isso não é problema; o Armbian Imager conseguiu gravar `.img` local.

---

## 12. Pacotes críticos gerados

Comando:

```bash
find output/debs -type f | grep -E "linux-image|linux-dtb|linux-u-boot|armbian-bsp" | sort
```

Resultado relevante:

```text
output/debs/armbian-bsp-cli-orangepizero3-current_25.11.1_arm64__1-PC6386-V7289-Hc65c-Bb0b9-Rf36a.deb
output/debs/armbian-bsp-cli-orangepizero3_25.11.1_arm64__1-PC6386-V7289-Hc65c-Bb0b9-Rf36a.deb
output/debs/linux-dtb-current-sunxi64_25.11.1_arm64__6.12.58-S7475-Deeea-P4795-Cd434Hb74f-HK01ba-Vc222-B2135-R448a.deb
output/debs/linux-image-current-sunxi64_25.11.1_arm64__6.12.58-S7475-Deeea-P4795-Cd434Hb74f-HK01ba-Vc222-B2135-R448a.deb
output/debs/linux-u-boot-orangepizero3-current_25.11.1_arm64__2025.04-S3482-Pf089-H8869-V1f74-Bbf55-R448a.deb
```

Validação:

- kernel: 6.12.58;
- DTB: 6.12.58;
- U‑Boot: 2025.04;
- BSP da placa: presente.

---

## 13. Checksums

Comandos:

```bash
cd ~/totem-os/armbian-build-v25.11/output/images
sha256sum * > SHA256SUMS-local.txt
cat SHA256SUMS-local.txt
```

SHA256 principal:

```text
99fce7ad04f9c6529655d2d6f8568d5a484c05bdcbdf679e3423a5e7241894e7  Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img
```

Outros:

```text
ca380133728e05754391d43afc2b747465c6b9665b8f9b3b887da20303f60b71  .img.sha
e075385dd4a39b5d6bcb647083ebd01db6e6b8cf41f9efa701da9b734d3b6c7c  .img.txt
```

---

## 14. Cópia para Windows

Comando:

```bash
mkdir -p /mnt/c/Users/felip/Downloads/totem-os-images
cp -v * /mnt/c/Users/felip/Downloads/totem-os-images/
```

Destino:

```text
C:\Users\felip\Downloads\totem-os-images
```

---

## 15. Gravação no cartão

A imagem foi gravada a partir do Windows, usando imagem local.

Decisão: não usar `dd` pelo WSL para gravar no cartão neste momento. Motivos:

- reduz risco operacional;
- evita confusão de device path no WSL;
- mantém o fluxo acessível;
- permite usar ferramenta com verificação visual.

---

## 16. Primeiro boot

A imagem bootou com sucesso.

Banner observado:

```text
v25.11.1 for Orange Pi Zero3 running Armbian Linux 6.12.58-current-sunxi64
Packages: Debian rolling (bookworm)
Updates: Kernel upgrade disabled and 1 package available for upgrade
Support: DIY (custom image)
Memory usage: 8% of 1.93G
Usage of /: 5% of 29G
```

Interpretação:

- imagem customizada correta;
- kernel correto;
- upgrade de kernel desabilitado;
- RAM coerente com placa 2 GB;
- root expandido para cartão;
- `DIY/custom image` esperado para build próprio.

---

## 17. Conteúdo confirmado na placa

### `uname -a`

```text
Linux orangepizero3 6.12.58-current-sunxi64 #4 SMP Thu Nov 13 20:34:41 UTC 2025 aarch64 GNU/Linux
```

### `/etc/armbian-release`

Pontos importantes:

```text
BOARD=orangepizero3
BOARD_NAME="Orange Pi Zero3"
BOARDFAMILY=sun50iw9
BUILD_REPOSITORY_COMMIT=e172058
LINUXFAMILY=sunxi64
IMAGE_TYPE=user-built
BOARD_TYPE=csc
KERNEL_TARGET=current,edge
VERSION=25.11.1
BRANCH=current
```

### Pacotes críticos

```text
hi  armbian-bsp-cli-orangepizero3-current 25.11.1
hi  linux-dtb-current-sunxi64             25.11.1
hi  linux-image-current-sunxi64           25.11.1
hi  linux-u-boot-orangepizero3-current    25.11.1
```

O status `hi` confirma hold dos pacotes críticos.

---

## 18. Problemas resolvidos durante o processo

### Problema 1 — pasta inicial inadequada

O processo começou em:

```text
/mnt/c/Users/felip/Downloads/Nova pasta (2)
```

Esse caminho contém espaços e parênteses. Foi decidido mover o trabalho para:

```text
/home/builder/totem-os
```

### Problema 2 — build como root

Inicialmente o WSL estava como root. Criamos usuário `builder` para isolar o ambiente.

### Problema 3 — terminal/UTF‑8

A primeira tentativa abortou com erro 43. Solução aplicada:

```bash
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export TERM=xterm-256color
```

Além disso, a recomendação operacional ficou: usar Windows Terminal e Docker para builds futuros.

### Problema 4 — escolha Docker

Havia dúvida entre `PREFER_DOCKER=yes` e `./compile.sh docker`. A execução com `PREFER_DOCKER=yes` funcionou. Para futuras reproduções, recomenda-se padronizar em `./compile.sh docker`, porque é a forma documentada de modo Docker.

### Problema 5 — Codex criou `.codex` no repositório

Foi observado que Codex poderia criar metadados locais. Recomendação:

```bash
rm -rf .codex
git status --short
```

antes do build.

---

## 19. Comando recomendado para reprodução futura

Em uma execução futura limpa, usar:

```bash
cd ~/totem-os

git clone --depth=1 --branch=v25.11 https://github.com/armbian/build armbian-build-v25.11
cd armbian-build-v25.11

export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export TERM=xterm-256color

./compile.sh docker \
  EXPERT=yes \
  BOARD=orangepizero3 \
  RELEASE=bookworm \
  BRANCH=current \
  BUILD_MINIMAL=yes \
  BUILD_DESKTOP=no \
  KERNEL_CONFIGURE=no \
  NETWORKING_STACK=network-manager \
  BSPFREEZE=yes
```

Para capturar log:

```bash
mkdir -p ~/totem-os/logs
script -af ~/totem-os/logs/build-A-v25.11-current-docker.log
# rodar build aqui
exit
```

---

## 20. Próxima evolução da imagem

A imagem gerada ainda é base. Ela ainda não contém:

- aplicação principal;
- player configurado;
- modo manutenção;
- hotspot de configuração;
- estrutura `/data` final;
- scripts de diagnóstico;
- política de atualização da aplicação;
- root read-only.

Esses elementos devem entrar em uma nova imagem de produto, via:

```text
userpatches/overlay
userpatches/customize-image.sh
systemd units
scripts versionados
```

A placa não deve ser configurada manualmente e depois clonada. A personalização deve estar no repositório.
