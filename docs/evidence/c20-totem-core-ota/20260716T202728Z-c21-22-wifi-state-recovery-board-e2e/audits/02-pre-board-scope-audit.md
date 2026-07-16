**Findings**

- **Blocker de governança para registrar agora:** não encontrei evidência de OTA governado verde para C21.22/`9526cf9`; há apenas o pacote/manifesto local, com `source_commit` correto e `stable_promotion_evidence_sha256` vazio em [manifest.json](/home/builder/totem-os/orange_pi_totem/releases/core-updates/c21.22-wifi-state-recovery-20260716T194811Z-9526cf9/dadooh-totem-core-c21.22-wifi-state-recovery-20260716T194811Z-9526cf9.manifest.json:34). Logo, o claim é registrável somente depois do apply/rollback/reapply governado verde.

- **Blockers de implementação M9.4-6:** nenhum encontrado no recorte auditado. O commit fecha lista vazia/cache/refresh e paginação visível, inclusive retrato, em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3444) e cobre isso em self-test/replay em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:8569).

- **Sem overclaim de conectividade no código:** o estado real é normalizado para `transport`, `wifi_signal`, `internet` e `source`; `portal` fica fora do contrato e vira `unknown` em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:567). O probe Dadooh não é atribuído ao transporte errado por causa do guard de mismatch em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:659).

- **Diagnóstico/recuperação fechado no recorte:** categorias públicas são fechadas e sanitizadas em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:121), renderizadas sem log bruto em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3577), e o fluxo mantém retry/contexto em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:4123).

- **Sem evidência de segredo publicado nas pastas finais:** a busca por sentinelas de senha/diagnóstico bruto não retornou ocorrência. A própria suíte exige máscara de senha persistida em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:8766) e ausência de SSID/senha em artefatos públicos em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:8870).

**Limitações Honestamente Separadas**

- Portal cativo: não implementado, não detectado e não claimável. Isso é item posterior da fila; nesta rodada o correto é manter como não-claim.

- AP aberto físico: segue pendente desde C21.21; o README declara ausência de AP aberto real na placa em [README.md](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/README.md:8). M9.4-6 não deve registrar prova física nova de associação aberta.

- Galeria/replay são evidência sintética/off-board: `board_touched=false` e `networkmanager_touched=false` no replay; a galeria ainda marca necessidade de HDMI/câmera para percepção final em [generate_ui_ux_gallery.py](/home/builder/totem-os/orange_pi_totem/scripts/qa/generate_ui_ux_gallery.py:2582). Isso não bloqueia o recorte lógico, mas limita claim visual físico.

**Claim Registrável Após OTA Governado Verde**

> `totem-core` C21.22 `c21.22-wifi-state-recovery-20260716T194811Z-9526cf9`, fonte `9526cf9`, fecha em homologation os itens M9.4-6 da fila Wi-Fi: estados visuais de lista/cache/refresh/conectando/sucesso/falha/recuperação em paisagem e retrato, explicação pública sanitizada de transporte e acesso ao serviço Dadooh, e diagnóstico/retry por categorias seguras de falha, sem publicar SSID, senha, IP, MAC, DNS ou log bruto, e sem atribuir probe Dadooh a transporte divergente.

Não incluir no claim: stable/público, nova imagem, portal cativo, navegador de portal, internet genérica fora do probe Dadooh, ou prova física de associação a AP aberto.