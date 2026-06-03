# 05 — Política de atualização

## 1. Objetivo

Evitar que atualizações não controladas invalidem a homologação da imagem do totem ou introduzam regressões em kernel, DTB, U-Boot, BSP, rede, vídeo ou filesystem.

A imagem Candidato A foi construída e validada inicialmente com uma composição específica:

```text
Armbian Build v25.11
Commit: e172058
Board: orangepizero3
Release: Debian Bookworm
Branch: current
Kernel: 6.12.58-current-sunxi64
U-Boot: 2025.04
Build: Minimal
Network stack: NetworkManager
BSPFREEZE: yes
```

## 2. Regra principal

Não executar em campo:

```bash
apt upgrade
apt full-upgrade
apt dist-upgrade
armbian-upgrade
```

Motivo: esses comandos podem alterar bibliotecas, serviços, pacotes Armbian, kernel, DTB, U-Boot ou BSP, invalidando a composição validada.

## 3. Permitido em bancada controlada

Durante validação, é aceitável executar:

```bash
apt update
apt-get install --no-upgrade -y <pacote-especifico>
```

Exemplo usado na triagem:

```bash
apt update
apt-get install --no-upgrade -y stress-ng
```

A opção `--no-upgrade` reduz o risco de atualizar pacotes já instalados.

## 4. Pacotes críticos devem permanecer em hold

Verificação:

```bash
apt-mark showhold
dpkg -l | grep -E "linux-image|linux-dtb|linux-u-boot|armbian-bsp"
```

No Candidato A, os pacotes críticos apareceram com status `hi`, indicando hold instalado:

```text
armbian-bsp-cli-orangepizero3-current
linux-dtb-current-sunxi64
linux-image-current-sunxi64
linux-u-boot-orangepizero3-current
```

## 5. Tipos de atualização

### 5.1 Conteúdo e configuração

Podem ser atualizados pelo backend e gravados em `/data`:

- playlist;
- mídias;
- ID de ambiente;
- posição da tela;
- parâmetros operacionais;
- fila de telemetria.

### 5.2 Aplicação

Nota C18: o contrato vigente e [UPDATE_CONTRACT.md](UPDATE_CONTRACT.md). O
layout abaixo e conceitual/historico. OTA comum atual usa
`/data/core/totem/current` somente para `totem-core`; o caminho
`/data/apps/kiosky-player/current` e legado/congelado na C18 e nao libera OTA
de `kiosky-player`.

Deve usar release versionada, com rollback:

```text
/opt/totem/releases/app-1.2.3
/opt/totem/current -> /opt/totem/releases/app-1.2.3
```

O serviço systemd deve apontar para `/opt/totem/current`.

### 5.3 Sistema operacional

Atualizações de sistema devem gerar nova imagem, nova homologação e nova release.

### 5.4 Kernel, DTB, U-Boot, BSP

Só atualizar em bancada, com matriz completa de testes. Nunca via upgrade livre em campo.

## 6. Direção futura

Para frota maior, avaliar atualização A/B com Mender ou RAUC. Até lá, adotar:

- app update com rollback;
- imagem completa versionada;
- diagnóstico remoto;
- kernel/DTB/U-Boot congelados.
