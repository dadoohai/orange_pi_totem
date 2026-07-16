**Findings**

**Blocker:** nenhum encontrado.

**Alta:** nenhum fail-open encontrado. Segurança desconhecida segue pelo caminho protegido, não pelo aberto: [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3755). Rede aberta só vira payload `security_type=open` sem `psk`, e o adaptador rejeita open contraditório com credencial: [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:3122), [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:1573). O keyfile só adiciona `[wifi-security]` no caso WPA-PSK: [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:1607).

**Média:** nenhum problema transacional bloqueante encontrado. O sucesso é rebaixado para falha quando `nmcli connection up` não resulta em IPv4: [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:2176). A restauração captura fonte anterior, derruba/deleta o perfil novo e recarrega/reativa o anterior quando aplicável: [totem_wifi_nm_adapter.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:1817).

**Baixa / evidência:** a auditoria pré-pacote `02-pre-package-ux-audit.md` contém uma observação stale sobre copy “Senha protegida.”, mas o código e o tar C21.21 têm “Senha somente quando necessaria.”: [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:5472). Não bloqueia o candidato, mas é ruído na evidência.

**Checks Relevantes**

O pacote é exatamente `c21.21-open-wifi-20260716T171724Z-4b294c8`, source `4b294c8c95e7d7715d9f0abdce5cab1e8f2dcf34`, SHA `87a7f8...79683`: [package-manifest.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/package/package-manifest.json:18). Comparei o conteúdo do tar contra `git show 4b294c8` para wizard e adapter; bateu byte a byte.

Os dois ajustes de timeout de QA são bounded e não mudam critério de aprovação: autopull evidence `300s` em [c18_ota_release_gate.py](/home/builder/totem-os/orange_pi_totem/scripts/qa/c18_ota_release_gate.py:209), H2 nested self-test `120s` em [c18_ota_policy_static_test.py](/home/builder/totem-os/orange_pi_totem/scripts/qa/c18_ota_policy_static_test.py:3588). Não entraram no tar OTA.

Stable gate bloqueou homologation com rc `41`; apply, rollback e reapply deram rc `0`. Final voltou para policy stable, timer ativo, player sem restart, Ethernet e Wi-Fi conectados: [runtime.final.txt](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/board/runtime.final.txt:3), [status.final.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/board/status.final.json:50).

**GO/NO-GO**

**GO para o candidato OTA homologation C21.21.**
**NO-GO para declarar aceite físico de AP aberto real.** A própria evidência mantém isso como pendente: [README.md](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/README.md:49), [result.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/result.json:49).

Não implementei nada. Rodei apenas comandos somente leitura, incluindo `git diff --check`, inspeção de diffs, hashes e conteúdo do tar.
