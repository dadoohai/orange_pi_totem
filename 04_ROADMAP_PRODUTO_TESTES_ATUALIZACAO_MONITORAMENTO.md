# Roadmap de produto, testes, atualização e monitoramento

**Projeto:** Totem Orange Pi Zero 3  
**Base atual:** Candidato A — Armbian Build v25.11 / Bookworm Minimal / kernel 6.12.58  
**Status:** boot e reboots iniciais aprovados; próximos passos envolvem carga, aplicação, `/data`, read-only e operação remota.

---

## 1. Visão geral do roadmap

A fundação técnica foi iniciada, mas o produto ainda não está pronto para campo. A sequência recomendada é:

```text
1. Finalizar triagem da base A
2. Automatizar diagnóstico e healthcheck
3. Mapear aplicação Python
4. Definir layout /data
5. Criar imagem produto v0.1
6. Testar player/vídeo/rede
7. Ativar root read-only
8. Testar corte seco
9. Definir atualização de app
10. Definir atualização de sistema
11. Criar telemetria e comandos remotos
12. Rodar piloto de campo
```

---

## 2. Fase 1 — Finalizar triagem da base A

### Objetivo

Confirmar que a base limpa não apresenta falhas de kernel, filesystem, SD, serviços, rede ou temperatura sob carga básica.

### Já realizado

- H2testw aprovado.
- Boot inicial aprovado.
- Reboots curtos aprovados.
- Sem Oops/panic/EXT4/mmc timeout.
- Kernel e U‑Boot corretos.
- Pacotes críticos em hold.

### Ainda fazer

#### Rede

```bash
ip -br addr
nmcli device status
nmcli connection show
rfkill list
journalctl -u NetworkManager -b --no-pager | tail -n 80
```

#### Stress CPU/RAM

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

#### Temperatura

```bash
watch -n 5 'cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null; free -h; df -h'
```

### Critério de aprovação

- sem Oops;
- sem panic;
- sem EXT4 error;
- sem mmc timeout/reset;
- sem serviço falhado;
- temperatura aceitável;
- rede estável;
- boot/reboot estáveis.

---

## 3. Fase 2 — Automatizar diagnóstico e healthcheck

### Objetivo

Criar ferramentas simples para coletar evidências sempre que a placa apresentar problema.

### Scripts recomendados

```text
/usr/local/bin/totem-healthcheck
/usr/local/bin/totem-diag-pack
/usr/local/bin/totem-logscan
/usr/local/bin/totem-test-reboot
```

### `totem-healthcheck` deve coletar

```text
data/hora
hostname
device_id
versão da imagem
versão do app
uname -a
/etc/armbian-release
apt-mark showhold
pacotes kernel/dtb/u-boot/bsp
cat /proc/sys/kernel/tainted
free -h
df -h
lsblk -f
ip -br addr
nmcli device status
systemctl --failed
temperatura
últimos erros do kernel
últimos erros do app
```

### Assinaturas de erro a procurar

```text
Internal error: Oops
Kernel panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout
mmc reset
I/O error
Out of memory
segfault
thermal throttling
```

### Papel do Codex

O Codex deve ajudar a gerar e revisar esses scripts no repositório do produto. Ele deve operar preferencialmente no PC/WSL, não na placa como ambiente principal de desenvolvimento.

Prompt recomendado para o Codex:

```text
Você é meu agente auxiliar para criar scripts de diagnóstico de um totem Orange Pi Zero 3.
Não use comandos destrutivos.
Crie scripts shell idempotentes para coletar estado de kernel, filesystem, rede, disco, RAM, temperatura, serviços e logs críticos.
O objetivo é gerar um pacote .tar.gz de diagnóstico e um resumo legível.
```

---

## 4. Fase 3 — Mapear aplicação Python

### Objetivo

Entender exatamente onde a aplicação escreve, baixa, lê, cacheia e falha.

### Perguntas obrigatórias

- Onde a aplicação salva configuração?
- Onde salva ID do ambiente?
- Onde salva posição de tela?
- Onde salva mídias?
- Como faz download?
- Usa `.tmp` durante download?
- Faz hash/tamanho antes de promover arquivo final?
- Onde salva telemetria pendente?
- Onde salva logs?
- O que acontece sem internet?
- O que acontece sem mídia?
- O que acontece se o endpoint falhar?
- O que acontece se a tela não for reconhecida?

### Prompt recomendado para Codex no repositório da aplicação

```text
Você está no repositório da aplicação Python de um totem Orange Pi Zero 3.
Não altere arquivos ainda.
Mapeie todos os pontos de escrita em disco, download de mídia, persistência de configuração, telemetria e logs.
Classifique cada escrita em: persistente necessária, temporária, cache, log, mídia, configuração, risco em corte de energia.
Depois proponha um layout em /data e alterações para escrita atômica.
```

---

## 5. Fase 4 — Definir layout `/data`

### Objetivo

Separar o sistema operacional do estado do produto.

### Layout recomendado

```text
/data
  /config
    environment.json
    display.json
    network.json opcional
  /media
    video-id.mp4
    *.tmp
  /spool
    telemetry
    commands
  /state
    sync-state.json
    player-state.json
  /logs
    app.log opcional, rotacionado e pequeno
```

### Regras

- O root `/` não deve armazenar estado do produto.
- Mídias devem ir para `/data/media`.
- Configuração deve ir para `/data/config`.
- Telemetria pendente deve ir para `/data/spool`.
- Logs do app devem ser mínimos, rotacionados ou enviados por telemetria.
- Downloads devem usar `.tmp` e rename atômico.

### Download seguro

Fluxo recomendado:

```text
1. baixar para /data/media/video.mp4.tmp
2. gravar em blocos
3. fsync do arquivo
4. validar tamanho/hash
5. rename para /data/media/video.mp4
6. fsync do diretório
7. remover .tmp antigos no boot
```

---

## 6. Fase 5 — Criar imagem produto v0.1

### Objetivo

Transformar a imagem base em imagem de produto.

### O que entra na imagem

```text
/opt/totem
systemd units
scripts de diagnóstico
NetworkManager
player
Chromium ou navegador/configurador se necessário
serviço do app
serviço de manutenção
estrutura inicial /data
Bluetooth desabilitado se não usado
política de update
```

### O que não entra na imagem

```text
mídias baixadas
ID fixo de cliente
credenciais Wi‑Fi de cliente
logs antigos
cache
machine-id duplicado
chaves únicas reutilizadas
```

### Mecanismo de customização

Usar:

```text
userpatches/overlay
userpatches/customize-image.sh
```

Exemplo estrutural:

```text
totem-os/
  armbian-build-v25.11/
  userpatches/
    customize-image.sh
    overlay/
      opt/totem/
      etc/systemd/system/totem-player.service
      etc/systemd/system/totem-maintenance.service
      usr/local/bin/totem-healthcheck
      usr/local/bin/totem-diag-pack
```

---

## 7. Fase 6 — Modo manutenção e Wi‑Fi

### Objetivo

Permitir operação por usuário não técnico sem depender de desktop Linux.

### Fluxo ideal de primeiro boot

```text
Liga o totem
↓
sem configuração detectada
↓
cria rede Totem-Setup-XXXX ou abre configurador local
↓
operador conecta celular/notebook
↓
acessa página local
↓
seleciona Wi‑Fi, senha, ambiente, posição da tela
↓
totem registra no backend
↓
baixa mídias
↓
entra em modo player
```

### Ferramentas

- NetworkManager;
- `nmcli` por trás do configurador;
- servidor local da aplicação;
- hotspot futuro com `hostapd`/NetworkManager, após teste.

### Testes obrigatórios

- conectar em rede nova;
- trocar rede;
- senha errada;
- rede indisponível;
- reconexão após reboot;
- perda e retorno de internet;
- acesso ao modo manutenção sem internet.

---

## 8. Fase 7 — Player e vídeo

### Objetivo

Validar a carga real do produto.

### Testes

```text
4h de playlist Full HD
24h de playlist Full HD
72h de playlist Full HD
reboot durante operação
endpoint fora
internet fora
/data/media vazio
mídia inválida
mídia parcial .tmp
```

### Métricas

- temperatura;
- RAM;
- CPU;
- travamentos do player;
- reinícios systemd;
- erros de kernel;
- falhas de rede;
- falhas de decodificação;
- sincronização de mídia.

---

## 9. Fase 8 — Root read-only

### Objetivo

Proteger o sistema contra corte seco de energia.

### Pré-requisitos

- aplicação usando `/data` corretamente;
- logs controlados;
- mídia/config/telemetria fora do root;
- healthcheck funcionando;
- player estável.

### Ativação

Via Armbian Config/overlayroot. Comando citado anteriormente:

```bash
sudo armbian-config --cmd ROO001
```

### Teste simples

```bash
sudo sh -c 'echo teste > /etc/prova-overlay'
sudo reboot
ls /etc/prova-overlay
```

Resultado esperado: o arquivo não deve persistir.

### Teste de corte seco

Só depois do root read-only ativo:

```text
1. tocar vídeo
2. simular queda de energia
3. ligar novamente
4. verificar boot
5. verificar /data
6. verificar logs críticos
7. verificar mídia parcial
```

---

## 10. Fase 9 — Atualização da aplicação

### Estratégia recomendada

A aplicação deve ser atualizada independentemente do sistema.

Layout:

```text
/opt/totem/releases/app-1.0.0
/opt/totem/releases/app-1.0.1
/opt/totem/current -> /opt/totem/releases/app-1.0.1
```

Fluxo:

```text
1. backend informa nova versão
2. baixa pacote verificado
3. valida assinatura/hash
4. instala em nova pasta
5. roda healthcheck curto
6. troca symlink current
7. reinicia serviço
8. se falhar, rollback para versão anterior
```

systemd:

```text
ExecStart=/opt/totem/current/start.sh
Restart=always
RestartSec=5
```

---

## 11. Fase 10 — Atualização do sistema

### Agora

Não fazer `apt upgrade` livre em campo.

Atualização de sistema deve ser:

- via imagem nova testada;
- ou por lista controlada de pacotes;
- nunca trocando kernel/DTB/U‑Boot/BSP sem homologação.

### Futuro profissional

Implementar A/B update com Mender ou RAUC.

Modelo A/B:

```text
rootfs A ativo
rootfs B inativo
/data persistente
update grava B
boot em B
healthcheck aprova
B vira ativo
se falha, volta para A
```

Isso é mais robusto para atualização de sistema em campo.

---

## 12. Fase 11 — Telemetria e monitoramento

### Heartbeat mínimo

Cada totem deve enviar periodicamente:

```text
device_id
ambiente
versão da imagem
versão do app
kernel
uptime
temperatura
uso de disco
uso de RAM
rede atual
mídia atual
última sincronização
última telemetria
quantidade de restarts do app
estado do player
```

### Alertas críticos

Enviar alerta se aparecer:

```text
Internal error: Oops
Kernel panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout/reset
disco cheio
temperatura alta
app reiniciando demais
sem mídia válida
sem internet por tempo elevado
sem telemetria por tempo elevado
```

### Comandos remotos seguros

```text
reiniciar player
reiniciar sistema
enviar diagnóstico
limpar .tmp antigos
ressincronizar mídia
resetar tela
entrar em modo manutenção
atualizar app
rollback app
```

Evitar permitir comandos arbitrários como rotina.

---

## 13. Fase 12 — Piloto de campo

Antes de lote maior, rodar um piloto com poucas unidades.

### Critérios

- pelo menos 1 semana em ambiente real;
- fonte dedicada 5V/3A;
- gabinete real;
- tela real;
- rede real;
- playlist real;
- telemetria ativa;
- coleta de diagnóstico automatizada.

### Objetivo

Descobrir problemas não vistos em bancada:

- calor em gabinete fechado;
- Wi‑Fi instável;
- rede do cliente bloqueando endpoint;
- tela HDMI específica;
- queda de energia real;
- operador usando modo manutenção;
- velocidade real de download;
- comportamento do player por dias.

---

## 14. Uso do Codex daqui para frente

### Melhor uso

- analisar repositório da aplicação;
- gerar scripts de diagnóstico;
- criar testes;
- revisar systemd units;
- revisar layout `/data`;
- preparar `customize-image.sh`;
- revisar logs.

### Onde usar

Preferencialmente no PC/WSL, com repositórios Git.

### Onde evitar

Evitar tratar a Orange Pi como ambiente de desenvolvimento principal. Usar a placa para runtime/teste.

### Prompt operacional para Codex

```text
Você é um agente auxiliar de engenharia de confiabilidade para um totem Orange Pi Zero 3.
Contexto: Armbian Build v25.11, Bookworm Minimal, kernel 6.12.58, app Python, player de mídia, /data persistente e root read-only planejado.
Tarefa: revisar o código para riscos de corte de energia, escrita não atômica, logs excessivos, atualização sem rollback e falhas sem modo seguro.
Não execute comandos destrutivos.
Não altere arquivos sem listar antes o plano.
```

---

## 15. Ordem prática dos próximos comandos

### 15.1 Rede

```bash
ip -br addr
nmcli device status
nmcli connection show
rfkill list
journalctl -u NetworkManager -b --no-pager | tail -n 80
```

### 15.2 Stress

```bash
apt update
apt install -y stress-ng
stress-ng --cpu 4 --vm 1 --vm-bytes 50% --timeout 30m --metrics-brief
```

### 15.3 Pós-stress

```bash
cat /proc/sys/kernel/tainted
systemctl --failed
journalctl -k -b --no-pager | grep -iE "oops|panic|EXT4-fs error|Aborting journal|Remounting filesystem read-only|mmc.*timeout|mmc.*reset|thermal|voltage|fail|error" || true
```

### 15.4 Diagnóstico de Bluetooth

Se Bluetooth não for usado, planejar desabilitação na imagem de produto:

```bash
systemctl disable --now bluetooth 2>/dev/null || true
```

Mas não aplicar sem registrar, pois queremos que alterações entrem no build final.

---

## 16. Decisão final desta etapa

O projeto saiu de um estado de imagem clonada e instável para uma fundação mais profissional:

```text
Imagem própria gerada por Armbian Build
+ kernel/DTB/U-Boot congelados
+ base Minimal
+ NetworkManager
+ boot/reboot inicial validado
+ próximos testes definidos
```

A prioridade agora é não acelerar para instalação da aplicação antes de consolidar diagnóstico, layout `/data` e testes de base. Isso evita repetir o padrão antigo: configurar, funcionar por acaso, clonar e perder rastreabilidade.
