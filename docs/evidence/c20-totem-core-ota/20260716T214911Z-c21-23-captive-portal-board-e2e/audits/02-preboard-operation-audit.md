Não toquei a placa nem editei arquivos. A auditoria foi só por leitura do repo, manifest/payload e precedentes C21.22.

**Achados Por Severidade**

**Alta**
- O timer/agent precisa ser isolado antes de qualquer janela `homologation`. O serviço de produção roda `apply-github-latest` para `totem-core`, então deixá-lo ativo durante a troca de policy cria risco de corrida/contenda e de buscar artefato remoto fora do pacote local auditado. Ref: [totem-update-agent.production.service](/home/builder/totem-os/orange_pi_totem/scripts/board/systemd/totem-update-agent.production.service:15).
- O bloqueio esperado sob `stable` é `rc=41`, mas só é evidência válida se a policy inicial for exatamente `stable` e a rejeição for por incompatibilidade de canal. O updater valida canal/policy antes de aplicar local e `cmd_apply_local` retorna 41 em falha de validação. Ref: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:1325), [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:3832).

**Média**
- O estado esperado de symlinks muda: partindo de `current=C21.22` e `previous=C21.21`, após apply C21.23 deve ficar `current=C21.23`, `previous=C21.22`; após rollback, `current=C21.22`, `previous=C21.23`; após reapply final, `current=C21.23`, `previous=C21.22`. Não espere preservar C21.21 como `previous`. Ref: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:2561), [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:3878).
- Com Ethernet e Wi-Fi ativos, a coleta normal de conectividade tende a provar o transporte da rota default, historicamente Ethernet no C21.22. Isso preserva rede, mas não prova portal cativo real em Wi-Fi. Para C21.23, o repo cobre lógica/UX por self-tests; a própria especificação ainda exige prova física/emulada antes de suporte de campo. Ref: [200_C21_23_CAPTIVE_PORTAL_DETECTION.md](/home/builder/totem-os/orange_pi_totem/docs/product/200_C21_23_CAPTIVE_PORTAL_DETECTION.md:38).
- Abortável se houver sessão de settings ativa, lock/request de settings, lock de update ocupado, ou agent rodando. O updater trata esses casos com guardas próprios. Ref: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:2167).

**Baixa**
- O pacote C21.23 é coerente com o recorte: manifest `channel=homologation`, source commit `3e5dbf8`, sem evidência stable, payload só com `bin/`, `health/` e `manifest-fragment/`, sem systemd, NetworkManager profiles, player runtime, media ou updater. Ref: [manifest](/home/builder/totem-os/orange_pi_totem/releases/core-updates/c21.23-captive-portal-detection-20260716T214621Z-3e5dbf8/dadooh-totem-core-c21.23-captive-portal-detection-20260716T214621Z-3e5dbf8.manifest.json:2), [UPDATE_CONTRACT.md](/home/builder/totem-os/orange_pi_totem/docs/UPDATE_CONTRACT.md:188).

**Procedimento Mínimo Auditado**

1. Capturar baseline: `status`, policy, timer, agent, lock, player `NRestarts`, Ethernet/Wi-Fi, settings inactive.
2. Ainda sob `stable`, tentar `apply-local` do manifest C21.23 e exigir `rc=41`, sem mutação de `current/previous`.
3. Parar/isolar `totem-update-agent.timer`; confirmar timer inactive, agent inactive, lock livre.
4. Aplicar policy homologation exata, não usar `apply-github-latest`.
5. Aplicar localmente o manifest/payload C21.23; exigir `rc=0`.
6. Rodar self-tests do updater/core, wizard e Wi-Fi adapter; executar coleta normal de conectividade; confirmar player ativo, `NRestarts` inalterado, Ethernet e Wi-Fi preservados.
7. Executar rollback; exigir `current=C21.22`, `previous=C21.23`.
8. Reaplicar o mesmo pacote local; exigir `current=C21.23`, `previous=C21.22`.
9. Restaurar policy `stable`, reativar timer enabled+active, confirmar agent inactive, lock livre, player/rede preservados.

**Condições De Aborto**

Aborte em qualquer um destes pontos: baseline diferente do informado; policy não estável antes do bloqueio; bloqueio stable diferente de `rc=41`; qualquer `apply/rollback/reapply/self-test/coleta` com `rc!=0`; timer ou agent ativo durante policy homologation; lock ocupado; settings ativo/lock/request presente; uso de GitHub/latest/publicação/stable promotion/browser; `current/previous` inesperado; player inactive ou `NRestarts` aumentar; perda de Ethernet ou Wi-Fi; coleta alterando config/contexto/rede; persistência de URL/conteúdo de portal, credenciais ou SSID fora do contrato.

**GO/NO-GO**

GO condicionado para executar o ensaio local, assistido e reversível de C21.23 nesse procedimento.

NO-GO para qualquer conclusão além do recorte: stable, publicação, navegador, nova imagem ou suporte de campo para portal cativo real. Também é NO-GO imediato se qualquer condição de aborto ocorrer.