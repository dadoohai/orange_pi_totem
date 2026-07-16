**Veredito**

GO para commitar o fechamento do recorte C21.23 homologation-only. Não encontrei falso-verde bloqueante, contradição material, hash quebrado, artefato ausente decisivo, sobreclaim fora dos non-claims, nem dado privado exposto nos artefatos textuais/PNG revisados.

GO limitado ao recorte auditado. Não é GO para stable, publicação pública, navegador de portal, nova imagem, prova física/emulada de captive portal ou diffs fora deste fechamento.

**Achados**

Crítico/Alto/Médio: nenhum.

Baixo/Informativo:
- `state.updated_at` em [status.final.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/board/status.final.json:47) está stale (`2026-07-14`) apesar de `current.applied_at_utc` e `last_operation` serem de `2026-07-16`. Não invalida o claim porque `current`, `previous`, symlinks e `last_operation` fecham corretamente.
- `package/SHA256SUMS` usa caminhos relativos à raiz do repo, não ao diretório `package/`, e o `SHA256SUMS` global lista o manifest mas não o próprio `package/SHA256SUMS` ([SHA256SUMS](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/SHA256SUMS:60), [package/SHA256SUMS](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/package/SHA256SUMS:1)). Validei da raiz do repo: manifest e tarball dão OK.

**Base do GO**

A identidade fonte/pacote sustenta o README: versão, source commit, manifest SHA e payload SHA batem com [README.md](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/README.md:17) e [result.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/result.json:14). O payload real em `releases/core-updates/...tar.gz` valida contra `90990b...`.

Gates e fluxo OTA fecham: `verification.json` marca source/package gates, rc41 stable block, apply, rollback, reapply, policy final e observação pós-reapply como true ([verification.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/verification.json:2)). Os logs `.rc` conferem: stable block `41`; apply/rollback/reapply/self-tests `0`.

Estado final sustentado: `current=C21.23`, `previous=C21.22`, player ativo, zero restarts, timer active/enabled, Ethernet e Wi-Fi conectados em [runtime.final.txt](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/board/runtime.final.txt:3). Policy final voltou a stable em [status.final.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/board/status.final.json:50).

Claim funcional sustentado pelo pacote exato: o opener recusa redirects e a classificação separa portal/inconclusivo em [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:676) e [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:731). Os self-tests cobrem redirect inesperado, HTML/511, ambiguidade e “sem credenciais/cookies/device identifiers” em [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:3096). O wizard bloqueia commit/write/review quando `captive_portal=required` em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3204), [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:4703) e [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:7892).

Replay/galeria sustentam o escopo declarado: `12` cenários, `55` assertivas, `62` telas, sem tocar NetworkManager/writer/board/backend; galeria `123/123`, zero falhas PNG. Abri os quatro PNGs portal e não vi URL, SSID real, MAC/IP, credencial ou conteúdo de portal. Os non-claims em [result.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/result.json:44) estão alinhados com os limites do README.