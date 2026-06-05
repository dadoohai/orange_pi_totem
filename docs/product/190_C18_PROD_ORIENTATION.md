# 190 — C18.PROD-ORIENTATION (decisão, doc curto)

Doc **de decisão** (sem mudança de placa/rebuild; usa medições read-only já coletadas como insumo) para orientar a
caminhada da 1ª candidata controlada de produção (**RC1**) a partir da baseline validada `1d`.
O bug original (`media_load_failed` / saturação de CPU no decode em software) está **RESOLVIDO**;
HW decode end-to-end OK. Esta é a separação **RC1 controlada ≠ produção final/batch**.

> **Nota 2026-06-04:** este doc preserva a orientação tomada quando a baseline
> era `1d` e nao e fonte autoritativa para a linha viva de updates C18. A golden
> atual de laboratório/delivery passou a ser
> `c18-hwdecode-lab-1t`
> (`sha256=7ab5a582f2ce51f13338be8ad4a68a15cb736007f617a49456704c5c45cefec6`),
> com estado runtime de referência após OTA manual `totem-core`
> `c18.ota-core-config-missing-20260603T150429Z-2a7a327`. Consultar
> `189_C18_OTA_READINESS_GATE.md` para o baseline live/golden.

## Baseline observado (1d) — o que está validado em hardware
- **Imagem:** `c18-hwdecode-lab-1d` · sha256 `82a1717f56be8b6aeb8a6b55f43ab5b694d05ce3c751c47dee524c1aed386ca0` · ainda `final_image=false` / `not_for_production=true` (LAB privada).
- **Cartão:** microSD novo 32 GB **aprovado** (o anterior reprovou `h2testw`; foi o fator ambiental dominante observado/provável). dmesg limpo, 27 GB livres.
- **Wrapper** `/opt/totem/bin/totem-mpv-hwdecode`: força `--vo=gpu --gpu-context=drm --hwdec=v4l2request-copy` (copy-back, nv12 — **não** zero-copy) e remove `--no-osc`. O zero-copy (`v4l2request`/drm_prime) causava **panfrost JS faults** em mídia portrait.
- **`kiosk.py` byte-idêntico à C17.4.2** exceto `mpv_path`. Config efetiva: `sync_enabled=false`, `preload_next=false`, `mpv_debug_events=true`, `require_full_download_before_switch=true`, `rotation_deg=0`, `default_duration_ms=10000`, `min_free_space_bytes=512MiB`.
- **Validação:** sequência OK (3 voltas 0→7 em ordem) · `media_load_failed=0` · panfrost faults=0 · mpv 1 pid · **sem preto perceptível** (HDMI, humano).
- **Medições read-only (cartão novo):** boot **22,0 s** (4,0 s kernel + 18,0 s userspace); CPU em playback ~30–49 %/núcleo em itens leves e **pico sustentado ~94–95 %/núcleo** no item pesado (incl. **1080×1920@30**), RSS estável **140 MB**; térmico (**amostra curta read-only sob playback**) **~54–56 °C** (cpu pico 56,4 °C), **sem throttle** (~14 °C de margem ao gate de 70 °C) — o **soak 24h** ainda valida o térmico em **endurance**. 8 mídias de **resolução mista** (360×640 … 1080×1920; 24/30 fps).

## Decisões
1. **Build.** RC1 **controlada na stack atual da 1d** (já validada em HW; não introduzir variáveis agora). **Isto NÃO é produção final/batch.** Para **produção/batch**, o **rebuild GCC-12 native/limpo** segue como **gate** OU **aceite formal de risco** explícito. *(Separação: "RC1 controlada na stack atual; produção final exige hardening/rebuild ou aceite formal".)*
2. **Rotação.** `rotation_deg=0` **aceito** como decisão prática/baseline para esta montagem/validação (RC1 controlada). **270 fora de escopo agora.** Reabrir **só** se houver problema visual reportado (imagem deitada/invertida no HDMI).
3. **`mpv_debug_events`.** **Manter `=true`** na RC1/soak — foi a config validada **e** melhora detecção/recuperação de falhas de load (justamente o modo do bug original). Decisão **consciente e provisória**: validar o que vai ser entregue. Se virar incômodo (log/escrita/complexidade), tratar em **rodada própria**.
4. **Teto de mídia.** RC1 = **1080p30 H.264**. **4K / 60 fps / bitrate alto fora de escopo.** Registrar: `v4l2request-copy` tem **margem menor que zero-copy** (memcpy/frame) — funcional e térmico **OK para 1080p30**, **não generalizar**.
5. **Cartão (BOM).** Não basta "A2": **microSD 32 GB mínimo**, **marca/SKU qualificado**, preferencialmente **high-endurance/industrial**, **`h2testw` ou equivalente em incoming-QA**, e **tracking por serial/lote**. **Não usar cartão genérico.**
6. **Soak (gate FUTURO, não ação imediata).** O **soak 24h não-assistido** é o **gate de endurance para promover à produção/batch** — **não** é a próxima ação agora. Quando for executado, deve rodar **exatamente a config da RC1** e aprovar por: `restarts=0` · `panfrost faults=0` · `mmc/I-O errors=0` · `hard_resync=0` · `media_load_failed=0` (playback local/cache) · **temperatura capturada, sem throttle** · **RSS estável** · **CPU reportada com p95/pico (não só média)** · **tamanho de log observado** (garantir que `mpv_debug_events=true` não gera resíduo exagerado).
7. **Boot.** Registrar **22 s como baseline saudável**; **não abrir frente de otimização agora**. Enquadramento correto: *"o cartão antigo provavelmente explicava a maior parte dos ~2 min; no cartão novo a 1d mede 22 s."* Não transformar em investigação.
8. **Provisionamento de config.** A imagem leva **só defaults seguros**; segredos via **seed do operador** (fora do Git, permissão restrita) → **wizard** → **writer atômico**. **Nenhum segredo embutido** na imagem.

## O que NÃO entra nesta imagem (fora de escopo)
- **Read-only / overlayroot (C12)** — bloqueado, decisão separada.
- **Boot tuning** — boot já saudável (22 s).
- **Refactor do `kiosk.py`** — byte-idêntico à C17.4.2 (só `mpv_path`).
- **Voltar ao zero-copy `v4l2request`** — causou panfrost JS faults; exigiria re-validação por mídia.

## Decisões em aberto (precisam do usuário)
- **Produção final:** GCC-12 native/rebuild como **gate** vs **aceite formal de risco** (item 1), ao sair da RC1 controlada para batch.

*(Rotação não é mais pendência ativa: `0` aceito para a RC1, reabrir só se houver problema visual. Soak 24h é gate futuro, não ação imediata.)*

## Próxima ação imediata
**Nenhuma execução na placa.** A `1d`/RC1 segue como **baseline controlada em uso/observação** (sem regravar, sem alterar config, **sem soak**). O **soak 24h** fica como **gate futuro** antes de promover à produção/batch (item 6), a agendar quando você decidir avançar para batch — e aí com a config exata da RC1. As demais decisões em aberto (produção final) ficam para esse momento.
