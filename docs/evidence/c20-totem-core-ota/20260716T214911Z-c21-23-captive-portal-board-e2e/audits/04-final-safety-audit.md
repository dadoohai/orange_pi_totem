**Achados**

Crítico/Alto: nenhum.

Médio: nenhum blocker para o recorte C21.23. O limite permanece explícito: não há prova física/emulada de portal cativo, então é **NO-GO** para declarar suporte de campo completo de portal real. Isso está corretamente tratado como non-claim na evidência.

Baixo/Informativo: o working tree está sujo com docs e evidência não rastreada. O GO abaixo vale para o pacote exato `c21.23...3e5dbf8` e para a evidência lida, não para um novo build a partir do estado atual.

**Conclusão Técnica**

Portal vs ambiguidade: OK. `online` continua dependendo do HTTPS HEAD; portal só vira `required` com 511, redirect inesperado/oversized ou HTML interceptado. Timeout/DNS/TLS/non-HTML ficam inconclusivos, não portal. Ver [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:731) e [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:783).

Redirect/body/timeouts: OK. Redirect handler não segue redirects, body é limitado a 4096 bytes, Location a 2048 chars, socket timeout é 0.75s e a coleta usa orçamento total. Ver [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:676) e [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:711).

Privacidade: OK. O estado público só publica enum/flags; URL, HTML, cookie, SSID, senha, IP, DNS e erro bruto não aparecem no contrato. Evidência normal mostra `online/not_detected` com flags sanitizadas.

Fail-closed no wizard: OK. `required` bloqueia readiness, review e escrita; `write_visual_artifacts` rechecou portal ao vivo antes de gravar. Ver [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3204), [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:4904) e [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:4703).

Normal network/regressão: OK dentro da prova disponível. A placa terminou com `transport=ethernet`, `internet=online`, `captive_portal=not_detected`; Ethernet e Wi-Fi conectados, player ativo, zero restarts.

Pacote/fronteiras OTA: OK. Manifest é `component=totem-core`, `channel=homologation`, source clean `3e5dbf8`; tar fica em `bin/`, `health/`, `manifest-fragment/`, sem player-runtime/public stable/kernel. Stable bloqueou homologation com rc `41` por incompatibilidade de canal; apply/rollback/reapply rc `0`; policy final igual à inicial.

**GO/NO-GO**

**GO** para fechar C21.23 como candidata homologation `totem-core` de detecção positiva de portal cativo, com ambiguidade fail-closed e sem regressão relevante observada.

**NO-GO** para stable/public release, navegador/autenticação de portal, nova imagem ou claim de suporte de campo para portal físico/emulado.