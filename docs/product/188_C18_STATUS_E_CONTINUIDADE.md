# 188 — C18 Status & Continuidade

Documento mestre de status e continuidade do C18. Objetivo: permitir que alguém retome o trabalho **do zero**, após uma compactação de contexto, usando apenas fatos verificados.

---

## Problema original

Placa **Orange Pi Zero 3** / SoC **Allwinner H618**, **Armbian Bookworm Minimal**, player **MPV** via **DRM/KMS** sob **systemd**.

Sintoma: a mídia repetia / "não respeitava o tempo".

Diagnóstico **C18.RUNTIME** provou que a causa **NÃO** era duração, API, playlist nem sync. A causa-raiz é:

- Decode **H.264 em SOFTWARE** satura a CPU na transição de mídia (`loadfile`);
- Isso **trava a thread principal** que serve o IPC do MPV;
- O **timeout de IPC (2s)** estoura → falso `media_load_failed`;
- O **watchdog reinicia o MPV** → trava / pisca / repete visível.

---

## Solução (provada) — C18.RUNTIME A2..B9

HW decode via **Cedrus / V4L2 Request (stateless)** com stack userspace custom, com **`vo=gpu` zero-copy no panfrost**.

Stack (forks/versões):

- **ffmpeg** fork Kwiboo `@2af4006` (branch `v4l2request-2024-v2`);
- **mpv** fork Kwiboo `@8670d2e` (branch `v4l2request-test-20240808`);
- **libplacebo** `@64c1954`;
- **libass / freetype / fribidi**.

Provas na placa (hardware):

- **B1**: ffmpeg ~**24x menos CPU** em 1080p High / CABAC / B-frames;
- **B7**: display **zero-copy** (`drm_prime` → overlay panfrost);
- **B8**: rotação **270** via EGLImage;
- **B9**: soak de **867 transições** `loadfile` com **0 falhas**, ~**20% de 1 núcleo**.

Tudo commitado na branch isolada **`c18-runtime-a1-cedrus-hwdecode-poc`** (A1..B9).

---

## Produtização — C18.IMAGE-LAB (imagem 1c, sha, deriver, integração)

Imagem-lab privada derivada **OFFLINE** e **ROOTLESS** (via **debugfs**, sem rebuild do Armbian/kernel) a partir da última imagem validada em hardware **C17.4.2**.

> **ATENÇÃO:** **NÃO** usar **C17.7** como base. A base é **C17.4.2**.

**Deriver / scripts:**

- Script principal: `scripts/build/derive_c18_image_lab_1_hwdecode.py`;
- Usa o helper `scripts/build/derive_c15_2_1_homolog_image.py` para `debugfs` / `parse_mbr` / `copy_range`.

**O que a imagem integra:**

- Stack em `/opt/totem/hwdecode/{bin/mpv,bin/ffmpeg,lib}`;
- Wrapper `/opt/totem/bin/totem-mpv-hwdecode` que:
  - ajusta `LD_LIBRARY_PATH`;
  - força `--vo=gpu --gpu-context=drm --hwdec=v4l2request`;
  - **FILTRA** `--no-osc`;
- `kiosk.py` com `DEFAULT` `mpv_path` → apontando para o **wrapper**;
- Serviço **oneshot** `totem-panfrost-rebind` (userspace, roda **antes do player**, faz bind do panfrost se faltar `/dev/dri/renderD128`);
- **R4 `updatectl`** injetado;
- usuário `totem` já no **grupo `video`**.

**Imagem final:**

- Nome: **`c18-hwdecode-lab-1c`**;
- **sha256:** `766a3eb2071e599df5561918c8308f9559fb8d24ee65168839a8cf6a75d85c29`;
- As versões defeituosas **1** e **1b** foram **removidas** de `output/images`;
- Flags do artefato: `artifact_private=true`, `final_image=false`, `not_for_production=true`.

---

## Os 3 bugs corrigidos (todos do deriver)

Todos os 3 bugs eram do **deriver/build** (a stack HW B1..B9 **sempre esteve OK**). Achados na validação em hardware **C18.IMAGE-LAB.2**:

### Bug 1 (1 → 1b) — kiosk.py corrompido

`kiosk.py` corrompido (**SyntaxError linha 3425**) porque o arquivo foi lido via debugfs `cat`, que anexa o **banner do debugfs** (stderr) ao conteúdo.

**Correção:** ler via **`debugfs dump`** + `py_compile` na validação.

### Bug 2 (1 → 1b) — panfrost probe -110

panfrost `1800000.gpu` probe **`-110`** (**deferred-probe race** no boot), sem `renderD128` → `vo=gpu` falharia. A GPU é sã (re-bind manual sobe na hora).

**Correção:** serviço **`totem-panfrost-rebind`**.

### Bug 3 (1b → 1c) — --no-osc no mpv custom

O player passa `--no-osc` (válido no mpv 0.35.1), mas o mpv custom é **`-Dlua=disabled`** e a OSC é um script Lua → a opção `--osc` **não existe** → o mpv **aborta (Fatal) ANTES de criar o socket IPC** → o player estoura o **timeout de 10s** de IPC e entra em **crash-loop** ("iniciando player").

**Correção:** o **wrapper FILTRA `--no-osc`**.

---

## Estado atual (validado em hardware)

A placa:

- IP **`192.168.18.131`**, usuário **`root`**, senha **interativa** via helper expect lendo `$SSHPASS` (**NUNCA persistir**);
- hostname **`orangepizero3`**;
- está rodando o **conteúdo da 1c** (a **1b** gravada pelo usuário **+** o **wrapper corrigido aplicado in-place**, autorizado pelo usuário).

Persistência:

- A raiz `/` é **ext4 rw** e **`overlayroot=tmpfs` NÃO está ativo** (o C12 read-only nunca foi de fato shipado);
- Portanto o **fix in-place PERSISTE no reboot** → a placa funciona e **sobrevive a reboot**, **SEM** necessidade urgente de regravar.

Validação ao vivo (**C18.IMAGE-LAB.2**, clean-board, no core):

- `hwdec-current=v4l2request`;
- tocando **H.264 real**;
- `media_load_failed=0`;
- mpv **estável** (**1 pid**);
- CPU ~**13,6%**;
- transições **sem crash**.

**O bug original (`media_load_failed` por saturação de CPU) está ELIMINADO.**

---

## PROBLEMAS ABERTOS (próxima intenção)

> Itens **AINDA NÃO resolvidos**.

### (A) #1 PRINCIPAL — TELA PRETA entre os vídeos + sequenciamento errado

**Sintoma (relato do usuário, errático):** **TELA PRETA** entre os vídeos — às vezes fica **MUITO TEMPO**, **SEM padrão de transição**, e as **MÍDIAS NÃO ESTÃO SEQUENCIANDO CORRETAMENTE**.

Medições anteriores:

- playlist de **8 itens** (index 0..7);
- transições agendadas "coladas" (gap de agendamento ~**0,1–0,2s**);
- resolução **constante 480x848**.

Mas o usuário vê **pretos longos / erráticos + sequência errada**.

Observações:

- **NÃO diagnosticado a fundo ainda;**
- **NÃO** é diferença 1b ↔ 1c nem coisa de regravar (a placa **==** conteúdo 1c);
- É **qualidade/lógica de transição**: latência do `loadfile-replace` (descarrega → preto → carrega → 1º frame) e possivelmente **reinit de hwdec/VO por arquivo**;
- O player usa **`loadfile ... replace`** por item (+ `append` / `keep-open`).

Hipóteses de correção:

- **prefetch/preload** do próximo (`mpv --prefetch-playlist`);
- **segurar o último frame** até o próximo aparecer;
- ajustar a **lógica de transição do `kiosk.py`**.

**PRECISA:** medir a **duração do preto ao vivo**, entender a **sequência errada**, e **decidir** se resolve com **flags do mpv** (rápido) ou **mudança no `kiosk.py`**.

### (B) Boot lento (~2min de tela preta antes do wizard)

Boot ~**2min** com tela preta antes do wizard (**kernel 30s** + **userspace 1m41**) — lento; otimizar depois (janela do **deferred-probe** + **firstboot**). O **terminal-no-boot NÃO reaparece mais** (resolvido implicitamente na 1b/1c).

### (C) Rotação 270 não setada no wizard

Rotação **270** não setada no wizard (config/orientação, **não é bug**).

### (D) Rebuild GCC-12 limpo para PRODUÇÃO (recomendado)

Recomendado para a imagem de **PRODUÇÃO**: rebuild **GCC-12 limpo** num **chroot Bookworm**. A stack atual é **GCC-13** + **static-libstdc++** + **shim `__isoc23` só na libplacebo** + **libass sem harfbuzz** — provada em hardware, mas "**suja**".

---

## Próximos passos / a validar

1. **Diagnosticar e corrigir a tela preta + sequenciamento** (ao vivo via SSH, **SEM regravar**);
2. **Confirmação VISUAL no HDMI** (olho humano: imagem correta + rotação);
3. **Otimizar tempo de boot;**
4. **Rebuild GCC-12 de produção;**
5. **Imagem de produção** (a decisão **C12 read-only** é separada e está **bloqueada**).

> **NÃO** aceitar a limitação **(C)** (aceitar o restart) sem **decisão humana**.

---

## Guardrails permanentes

- **NÃO** gerar imagem de produção/release/flash/cartão/poweroff **sem autorização**;
- **SSH só na ÚNICA placa disponível** (`192.168.18.131`);
- **Senha nunca persistida**;
- **Sanitizar tudo** — não imprimir: `api_key`, `api_url` real, `environment_id` real, SSID, senha wifi, IP/MAC/DNS, URLs reais de mídia;
- **Não embutir** `/data/config/config.json` nem config real;
- **C12 / read-only bloqueado e intocado**;
- Mudanças **in-place** na placa exigem **OK explícito** do usuário;
- Preferência do usuário por **MENOS ciclos de gravação/teste** (demoram).

---

## Referências (commits, paths, branches, memórias, sha)

**Repositórios / branches:**

- Repo **`orange_pi_totem`** branch **`foundation-v0.1`** — último commit **`5a0ceb3`** (= doc 187 + roadmap + deriver + evidência 1c; também 186);
- **PoC A1..B9** na branch **`c18-runtime-a1-cedrus-hwdecode-poc`**;
- **`kiosky-player`** branch **`appliance-v0.1`** `@e76204a`.

**Stack HW (forks / commits):**

- ffmpeg Kwiboo `@2af4006` — branch `v4l2request-2024-v2`;
- mpv Kwiboo `@8670d2e` — branch `v4l2request-test-20240808`;
- libplacebo `@64c1954`;
- libass / freetype / fribidi.

**Paths principais:**

- `scripts/build/derive_c18_image_lab_1_hwdecode.py` (deriver);
- `scripts/build/derive_c15_2_1_homolog_image.py` (helper debugfs / parse_mbr / copy_range);
- `/opt/totem/hwdecode/{bin/mpv,bin/ffmpeg,lib}` (stack na placa);
- `/opt/totem/bin/totem-mpv-hwdecode` (wrapper);
- `kiosk.py` (`DEFAULT` `mpv_path` → wrapper);
- serviço `totem-panfrost-rebind`;
- `output/images` (1 e 1b removidas).

**Imagem:**

- Nome: `c18-hwdecode-lab-1c`;
- **sha256:** `766a3eb2071e599df5561918c8308f9559fb8d24ee65168839a8cf6a75d85c29`;
- Flags: `artifact_private=true`, `final_image=false`, `not_for_production=true`.

**Placa:**

- IP `192.168.18.131`, usuário `root`, hostname `orangepizero3`, senha interativa via expect lendo `$SSHPASS` (nunca persistir).

**Memórias relevantes:**

- `c18-runtime-decode-stall`;
- `c18-image-lab-2-firstboot-obs`;
- `bounded-diagnostic-rounds`;
- `offboard-dev-test-capabilities`.
