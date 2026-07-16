**Findings**

Críticos/Altos: nenhum.

Médios: nenhum bloqueante para M9.4-6.

Baixos / não bloqueantes:
- O dossiê de evidência tem arquivos pós-`SHA256SUMS` que não estão cobertos pelo manifesto de hashes: `verification.json`, `board/runtime.post-observation.txt` e `board/current-files.txt`. Os arquivos listados em `SHA256SUMS` verificam corretamente, então isso é uma observação de integridade arquivística, não uma regressão do pacote.
- A evidência C21.22 e os docs revisados aparecem no worktree como não versionados/modificados. Se o fechamento exige dossiê commitado, ainda falta essa etapa de controle documental; não afeta o binário/pacote homologation já validado.

**Verificações**

O pacote C21.22 aponta para `source_commit` `9526cf9`, canal `homologation`, sem promoção stable e com payload compatível com o tarball em `releases/core-updates/...manifest.json`.

A evidência declara e sustenta apenas M9 itens 4-6: estados visuais, distinção Ethernet/Wi-Fi/Dadooh e falhas/retry seguros. Os limites ficam explícitos: sem portal cativo, sem browser, sem stable público, sem AP aberto físico e sem falhas Wi-Fi físicas inferidas em [README.md](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T202728Z-c21-22-wifi-state-recovery-board-e2e/README.md:58).

Não encontrei claim maior que código/teste nos docs: [C20_UX_ACCUMULATION_PLAN.md](/home/builder/totem-os/orange_pi_totem/docs/C20_UX_ACCUMULATION_PLAN.md:778), [C18_MACRO_STEERING.md](/home/builder/totem-os/orange_pi_totem/docs/C18_MACRO_STEERING.md:358) e [C18_OTA_OPERATIONAL_SOURCE_OF_TRUTH.md](/home/builder/totem-os/orange_pi_totem/docs/C18_OTA_OPERATIONAL_SOURCE_OF_TRUTH.md:841) estão alinhados com o recorte C21.22.

A evidência operacional fecha: gates fonte/pacote `84/84`, replay `12` cenários e `53` assertions, galeria `119/119`, stable bloqueado com `rc=41`, apply/rollback/reapply `rc=0`, estado final C21.22/C21.21, player com `0` restarts, Ethernet e Wi-Fi preservados, política/timer stable restaurados em [board/summary.txt](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T202728Z-c21-22-wifi-state-recovery-board-e2e/board/summary.txt:1).

No código, a guarda de transporte evita atribuir Dadooh online ao transporte errado, o retry de autenticação volta para correção de senha, retries não-auth são diretos e contextualizados, e os artefatos públicos são sanitizados para não expor senha/SSID real/IP/MAC/DNS.

**Veredito**

GO para fechar a candidata `homologation` C21.22 estritamente para M9 itens 4-6.

NO-GO para qualquer ampliação de escopo: portal cativo, browser, stable, release público, AP aberto físico, falhas Wi-Fi físicas ou aceitação por framebuffer interativo.