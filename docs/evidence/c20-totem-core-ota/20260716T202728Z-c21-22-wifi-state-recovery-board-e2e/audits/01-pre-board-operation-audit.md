**Findings**

**Alta:** antes de mudar a policy para `homologation`, o timer deve estar parado e o `totem-update-agent.service` inativo. A unidade de produção chama `apply-github-latest` para `totem-core`, então deixar o timer ativo durante a janela homologation abre risco de concorrência ou seleção remota fora do pacote local: [totem-update-agent.production.service](/home/builder/totem-os/orange_pi_totem/scripts/board/systemd/totem-update-agent.production.service:15).

**Alta:** C21.22 tem pacote commitado, mas não vi pasta de evidência de placa nem gate C21.22 commitado. O pacote é coerente, porém o claim atual deve ficar em “candidato empacotado pronto para ensaio local”, não “validado na placa”. O manifest é `homologation`, `totem-core`, `source_dirty=false`, sem promoção stable: [manifest](/home/builder/totem-os/orange_pi_totem/releases/core-updates/c21.22-wifi-state-recovery-20260716T194811Z-9526cf9/dadooh-totem-core-c21.22-wifi-state-recovery-20260716T194811Z-9526cf9.manifest.json:1).

**Média:** o procedimento proposto necessariamente muda o rollback direto. Partindo de C21.21 current/C21.20 previous, após apply C21.22 o `previous` vira C21.21; após rollback/reapply final, o estado esperado é C21.22 current/C21.21 previous. Não espere preservar C21.20 como `previous`. O updater faz exatamente essa troca de symlinks: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:2561).

**Média:** abortar se houver settings session, request pendente ou lock ocupado. O updater tem guard para settings e lock global no apply/rollback local; tratar rc 40 como defer operacional, rc 49/51/52 como bloqueio até entender a causa: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:3832).

**Baixa:** `release_dir_exists_will_overwrite` na reaplicação é esperado, desde que seja a mesma versão/SHA C21.22. Não é blocker isolado.

**Procedimento Mínimo Seguro**

1. Pré-checar pacote: SHA do payload C21.22 `a98c3ad1...e523d60`; manifest SHA observado `9ee79d9c...af0983d`. O tar contém só a allowlist de core; conferi os scripts do tar contra o commit `9526cf9`. O empacotador exclui secrets, config, logs, NetworkManager profiles, systemd, player launchers e updater self-update: [build_totem_core_release_package.sh](/home/builder/totem-os/orange_pi_totem/scripts/deploy/build_totem_core_release_package.sh:8).

2. Capturar baseline da placa: `totem-updatectl status --component totem-core`, timer/service, `NRestarts`, Ethernet/Wi-Fi, settings. Base esperada conforme C21.21: current C21.21, previous C21.20, policy stable, timer active/enabled, player active, restarts 0, end0/wlan0 connected: [runtime.final.txt](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/board/runtime.final.txt:3).

3. Parar o timer para isolar o ensaio; confirmar timer inactive, enabled preservado, e `totem-update-agent.service` inactive.

4. Ainda sob policy `stable`, rodar `apply-local --component totem-core` com o manifest C21.22 e esperar rc `41` por canal incompatível. Esse é o bloqueio correto; C21.21 provou o mesmo padrão: [summary.txt](/home/builder/totem-os/orange_pi_totem/docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/board/summary.txt:3). O updater exige canal exato entre manifest e policy: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:1325).

5. Trocar temporariamente `/data/updates/policy.json` para homologation, mantendo `allowed_components=["totem-core"]`, `device_track="c18-hwdecode"`, `allow_downgrade=false`. Timer continua parado.

6. Aplicar C21.22 por pacote local. Esperado: rc 0, current C21.22, previous C21.21, health de `totem-core` verde. O apply local valida manifest, SHA, extrai allowlist e roda health antes/depois da promoção: [totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:2435).

7. Rodar QA não persistente contra `/data/core/totem/current`: self-tests do updater/core, wizard e adapter; preview/replay/galeria somente com saída em `/tmp`. Os harnesses de galeria e replay declaram não tocar Wi-Fi, writer, serviços, player, MPV real ou backend: [generate_ui_ux_gallery.py](/home/builder/totem-os/orange_pi_totem/scripts/qa/generate_ui_ux_gallery.py:2), [run_wizard_input_replay.py](/home/builder/totem-os/orange_pi_totem/scripts/sim/run_wizard_input_replay.py:2).

8. Executar rollback. Esperado: rc 0, current C21.21, previous C21.22. Depois reaplicar C21.22. Esperado final: current C21.22, previous C21.21.

9. Restaurar policy stable e reativar timer para active/enabled. Checagem final: policy stable, timer active/enabled, settings inactive, player active sem aumento de restarts, end0 e wlan0 connected, status current/previous conforme acima.

**Abortar Se**

Qualquer divergência do baseline C21.21/C21.20; serviço de update já ativo; lock busy não explicado; settings guard não limpo; stable block diferente de rc 41; policy homologation não exata; timer ativo durante homologation; apply/rollback/reapply rc != 0; current/previous inesperado; self-test/QA falhar; aumento de `NRestarts`; perda de Ethernet/Wi-Fi; tentativa de usar GitHub/latest, publicar stable, rodar wizard real ou aplicar Wi-Fi real.

**Veredito**

GO condicionado para ensaio local assistido de C21.22 com o procedimento acima. NO-GO para claim de stable, public release, timer real/GitHub, ou validação de conectividade física além das observações finais. O estado final operacional correto, se tudo passar, é C21.22 current, C21.21 previous, policy/timer stable restaurados.