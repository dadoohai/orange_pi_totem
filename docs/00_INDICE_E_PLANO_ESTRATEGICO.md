# Projeto Totem Orange Pi Zero 3 — Índice e plano estratégico

**Data:** 2026-04-29  
**Status:** documentação de fundação após geração e boot inicial do Candidato A  
**Hardware alvo:** Orange Pi Zero 3, variante observada com ~2 GB RAM  
**Uso:** totem de mídia Full HD com player Python, sincronização por endpoint, telemetria, Wi‑Fi e modo de manutenção/configuração.

---

## 1. Objetivo desta documentação

Esta documentação consolida a decisão técnica construída ao longo da investigação. Ela serve para três finalidades:

1. **Argumentar a decisão**: explicar por que abandonamos a imagem clonada antiga, por que mantemos Armbian como framework, por que não usamos Desktop/rolling/edge e por que o primeiro candidato de produção passou a ser uma imagem própria com Armbian Build v25.11 + Debian Bookworm Minimal + kernel 6.12.58.
2. **Registrar a execução**: documentar o ambiente, os comandos usados, a imagem gerada, os problemas encontrados durante o build e como foram resolvidos.
3. **Guiar a homologação**: organizar os testes já realizados e os próximos testes obrigatórios antes de chamar a base de produção.

Esta não é ainda uma homologação final do produto. É a documentação da **fundação técnica**.

---

## 2. Documentos gerados

### 00 — Índice e plano estratégico

Este arquivo. Resume os objetivos, a arquitetura documental e o plano macro.

### 01 — Decisão técnica e justificativa

Explica o raciocínio completo: sintomas observados, hipóteses descartadas, riscos do hardware, comparação entre sistemas operacionais, avaliação das versões do kernel, decisão sobre Armbian Build, escolha do Candidato A e definição de fallback.

Arquivo: `01_DECISAO_TECNICA_E_JUSTIFICATIVA.md`

### 02 — Geração da imagem base

Registra o procedimento inicial: ambiente WSL, Codex, Docker/Armbian Build, commit, parâmetros de build, imagem gerada, hash, pacotes produzidos e solução dos problemas encontrados durante a execução.

Arquivo: `02_GERACAO_DA_IMAGEM_BASE.md`

### 03 — Testes iniciais e evidências

Registra H2testw, boot inicial, diagnóstico da placa, logs relevantes, reboots limpos e interpretação dos alertas observados.

Arquivo: `03_TESTES_INICIAIS_E_EVIDENCIAS.md`

### 04 — Roadmap de produto, testes, atualização e monitoramento

Organiza o que ainda precisa ser feito: stress, vídeo, Wi‑Fi, `/data`, root read-only, modo manutenção, atualização de app, atualização de sistema, telemetria, diagnóstico remoto e aprendizado de campo.

Arquivo: `04_ROADMAP_PRODUTO_TESTES_ATUALIZACAO_MONITORAMENTO.md`

---

## 3. Leitura executiva

O problema inicial não era apenas “um cartão corrompido”. O cartão antigo caiu no `initramfs`, exigiu `fsck`, exibiu corrupção EXT4 e, depois, o sistema também mostrou `Internal error: Oops` no kernel `6.12.23-current-sunxi64`. Isso criou duas linhas de investigação: **integridade de armazenamento** e **estabilidade de kernel/stack de boot**.

O cartão atual passou no H2testw sem erros, o que removeu a suspeita mais direta de cartão falso/defeituoso. Porém, isso não elimina o risco estrutural: o produto usa microSD, sofre desligamentos forçados e escreve mídia/configuração/telemetria em runtime. Por isso, a solução não pode depender só de “um cartão melhor”.

A imagem clonada antiga de 29 GB foi descartada como base profissional porque ela copia estado, sujeira, logs, possíveis corrupções, identificadores e decisões manuais. Ela serve como referência funcional, não como matriz de produção.

A decisão técnica final foi manter **Armbian**, mas não como simples imagem baixada do site. O uso correto passa a ser o **Armbian Build Framework**, com imagem própria, reprodutível, versionada e testada. Isso permite controlar kernel, DTB, U‑Boot, pacotes, scripts, serviços, freeze de kernel e customizações do produto.

O primeiro candidato gerado foi:

```text
Armbian Build v25.11
BOARD=orangepizero3
Debian Bookworm Minimal
BRANCH=current
Kernel: 6.12.58-current-sunxi64
U-Boot: 2025.04
NetworkManager
BSPFREEZE=yes
sem Desktop
```

Esse candidato foi escolhido porque é o caminho limpo da placa no Armbian Build v25.11: não exige override estrutural e usa board config mais novo, incluindo U‑Boot v2025.04. Ele substitui o `6.12.23` suspeito por `6.12.58`, mantendo uma base reproduzível.

Fallback planejado:

```text
Candidato B:
Armbian Build v25.11 + Debian Bookworm Minimal + BRANCH=legacy
Kernel esperado: 6.6.75
Exige override controlado, pois orangepizero3 expõe current,edge por padrão.
```

O Candidato A já passou por boot inicial e bateria curta de reboots sem `Oops`, sem `panic`, sem erro EXT4, sem `mmc timeout/reset` e sem serviços falhados. O único alerta repetitivo foi Bluetooth `hci0: Opcode 0x0c03 failed: -110`, que não bloqueia se Bluetooth não for usado e deve ser desabilitado na imagem final.

---

## 4. Estratégia macro de produto

A estratégia não é “achar uma distro mágica”. A estratégia é transformar o totem em um appliance controlado:

```text
Imagem gerada por código
+ kernel/DTB/U-Boot congelados
+ sem Desktop completo
+ app controlado por systemd
+ /data persistente para config/mídia/telemetria
+ root filesystem read-only com overlay
+ logs em RAM ou reduzidos
+ downloads atômicos
+ telemetria e diagnóstico remoto
+ atualização de app com rollback
+ atualização de sistema apenas por processo controlado
```

A base só deve ir para campo depois de testes prolongados com vídeo real, rede, downloads, temperatura, reboot, corte de energia pós-read-only e diagnóstico de logs.

---

## 5. Estado atual do projeto

### Concluído

- H2testw no cartão: aprovado sem erros.
- Ambiente WSL preparado.
- Codex instalado e usado como agente de inspeção.
- Armbian Build v25.11 clonado no commit `e172058`.
- Configuração da placa conferida: `KERNEL_TARGET=current,edge`, `BOOTBRANCH=v2025.04`, extensão `uwe5622-allwinner`.
- Imagem Candidato A gerada.
- Imagem gravada no microSD.
- Boot inicial concluído.
- Diagnóstico inicial coletado.
- Reboots limpos realizados sem erros críticos.

### Em aberto

- Teste de stress CPU/RAM.
- Teste Wi‑Fi e troca de rede.
- Decisão formal sobre desabilitar Bluetooth.
- Teste de vídeo Full HD.
- Mapeamento da aplicação Python.
- Criação de `/data` e política de escrita.
- Scripts de diagnóstico e healthcheck.
- Root read-only com overlay.
- Testes de corte seco apenas depois do read-only.
- Estratégia formal de update do app e do sistema.

---

## 6. Critérios de reprovação

Qualquer candidato de imagem deve ser reprovado se aparecer:

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

---

## 7. Fontes principais consultadas

- Armbian Orange Pi Zero3 — página da placa, status Community e imagens atuais: https://www.armbian.com/boards/orangepizero3
- Armbian Board Support Rules — critérios de Community maintained: https://docs.armbian.com/User-Guide_Board-Support-Rules/
- Armbian Build Preparation — requisitos de build, WSL2/Ubuntu 24.04: https://docs.armbian.com/Developer-Guide_Build-Preparation/
- Armbian Build with Docker — método oficial Docker: https://docs.armbian.com/Developer-Guide_Building-with-Docker/
- Armbian Build Switches — parâmetros como `BUILD_MINIMAL`, `BSPFREEZE`, `NETWORKING_STACK`: https://docs.armbian.com/Developer-Guide_Build-Switches/
- Armbian Read Only FS / overlayroot: https://docs.armbian.com/User-Guide_Armbian-Config/System/
- kernel.org releases — LTS 6.6 e 6.12: https://www.kernel.org/releases.html
- linux-sunxi Orange Pi Zero3: https://linux-sunxi.org/Xunlong_Orange_Pi_Zero3
- DietPi issue sobre `6.12.23-current-sunxi64` e Oops: https://github.com/MichaIng/DietPi/issues/7545
- DietPi issue sobre `6.12.23-current-sunxi64` e reboot/kernel panic: https://github.com/MichaIng/DietPi/issues/7590
- DietPi issue sobre freeze em `6.6.44-current-sunxi64`: https://github.com/MichaIng/DietPi/issues/7488
