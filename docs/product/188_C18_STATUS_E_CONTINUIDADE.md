# 188 — C18 Status & Continuidade

Documento mestre de status e continuidade do C18. Objetivo: permitir que alguém retome o trabalho **do zero**, após uma compactação de contexto, usando apenas fatos verificados.

> **Nota de continuidade 2026-06-05:** a golden atual de laboratório/delivery
> para C18 passou a ser **`c18-hwdecode-lab-1q`**,
> sha256 `d487bf33737d5af4ba4bbf7859163cf21f0762ef4c5180f2aed3685e4aa5c009`.
> O estado runtime de referência do marco aplica por cima a release OTA manual
> `totem-core`
> `c18.ota-core-config-missing-20260603T150429Z-2a7a327`.
> Este doc preserva histórico da `1d`; para o baseline live/golden e contrato
> OTA atual, consultar também `docs/product/189_C18_OTA_READINESS_GATE.md` e
> `docs/UPDATE_CONTRACT.md`.
> `1k`/`1l`/`1m`/`1n`/`1o` permanecem como golden historicas anteriores. A `1q`
> valida em hardware o reconcile de manutencao autorizado com privilegio no boot,
> o gate de evidencia sanitizada e o playback/deep-health com config real; `player-runtime`
> continua congelado no fluxo publico (`rc=44`).

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

## Produtização historica — C18.IMAGE-LAB (imagem 1d, sha, deriver, integração)

Imagem-lab privada derivada **OFFLINE** e **ROOTLESS** (via **debugfs**, sem rebuild do Armbian/kernel) a partir da última imagem validada em hardware **C17.4.2**.

> **ATENÇÃO:** **NÃO** usar **C17.7** como base. A base é **C17.4.2**.

**Deriver / scripts:**

- Script principal: `scripts/build/derive_c18_image_lab_1_hwdecode.py`;
- Usa o helper `scripts/build/derive_c15_2_1_homolog_image.py` para `debugfs` / `parse_mbr` / `copy_range`.

**O que a imagem integra:**

- Stack em `/opt/totem/hwdecode/{bin/mpv,bin/ffmpeg,lib}`;
- Wrapper `/opt/totem/bin/totem-mpv-hwdecode` que:
  - ajusta `LD_LIBRARY_PATH`;
  - na `1c`, força `--vo=gpu --gpu-context=drm --hwdec=v4l2request`;
  - na `1d`, força `--vo=gpu --gpu-context=drm --hwdec=v4l2request-copy`;
  - **FILTRA** `--no-osc`;
- `kiosk.py` com `DEFAULT` `mpv_path` → apontando para o **wrapper**;
- Serviço **oneshot** `totem-panfrost-rebind` (userspace, roda **antes do player**, faz bind do panfrost se faltar `/dev/dri/renderD128`);
- **R4 `updatectl`** injetado;
- usuário `totem` já no **grupo `video`**.

**Imagem historica 1d:**

- Nome: **`c18-hwdecode-lab-1d`**;
- **sha256:** `82a1717f56be8b6aeb8a6b55f43ab5b694d05ce3c751c47dee524c1aed386ca0`;
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

### Ajuste 4 (1c → 1d) — panfrost faults no zero-copy + I/O do cartão antigo

A `1c` provou o HW decode e eliminou o bug original, mas a rodada de continuidade achou:

- `panfrost js fault` no caminho zero-copy `v4l2request`/`drm_prime` para algumas mídias
  portrait;
- o cartão anterior tinha erros `mmc`/I-O e falhou no `h2testw`, contaminando sintomas de
  tela preta/ordem/boot lento.

**Correção:** imagem **`1d`** força `v4l2request-copy` no wrapper e move o trace C17.4 para
`/run/totem/c17-4-firstboot`.

---

## Estado historico 1d (validado em hardware)

A placa:

- IP **`<board-ip-redacted>`**, usuário **`root`**, senha **interativa** via helper expect lendo `$SSHPASS` (**NUNCA persistir**);
- hostname **`orangepizero3`**;
- foi regravada pelo usuário com **`c18-hwdecode-lab-1d`** em cartão novo; o cartão anterior
  falhou no `h2testw` e saiu da investigação.

Persistência:

- A raiz `/` é **ext4 rw** e **`overlayroot=tmpfs` NÃO está ativo** (o C12 read-only nunca foi de fato shipado);
- Portanto o **fix in-place PERSISTE no reboot** → a placa funciona e **sobrevive a reboot**, **SEM** necessidade urgente de regravar.

Validação ao vivo (**C18.IMAGE-LAB.1d**, cartão novo, config real aplicada pelo writer
guardado a partir do seed local com `mpv_path` corrigido para o wrapper):

- `hwdec-current=v4l2request-copy`;
- `video pixelformat=nv12` (copy-back; não `drm_prime`);
- tocando **H.264 real**;
- `media_load_failed=0`;
- mpv **estável** (**1 pid**, sem restart observado);
- 8 mídias baixadas;
- **24 eventos `Playing media`** observados (**3 voltas 0→7 em ordem**);
- `panfrost_js_faults=0`;
- erros `mmc`/I-O = 0;
- `mpv_restart=0`, `hard_resync=0`, `ipc_timeout_error_count=0`.

**O bug original (`media_load_failed` por saturação de CPU) está ELIMINADO.**
O problema de ordem/preto errático tinha forte componente de cartão ruim + zero-copy/panfrost.
A confirmação visual humana do HDMI em 2026-06-02 reportou **nenhum preto perceptível** entre
vídeos.

---

## PROBLEMAS ABERTOS (próxima intenção)

> Itens **AINDA NÃO resolvidos**.

### (A) #1 PRINCIPAL — TELA PRETA entre os vídeos + sequenciamento errado

**Status em 2026-06-02:** **RESOLVIDO na `1d`** para a placa/cartão/mídias atuais.

Achados:

- a lógica de sequência do `kiosk.py` é byte-idêntica à referência C17.4.2, exceto `mpv_path`;
- `sync_enabled=false` e `preload_next=false` foram preservados na config real aplicada;
- no cartão antigo havia `mmc`/I-O stall e o cartão falhou `h2testw`;
- na `1c`, zero-copy gerava `panfrost js fault` em algumas mídias portrait;
- na `1d` + cartão novo, a sequência observada fez **3 voltas 0→7 em ordem**, sem
  `media_load_failed`, sem restart do mpv, sem hard-resync e sem faults panfrost.
- confirmação visual humana: **nenhum preto perceptível** entre vídeos.

Se o usuário ainda vir preto longo na `1d`, a próxima investigação deve medir visualmente o
gap do `loadfile replace` e só então avaliar flags/lógica. Não voltar ao zero-copy como fix
rápido sem nova validação por mídia.

### (B) Boot lento (~2min de tela preta antes do wizard)

Boot ~**2min** com tela preta antes do wizard (**kernel 30s** + **userspace 1m41**) — lento; otimizar depois (janela do **deferred-probe** + **firstboot**). O **terminal-no-boot NÃO reaparece mais** (resolvido implicitamente na 1b/1c).

### (C) Rotação 270 não setada no wizard

Rotação **270** não setada no wizard (config/orientação, **não é bug**).

### (D) Rebuild GCC-12 limpo para PRODUÇÃO (recomendado)

Recomendado para a imagem de **PRODUÇÃO**: rebuild **GCC-12 limpo** num **chroot Bookworm**. A stack atual é **GCC-13** + **static-libstdc++** + **shim `__isoc23` só na libplacebo** + **libass sem harfbuzz** — provada em hardware, mas "**suja**".

---

## Próximos passos / a validar

1. Continuar a frente de governanca de atualizacoes: `totem-core` OTA manual ja
   validado; `player-runtime` so avanca em thaw controlado, ainda congelado para
   producao;
2. `c18-hwdecode-lab-1q` e a golden de laboratorio/delivery atual: mantem os
   fechamentos pre-thaw anteriores e valida em hardware os follow-ups de
   reconcile autorizado, evidencia sanitizada e deep-health com config real;
3. **Rebuild GCC-12 de produção;**
4. **Imagem de produção** (a decisão **C12 read-only** é separada e está **bloqueada**).

> **NÃO** aceitar a limitação **(C)** (aceitar o restart) sem **decisão humana**.

---

## Guardrails permanentes

- **NÃO** gerar imagem de produção/release/flash/cartão/poweroff **sem autorização**;
- **SSH só na ÚNICA placa disponível** (`<board-ip-redacted>`);
- **Senha nunca persistida**;
- **Sanitizar tudo** — não imprimir: `api_key`, `api_url` real, `environment_id` real, SSID, senha wifi, IP/MAC/DNS, URLs reais de mídia;
- **Não embutir** `/data/config/config.json` nem config real;
- **C12 / read-only bloqueado e intocado**;
- Mudanças **in-place** na placa exigem **OK explícito** do usuário;
- Preferência do usuário por **MENOS ciclos de gravação/teste** (demoram).

---

## Referências (commits, paths, branches, memórias, sha)

**Repositórios / branches:**

- Repo **`orange_pi_totem`** branch **`foundation-v0.1`** — base local **`8705d78`** antes desta rodada;
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

- Nome: `c18-hwdecode-lab-1d`;
- **sha256:** `82a1717f56be8b6aeb8a6b55f43ab5b694d05ce3c751c47dee524c1aed386ca0`;
- Flags: `artifact_private=true`, `final_image=false`, `not_for_production=true`.

**Placa:**

- IP `<board-ip-redacted>`, usuário `root`, hostname `orangepizero3`, senha interativa via expect lendo `$SSHPASS` (nunca persistir).

**Memórias relevantes:**

- `c18-runtime-decode-stall`;
- `c18-image-lab-2-firstboot-obs`;
- `bounded-diagnostic-rounds`;
- `offboard-dev-test-capabilities`.
