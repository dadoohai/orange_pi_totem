# Testes iniciais e evidências — Candidato A

**Imagem:** Armbian-unofficial 25.11.1 / Orange Pi Zero3 / Bookworm Minimal / current 6.12.58  
**Data dos testes iniciais:** 2026-04-28  
**Status:** boot inicial e bateria curta de reboots aprovados

---

## 1. Objetivo dos testes iniciais

Os testes iniciais tiveram como foco validar os pontos mais críticos derivados do problema original:

- cartão SD básico confiável;
- boot limpo;
- kernel correto;
- ausência de `Internal error: Oops`;
- ausência de `kernel panic`;
- ausência de erro EXT4;
- ausência de `mmc timeout/reset`;
- serviços sem falha;
- RAM detectada corretamente;
- reboot limpo, porque o produto reinicia diariamente.

Esses testes ainda não validam a aplicação, vídeo, Wi‑Fi de campo, hotspot, download de mídia, root read-only ou corte seco.

---

## 2. Teste de cartão — H2testw

Resultado informado:

```text
Warning: Only 30107 of 30108 MByte tested.
Test finished without errors.
You can now delete the test files *.h2w or verify them again.
Writing speed: 17.7 MByte/s
Reading speed: 17.9 MByte/s
H2testw v1.4
```

Interpretação:

- cartão aprovado para prosseguir;
- sem evidência de capacidade falsa ou erro leitura/escrita no espaço testado;
- velocidade compatível com microSD comum;
- não garante robustez contra corte de energia, mas remove a suspeita imediata de cartão ruim.

---

## 3. Boot inicial — observações do banner

Após gravar a imagem, o sistema bootou e exibiu:

```text
v25.11.1 for Orange Pi Zero3 running Armbian Linux 6.12.58-current-sunxi64
Packages: Debian rolling (bookworm)
Updates: Kernel upgrade disabled and 1 package available for upgrade
Support: DIY (custom image)
IPv4: 192.168.18.114
Memory usage: 8% of 1.93G
CPU temp: 52°C
Usage of /: 5% of 29G
```

Interpretação:

- versão do kernel correta;
- imagem customizada, não oficial pronta;
- kernel upgrade desabilitado por `BSPFREEZE=yes`;
- RAM coerente com placa de 2 GB;
- root expandido para o cartão;
- temperatura inicial normal para boot/idle.

---

## 4. Diagnóstico inicial coletado

### Kernel

```bash
uname -a
```

Resultado:

```text
Linux orangepizero3 6.12.58-current-sunxi64 #4 SMP Thu Nov 13 20:34:41 UTC 2025 aarch64 GNU/Linux
```

Validação: correto.

---

### Armbian release

```bash
cat /etc/armbian-release
```

Trechos relevantes:

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

Validação:

- board correto;
- commit correto;
- imagem user-built;
- board tipo `csc`, coerente com status Community;
- branch current.

---

### Pacotes críticos

```bash
dpkg -l | grep -E "linux-image|linux-dtb|linux-u-boot|armbian-bsp"
```

Resultado:

```text
hi  armbian-bsp-cli-orangepizero3-current 25.11.1
hi  linux-dtb-current-sunxi64             25.11.1
hi  linux-image-current-sunxi64           25.11.1
hi  linux-u-boot-orangepizero3-current    25.11.1
```

Validação:

- `linux-image-current-sunxi64`: presente;
- `linux-dtb-current-sunxi64`: presente;
- `linux-u-boot-orangepizero3-current`: presente;
- `armbian-bsp`: presente;
- status `hi` confirma hold/congelamento.

---

### Kernel tainted

```bash
cat /proc/sys/kernel/tainted
```

Resultado:

```text
1024
```

Interpretação:

- valor constante nos testes;
- provável driver staging/proprietário, compatível com Wi‑Fi/Bluetooth UWE5622/AW859A;
- não foi acompanhado de `Oops` ou `panic`;
- deve ser monitorado, mas não reprova a imagem.

Observação: o valor importante a evitar seria taint decorrente de kernel Oops. Nesta etapa não apareceu Oops.

---

### Memória

```bash
free -h
```

Resultado:

```text
Mem.: 1,9Gi
Swap: 987Mi
```

Validação: coerente com placa de 2 GB.

---

### Blocos e filesystem

```bash
lsblk -f
```

Resultado relevante:

```text
mmcblk0p1 ext4 armbi_root ... /var/log.hdd /
zram0 [SWAP]
zram1 /var/log
```

```bash
df -h
```

Resultado:

```text
/dev/mmcblk0p1 29G 1,2G 28G 5% /
/dev/zram1 47M 1012K 43M 3% /var/log
```

Validação:

- root em ext4 no microSD;
- partição expandida;
- `/var/log` em zram, reduzindo escrita no SD;
- ainda não é root read-only.

---

### Serviços falhados

```bash
systemctl --failed
```

Resultado:

```text
0 loaded units listed.
```

Validação: aprovado.

---

## 5. Filtro inicial de kernel

Comando:

```bash
journalctl -k -b --no-pager | grep -iE "oops|panic|tainted|ext4|mmc|i/o|timeout|reset|thermal|voltage|fail|error"
```

Não apareceram os bloqueadores críticos:

```text
Internal error: Oops
Kernel panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout
mmc reset
```

Apareceram mensagens de atenção:

```text
dw-apb-uart ... Error applying setting, reverse things back
sun6i-spi ... Error applying setting, reverse things back
sunxi-mmc ... Error applying setting, reverse things back
Bluetooth: hci0: Opcode 0x0c03 failed: -110
```

Interpretação:

- As mensagens `Error applying setting` não bloquearam boot, SD, mount ou rede. Ficam em observação.
- A mensagem de Bluetooth é repetitiva. Se Bluetooth não for usado, deve ser desabilitado na imagem final.

---

## 6. Repositórios APT

`/etc/apt/sources.list` não existia, mas fontes estavam em `.sources`:

```text
/etc/apt/sources.list.d/armbian-config.sources
/etc/apt/sources.list.d/armbian.sources
/etc/apt/sources.list.d/debian.sources
```

Trechos:

```text
URIs: http://apt.armbian.com
Suites: bookworm
Components: main bookworm-utils bookworm-desktop
```

```text
URIs: http://deb.debian.org/debian
Suites: bookworm bookworm-updates bookworm-backports
Components: main contrib non-free non-free-firmware
```

```text
URIs: http://security.debian.org/
Suites: bookworm-security
```

Interpretação:

- Apesar do banner exibir “Debian rolling (bookworm)”, os repositórios estão em Bookworm/Bookworm updates/backports/security.
- Não apareceu `sid`, `unstable`, `trixie` rolling ou `edge`.
- Não é a rolling release que foi descartada.

---

## 7. Primeiro reboot limpo

Comando:

```bash
sync
systemctl reboot
```

A conexão SSH caiu normalmente e a placa voltou.

Após reboot:

```text
uptime: up 0 min
cat /proc/sys/kernel/tainted: 1024
systemctl --failed: 0 loaded units listed
```

Filtro do boot anterior e atual não mostrou Oops/panic/EXT4/mmc timeout. Apenas Bluetooth:

```text
Bluetooth: hci0: Opcode 0x0c03 failed: -110
```

Decisão: primeiro reboot aprovado.

---

## 8. Bateria curta de reboots

Foram realizados ciclos manuais de:

```bash
sync
systemctl reboot
```

Após cada reboot:

```bash
cat /proc/sys/kernel/tainted
systemctl --failed
journalctl -b -1 -k --no-pager | grep -iE "oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|Bluetooth: hci0" || true
```

Resultado repetido:

```text
tainted = 1024
systemctl --failed = 0 loaded units listed
Bluetooth: hci0: Opcode 0x0c03 failed: -110
```

Não apareceu:

```text
Oops
panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout
mmc reset
```

Interpretação:

- reboot limpo passou na triagem curta;
- o risco específico visto em relatos de reboot no `6.12.23` não apareceu no `6.12.58` nesta bateria curta;
- ainda não é homologação longa.

---

## 9. Pequena observação sobre hostname/DNS

Em alguns reboots, o primeiro `ssh root@orangepizero3` retornou:

```text
ssh: Could not resolve hostname orangepizero3
```

Na tentativa seguinte, conectou normalmente.

Interpretação:

- provável atraso de resolução local/mDNS/DNS após reboot;
- não é falha da placa nem do kernel;
- para produção, é melhor depender de IP, DHCP reservation, DNS controlado, hostname registrado ou agente que chama o backend, não de resolução local manual.

---

## 10. Status da imagem após testes iniciais

### Aprovado

- boot inicial;
- kernel correto;
- RAM correta;
- root expandido;
- kernel/DTB/U‑Boot/BSP em hold;
- sem serviços falhados;
- sem Oops;
- sem panic;
- sem erro EXT4;
- sem remount read-only;
- sem `mmc timeout/reset`;
- bateria curta de reboots.

### Atenção

- `tainted=1024`, provável driver staging;
- Bluetooth timeout repetitivo;
- mensagens `Error applying setting` em UART/SPI/MMC, sem impacto observado;
- ainda root gravável;
- ainda sem aplicação;
- ainda sem teste de vídeo;
- ainda sem teste Wi‑Fi de campo;
- ainda sem teste de corte seco.

---

## 11. Decisão desta fase

**Candidato A segue aprovado para próxima fase de testes.**

Ele não está homologado para produção, mas passou a triagem crítica inicial que era necessária para avançar.

---

## 12. Próximos testes recomendados

### 12.1 Rede e NetworkManager

```bash
ip -br addr
nmcli device status
nmcli connection show
rfkill list
journalctl -u NetworkManager -b --no-pager | tail -n 80
```

### 12.2 Stress leve CPU/RAM

```bash
apt update
apt install -y stress-ng
stress-ng --cpu 4 --vm 1 --vm-bytes 50% --timeout 30m --metrics-brief
```

Depois:

```bash
cat /proc/sys/kernel/tainted
systemctl --failed
journalctl -k -b --no-pager | grep -iE "oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|thermal|voltage|fail|error" || true
```

### 12.3 Temperatura

```bash
watch -n 5 'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null; free -h; df -h'
```

### 12.4 Vídeo

Instalar player mínimo e rodar playlist Full HD real por 4h, depois 24h, depois 72h.

### 12.5 Wi‑Fi

Testar:

- conectar em Wi‑Fi;
- reconectar após reboot;
- trocar rede;
- rede indisponível;
- voltar conexão;
- logs de NetworkManager.

### 12.6 Downloads e `/data`

Testar:

- download interrompido;
- arquivo `.tmp` não virar mídia final;
- rename atômico;
- `/data` quase cheio;
- boot com `/data/media` vazio;
- boot sem internet.

### 12.7 Corte seco

Só testar depois de:

- root read-only ativo;
- `/data` separado;
- downloads atômicos implementados;
- logs controlados.

---

## 13. Critérios de reprovação dos próximos testes

Reprovar se aparecer:

```text
Internal error: Oops
Kernel panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout
mmc reset grave
RAM detectada errada
travamento que exige power cycle
```

Alertas que não reprovam sozinhos, mas exigem registro:

```text
tainted=1024
Bluetooth timeout
Error applying setting, reverse things back
DNS local demora a resolver hostname
```

