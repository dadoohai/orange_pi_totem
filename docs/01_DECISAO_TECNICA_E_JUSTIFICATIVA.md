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
