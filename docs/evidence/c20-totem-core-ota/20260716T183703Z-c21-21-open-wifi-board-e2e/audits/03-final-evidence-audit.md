**Findings**

**Blocker/Alta:** nenhum encontrado.

**Média:** a associação a AP aberto físico continua **não provada** e não deve ser aceita por este marco. Isso está corretamente marcado como non-claim em [README.md](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/README.md:50) e `result.json`; não vi overclaim material nos artefatos principais.

**Baixa:** há contradições/staleness em auditorias pré-pacote dentro da evidência: uma diz faltar cobertura `write_visual_artifacts` para rede aberta, mas o self-test atual cobre isso em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:6377). Outra cita copy “Senha protegida”, mas o código atual usa “Senha somente quando necessaria” em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:5472). Não bloqueia o candidato, mas enfraquece a trilha de auditoria.

**Baixa:** os status JSON têm `state.updated_at` antigo, mas `current_symlink_target`, `last_operation`, `applied_at_utc` e `runtime.final.txt` sustentam o estado final. Eu não usaria `state.updated_at` como evidência temporal.

**Veredito**

**GO** para fechar **somente candidato/OTA C21.21**.
**NO-GO** para aceite físico de AP aberto real.

Claims sustentados: hashes do pacote batem (`sha256sum -c OK`), tarball contém os scripts do `source_commit` `4b294c8`, gates contam `84/84` nos dois JSONs, policy stable bloqueou com `rc=41`, apply/rollback/reapply deram `0/0/0`, final ficou C21.21 current e C21.20 previous, policy/timer stable restaurados, player ativo sem restart, Ethernet e Wi-Fi existente conectados.

Código/evidência sustentam rede aberta sem PSK, regressão WPA preservada, IPv4 obrigatório antes de sucesso e rollback transacional. Não encontrei segredo/SSID real exposto nos artefatos de board/pacote; os `TEST_WIFI_*` aparecem só em visual offboard sintético. Verificações foram somente leitura: `jq`, `sha256sum`, `tar -tzf`, comparação de hashes com `git show`, `rg` e `git diff --check`.
