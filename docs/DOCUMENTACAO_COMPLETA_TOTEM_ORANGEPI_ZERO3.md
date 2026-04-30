# Documentação completa — Totem Orange Pi Zero3

Este documento consolida os documentos principais do projeto. Os arquivos separados continuam sendo a fonte preferencial de manutenção.

> Atualização de alto nível — 2026-04-29: o Candidato A avançou além da fundação de SO. O `kiosky-player` já foi deployado em `/opt/totem/kiosky-player`, a config privada já foi criada em `/data/config/config.json`, e o app já rodou manualmente como usuário `totem`, criando mídia/estado/status nos caminhos esperados e sem escrita em `/opt/totem/kiosky-player`. A base OS permanece saudável, mas o Candidato A ainda não está homologado para produção porque o bloqueio atual está na integração app-MPV: IPC, watchdog e restart. Para o estado canônico atualizado, consultar [`STATUS_ATUAL.md`](STATUS_ATUAL.md) e [`app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md`](app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md).



---


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


---


# Decisão técnica e justificativa — Totem Orange Pi Zero 3

**Data:** 2026-04-29  
**Status:** decisão de fundação, ainda em homologação  
**Escopo:** escolha de sistema operacional, kernel, processo de imagem e arquitetura de confiabilidade para totens com Orange Pi Zero 3.

---

## 1. Contexto funcional do produto

O produto é um totem baseado em Orange Pi Zero 3 que:

- executa uma aplicação principal em Python;
- reproduz mídias, incluindo vídeos Full HD;
- baixa mídias a partir de um endpoint;
- envia telemetria;
- precisa conectar em redes Wi‑Fi de clientes;
- precisa permitir configuração por operador não técnico;
- possui comandos de manutenção, ajuste de tela e reset de configuração de tela;
- pode sofrer cortes secos de energia e desligamentos forçados;
- atualmente reinicia diariamente à meia-noite.

O objetivo não é apenas “fazer bootar”. O objetivo é construir uma base de produção mais próxima de appliance: reproduzível, testável, com menor risco de corrupção, com atualização controlada e com diagnóstico remoto.

---

## 2. Sintomas iniciais observados

O primeiro sintoma foi queda no `initramfs` com erro no filesystem root:

```text
armbi_root contains a file system with errors, check forced.
Inode 11650 seems to contain garbage.
armbi_root: UNEXPECTED INCONSISTENCY; RUN fsck MANUALLY.
The root filesystem on /dev/mmcblk0p1 requires a manual fsck
```

Após `fsck -fy /dev/mmcblk0p1`, o filesystem foi modificado:

```text
Inode bitmap differences: -(11649--11664)
FILE SYSTEM WAS MODIFIED
```

No boot seguinte, apareceram erros de kernel e EXT4:

```text
Internal error: Oops
6.12.23-current-sunxi64
EXT4-fs error (device mmcblk0p1)
Aborting journal on device mmcblk0p1-8
EXT4-fs (mmcblk0p1): Remounting filesystem read-only
```

Esses sintomas apontaram para duas frentes:

1. **Corrupção real de filesystem**, compatível com desligamento forçado, escrita interrompida, fonte instável, cartão problemático ou root filesystem gravável em ambiente agressivo.
2. **Possível instabilidade de kernel/stack**, pois `Internal error: Oops` é falha interna do kernel, não erro comum de aplicação.

A conclusão inicial foi: não é responsável reduzir o problema a “cartão ruim” nem a “kernel ruim”. Os dois riscos precisavam ser tratados.

---

## 3. O que o H2testw mudou na análise

O cartão atual foi testado com H2testw no Windows. Resultado informado:

```text
Warning: Only 30107 of 30108 MByte tested.
Test finished without errors.
Writing speed: 17.7 MByte/s
Reading speed: 17.9 MByte/s
```

Isso indica que o cartão testado não apresentou erro óbvio de capacidade falsa ou corrupção leitura/escrita no teste completo disponível.

O H2testw não prova que o cartão será confiável indefinidamente em produção, nem elimina riscos de desgaste, fonte ruim ou corte de energia. Mas removeu uma suspeita imediata: “o cartão atual é claramente defeituoso”.

Consequência da decisão: avançamos para investigar a base do sistema, kernel/boot stack e arquitetura de escrita.

---

## 4. Por que abandonar a imagem clonada antiga

A imagem antiga tinha cerca de 29 GB porque foi clonada de um cartão de 32 GB já configurado. Ela foi descartada como base de produção por vários motivos:

- copia espaço vazio e depende do tamanho real do cartão original;
- pode não caber em outros cartões “32 GB” com alguns setores a menos;
- copia logs, cache, arquivos temporários e mídias;
- copia possíveis corrupções leves;
- duplica `machine-id`, chaves, hostname e estado local;
- torna difícil reconstruir exatamente o que foi instalado;
- transforma a placa configurada manualmente em “matriz”, o que não escala.

A imagem antiga pode continuar sendo útil como **referência funcional**: entender pacotes, serviços, player, configuração de tela e fluxo de usuário. Mas não deve ser a matriz de produção.

Decisão: a imagem final deve ser **gerada por código**, via Armbian Build Framework, com scripts e arquivos versionados.

---

## 5. Por que manter Armbian

A escolha não foi “continuar usando a imagem pronta da Armbian”. A escolha foi usar o **Armbian Build Framework** como ferramenta de fabricação da imagem.

Motivos:

- permite gerar imagem Debian/Ubuntu customizada para SBC;
- controla kernel, DTB, U‑Boot, BSP e root filesystem;
- permite `userpatches`, overlay e scripts de customização;
- permite congelar pacotes críticos de kernel/DTB/U‑Boot/BSP;
- facilita reproduzir uma mesma imagem por commit/tag;
- é mais profissional do que clonar cartão.

A página da Orange Pi Zero3 no Armbian lista a placa como **Community** e mostra imagens atuais com `current 6.12.23`. Isso não torna a imagem inválida, mas significa que ela não deve ser tratada como automaticamente homologada para frota. A documentação da Armbian define que placas Community não estão sob supervisão ativa do time principal e que imagens podem ser não testadas.

Decisão: **Armbian sim como framework; imagem pronta do site não como produção sem homologação própria.**

---

## 6. Por que não Armbian Desktop

A imagem Desktop foi descartada como base de produção porque:

- aumenta quantidade de serviços;
- aumenta uso de RAM;
- aumenta escrita em disco;
- adiciona ruído de diagnóstico;
- tende a instalar componentes irrelevantes para o appliance;
- não é a melhor forma de entregar usabilidade para operador não técnico.

O caminho recomendado não é “dar um desktop Linux ao operador”. É criar um **modo de manutenção próprio**, com página local e, futuramente, hotspot de configuração.

Decisão: usar Minimal/IOT e instalar apenas o necessário.

---

## 7. Por que não rolling/edge

Rolling/edge foram descartados porque o produto precisa de previsibilidade. Rolling e edge servem para teste e acesso a novidades, mas também trazem risco maior de regressão.

A Orange Pi Zero3 aparece no site da Armbian com imagens rolling mais novas, mas isso não combina com totem de campo em SD card e com atualização controlada.

Decisão: **não usar rolling/edge em produção**.

---

## 8. Por que Debian Bookworm

Bookworm foi escolhido como base inicial porque:

- é uma base Debian estável e previsível;
- a página da Armbian para Orange Pi Zero3 aponta Bookworm Minimal/IOT como imagem point release;
- evita usar Trixie em contexto rolling;
- evita Ubuntu Noble com dependências via Snap para Chromium, quando possível;
- encaixa melhor no conceito de appliance enxuto.

Bookworm não é escolhido por ser “o mais novo”, mas por ser a base mais conservadora e controlável neste contexto.

---

## 9. Por que o kernel 6.12.23 foi considerado suspeito

O kernel problemático observado no caso original foi:

```text
6.12.23-current-sunxi64
Internal error: Oops
```

Além disso, pesquisas externas encontraram relatos públicos de Orange Pi Zero 3 com `6.12.23-current-sunxi64` gerando `Internal error: Oops`, inclusive em upgrade e em reboot. Isso é relevante porque o produto reinicia diariamente.

A conclusão não foi “todo kernel 6.12 é ruim”. A conclusão foi:

```text
6.12.23-current-sunxi64 é suspeito e não deve ser promovido a produção sem homologação pesada.
```

---

## 10. Por que 6.6 não virou resposta automática

A linha 6.6 foi considerada porque:

- é LTS;
- o suporte mainline relevante da Orange Pi Zero3 aparece a partir dessa faixa;
- evita começar justamente pelo `6.12.23` suspeito.

Mas a decisão amadureceu: o problema da Orange Pi Zero 3 não é apenas número de kernel. A estabilidade depende de:

```text
U-Boot
DRAM init
TF-A
DTB
kernel
driver Wi-Fi UWE5622/AW859A
microSD
fonte
temperatura
```

Voltar para uma versão antiga do Armbian Build apenas para pegar kernel 6.6 poderia trazer um stack de boot mais antigo. Além disso, há relatos de freeze também em 6.6.x nessa placa.

Conclusão:

```text
6.6 é fallback conservador, mas não garantia.
```

---

## 11. Matriz final de candidatos

A matriz ficou assim:

| Ordem | Candidato | Papel | Observação |
|---:|---|---|---|
| 1 | Armbian Build v25.11 + Bookworm Minimal + current 6.12.58 | Primeiro candidato limpo | Sem override estrutural, board config mais novo, U‑Boot 2025.04 |
| 2 | Armbian Build v25.11 + Bookworm Minimal + legacy 6.6.75 | Fallback conservador | Exige override controlado, porque a placa expõe `current,edge` |
| 3 | Armbian Build v25.02 + Bookworm Minimal + current 6.6.72 | Fallback histórico | Kernel 6.6 concreto, mas stack de boot mais antigo |
| 4 | Imagem oficial Orange Pi Debian/Ubuntu | Controle de hardware | Útil para comparar HDMI/vídeo/Wi‑Fi/reboot, não base preferencial de frota |

---

## 12. Decisão do Candidato A

A primeira imagem gerada foi:

```text
Armbian Build v25.11
BOARD=orangepizero3
RELEASE=bookworm
BRANCH=current
BUILD_MINIMAL=yes
BUILD_DESKTOP=no
NETWORKING_STACK=network-manager
BSPFREEZE=yes
Kernel esperado: 6.12.58-current-sunxi64
U-Boot esperado: 2025.04
```

Motivos:

- caminho limpo da placa no Armbian Build v25.11;
- não exige override no board config;
- usa stack de boot mais recente que v25.02;
- evita o kernel 6.12.23 suspeito;
- preserva opção de fallback para 6.6.75 se falhar;
- mantém imagem reproduzível e versionada.

---

## 13. Decisão sobre `BSPFREEZE`

Foi usado:

```text
BSPFREEZE=yes
```

Objetivo:

- congelar kernel;
- congelar DTB;
- congelar U‑Boot;
- congelar BSP;
- evitar que `apt upgrade` troque a camada crítica em campo.

No boot inicial, isso foi confirmado pelo `dpkg -l`: os pacotes apareceram com status `hi`, indicando hold.

---

## 14. Decisão sobre NetworkManager

Foi usado:

```text
NETWORKING_STACK=network-manager
```

Motivo:

- o produto precisa trocar Wi‑Fi em campo;
- operadores não técnicos precisam de configuração fácil;
- o modo de manutenção deve conseguir listar redes, conectar/desconectar e salvar credenciais;
- NetworkManager facilita integração futura com configurador local/hotspot.

A imagem fica menos “minimal pura”, mas mais adequada ao uso real.

---

## 15. Decisão sobre Bluetooth

No boot e nos reboots apareceu repetidamente:

```text
Bluetooth: hci0: Opcode 0x0c03 failed: -110
```

Interpretação:

- timeout de inicialização/reset do Bluetooth;
- não bloqueou boot;
- não gerou falha de serviço;
- não apareceu acompanhado de Oops/panic.

Decisão proposta:

```text
Se o produto não usa Bluetooth, desabilitar Bluetooth na imagem final para reduzir ruído e tempo de boot.
```

Ainda não foi aplicado na imagem base porque os testes estavam validando o sistema limpo.

---

## 16. Decisão estrutural contra corte seco de energia

A versão de kernel não resolve sozinha o problema de corte seco. A arquitetura final precisa proteger o root filesystem.

Estrutura recomendada:

```text
/              root base protegido/read-only
/opt/totem     aplicação instalada
/data/config   configuração persistente
/data/media    mídias baixadas
/data/spool    telemetria pendente
/tmp           tmpfs
/var/log       zram/RAM ou log reduzido
```

O Armbian oferece modo read-only com overlayroot. A ativação deve acontecer depois que a aplicação e os caminhos persistentes estiverem bem definidos.

Decisão:

```text
Root read-only é obrigatório antes de testar corte seco como cenário de homologação.
```

---

## 17. Decisão sobre atualização

Não será permitido:

```text
apt upgrade livre em campo
```

Política futura:

1. **Mídia e configuração:** via backend, gravando em `/data`.
2. **Aplicação:** release versionada com rollback, por exemplo `/opt/totem/releases/app-x.y.z` + symlink `current`.
3. **Sistema/kernel:** apenas por imagem nova testada ou mecanismo A/B no futuro.
4. **Kernel/U‑Boot/DTB:** nunca atualizar diretamente na frota sem bancada.

---

## 18. Decisão sobre desenvolvimento

O desenvolvimento principal da aplicação deve acontecer fora da placa:

```text
PC/WSL/GitHub/CI -> build/release -> placa para runtime e teste
```

A placa não deve virar ambiente de desenvolvimento cotidiano porque isso aumenta escrita no SD, mistura estados e dificulta reproduzir a imagem.

Codex pode ajudar principalmente no PC/WSL, analisando repositórios e criando scripts/testes. Na placa, deve ser usado com cautela e apenas depois de estabilizar o sistema.

---

## 19. Resultado atual da decisão

O Candidato A foi gerado, gravado e bootado. Resultados iniciais:

- kernel correto: `6.12.58-current-sunxi64`;
- imagem própria: `IMAGE_TYPE=user-built`;
- build commit: `e172058`;
- board type: `csc`;
- pacotes críticos em hold;
- RAM detectada corretamente para placa de 2 GB;
- root expandido para 29 GB;
- `/var/log` em zram;
- `systemctl --failed` zerado;
- sem Oops;
- sem panic;
- sem erro EXT4;
- sem `mmc timeout/reset`;
- reboots limpos aprovados;
- Bluetooth timeout observado e registrado.

Conclusão: **o Candidato A é promissor e segue para testes de carga/rede/vídeo.**

---

## 20. Fontes e evidências

### Fontes externas principais

- Orange Pi Zero3 no Armbian: https://www.armbian.com/boards/orangepizero3
- Regras de suporte Armbian: https://docs.armbian.com/User-Guide_Board-Support-Rules/
- Armbian Build Preparation: https://docs.armbian.com/Developer-Guide_Build-Preparation/
- Armbian Docker Build: https://docs.armbian.com/Developer-Guide_Building-with-Docker/
- Armbian Build Switches: https://docs.armbian.com/Developer-Guide_Build-Switches/
- Armbian Read Only FS: https://docs.armbian.com/User-Guide_Armbian-Config/System/
- Kernel.org releases: https://www.kernel.org/releases.html
- linux-sunxi Orange Pi Zero3: https://linux-sunxi.org/Xunlong_Orange_Pi_Zero3
- DietPi issue 7545: https://github.com/MichaIng/DietPi/issues/7545
- DietPi issue 7590: https://github.com/MichaIng/DietPi/issues/7590
- DietPi issue 7488: https://github.com/MichaIng/DietPi/issues/7488

### Evidências internas da conversa

- Logs de `fsck` e EXT4 do sistema antigo.
- Resultado H2testw do cartão.
- Saída do Codex confirmando board config e kernels no v25.11.
- Logs de geração da imagem.
- Boot inicial da Orange Pi com Candidato A.
- Logs de reboot e filtros de kernel.


---


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


---


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


---

## 14. Baseline de rede antes do stress leve

Data: 2026-04-28T21:50:02-03:00.

Comandos executados:

```bash
ip -br addr
nmcli device status
NMCLI_PAGER=cat nmcli connection show
rfkill list
journalctl -u NetworkManager -b --no-pager | tail -n 120
```

Resultado resumido:

```text
end0  UP  192.168.18.114/24
wlan0 DORMANT
end0 ethernet conectado
wlan0 wifi desconectado
NetworkManager state: CONNECTED_GLOBAL
```

Interpretação:

- Ethernet funcional via `end0`.
- Wi‑Fi detectado como `wlan0`, sem bloqueio por rfkill.
- NetworkManager gerenciando rede corretamente.
- Driver Wi‑Fi informa suporte a Access Point, relevante para futuro modo manutenção/hotspot.
- `wlan0` desconectado nesta etapa não reprova, pois o teste usou cabo.

Evidência bruta/resumida:

```text
docs/EVIDENCIAS/2026-04-28/network-before-stress.txt
```

Classificação: aprovado para prosseguir com stress leve.

---

## 15. Stress leve CPU/RAM — 30 minutos

Data: 2026-04-28.

Comando executado:

```bash
apt update
apt-get install --no-upgrade -y stress-ng
stress-ng --cpu 4 --vm 1 --vm-bytes 50% --timeout 30m --metrics-brief
```

Observação: foi usado `apt install` específico para instalar `stress-ng`. Não foi executado `apt upgrade`.

Resultado principal:

```text
stress-ng: successful run completed in 1800.21s (30 mins, 0.21 secs)
```

Estado após o teste:

```text
tainted: 1024
systemctl --failed: 0 loaded units listed
Memória: 1.9 GiB total, 1.5 GiB livre
Swap: 396 KiB usado
Root: 29G, 5% usado
Temperatura ao fim: ~52–54°C
Temperatura máxima observada: 75°C sobre a mesa
Travou: não
Reiniciou sozinho: não
```

O filtro crítico de kernel não mostrou:

```text
Internal error: Oops
Kernel panic
EXT4-fs error
Aborting journal
Remounting filesystem read-only
mmc timeout
mmc reset
```

Interpretação:

- Carga leve CPU/RAM aprovada.
- O kernel permaneceu sem Oops/panic.
- O filesystem permaneceu sem erro EXT4.
- O cartão/driver MMC não mostrou timeout/reset.
- Temperatura máxima de 75°C em bancada aberta não reprova, mas exige teste posterior no gabinete real.
- Mensagens `Error applying setting, reverse things back` persistem como ruído observado, sem impacto operacional nesta etapa.

Evidência bruta/resumida:

```text
docs/EVIDENCIAS/2026-04-28/stress-30m.txt
```

Classificação: aprovado em carga leve CPU/RAM.

---

## 16. Status atualizado do Candidato A

### Aprovado até aqui

- H2testw do cartão;
- build da imagem;
- boot inicial;
- reboots curtos;
- rede cabeada/NetworkManager;
- carga leve CPU/RAM de 30 minutos.

### Continua pendente

- Wi‑Fi real em modo cliente;
- hotspot/modo manutenção;
- estrutura `/data`;
- desabilitação de Bluetooth se não usado;
- script de diagnóstico;
- instalação controlada do player;
- reprodução Full HD real;
- teste térmico no gabinete;
- root read-only com overlay;
- teste de corte seco;
- homologação 24h/72h.


---


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

---

## Atualização de status — 2026-04-28

### Candidato A

```text
Armbian Build v25.11
Debian Bookworm Minimal
Orange Pi Zero3
Kernel 6.12.58-current-sunxi64
U-Boot 2025.04
NetworkManager
BSPFREEZE=yes
```

### Etapas concluídas

- [x] H2testw do cartão;
- [x] geração da imagem base;
- [x] gravação e boot inicial;
- [x] confirmação de kernel/DTB/U‑Boot/BSP em hold;
- [x] reboots curtos limpos;
- [x] baseline de rede cabeada/NetworkManager;
- [x] stress leve CPU/RAM por 30 minutos.

### Resultado do stress leve

- `stress-ng` completou 1800.21s;
- sem travamento;
- sem reboot espontâneo;
- sem serviços falhados;
- sem Oops/panic;
- sem erro EXT4;
- sem `mmc timeout/reset`;
- temperatura máxima observada: 75°C em bancada aberta.

### Próximo bloco de trabalho

- [ ] criar estrutura `/data`;
- [ ] desabilitar Bluetooth se não usado;
- [ ] criar script de diagnóstico local;
- [ ] reforçar política de update nos scripts e documentação;
- [ ] preparar instalação controlada dos componentes do player;
- [ ] testar Wi‑Fi cliente;
- [ ] testar hotspot/modo manutenção.

### Regra reforçada

Não executar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade` em campo. Para instalação pontual em bancada, usar `apt-get install --no-upgrade -y <pacote>`.


---


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
