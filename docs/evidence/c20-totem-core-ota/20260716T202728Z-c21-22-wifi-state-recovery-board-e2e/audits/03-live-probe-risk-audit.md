**Veredito**

GO condicionado. O script é apropriado como QA visual real de baixo a médio risco para C21.22 somente para provar: wizard abre no HDMI real, indicador `Ethernet + Dadooh online` aparece no framebuffer, cancelamento não chama writer, player volta, e hashes de config/context/network ativo são preservados. Ele não é prova de Wi-Fi real, retry/recovery de Wi-Fi, pareamento, writer, nem soak.

**Achados**

1. **Risco operacional real, mas controlado:** o script não é observacional puro. Ele inicia `totem-open-settings.service`, para/reinicia `kiosky-player.service` via sessão, injeta teclas e usa cleanup externo. Ver [probe:210](/home/builder/totem-os/orange_pi_totem/scripts/qa/c20_connectivity_indicator_board_probe.sh:210), [session:1631](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_open_settings_session.sh:1631), [cleanup:144](/home/builder/totem-os/orange_pi_totem/scripts/qa/c20_connectivity_indicator_board_probe.sh:144). Seguro para bancada se a interrupção temporária do player for aceitável.

2. **Falso negativo provável se Ethernet não for a rota default.** A placa pode ter Ethernet e Wi-Fi ativos, mas o probe exige `transport == ethernet` e `internet == online`; o adaptador escolhe pelo default route verificado. Ver [probe:278](/home/builder/totem-os/orange_pi_totem/scripts/qa/c20_connectivity_indicator_board_probe.sh:278) e [adapter:1255](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_wifi_nm_adapter.py:1255).

3. **Falso negativo se layout inicial não for paisagem.** A asserção por pixel codifica a região paisagem `x=704..780, y=34..68`; o wizard tem posição diferente em retrato. Ver [probe:53](/home/builder/totem-os/orange_pi_totem/scripts/qa/c20_connectivity_indicator_board_probe.sh:53) e [wizard:861](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:861).

4. **A seed de homologação aumenta risco desnecessário.** O serviço pode criar `apply-policy.json` a partir de `/data/state/totem-settings/private-values.seed.json` no `ExecStartPre`; o probe cancela antes de salvar, mas para esta execução “sem aplicação real” eu trataria seed presente como NO-GO. Ver [service:13](/home/builder/totem-os/orange_pi_totem/scripts/board/totem-open-settings.service:13) e [policy:204](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_settings_lab_apply_policy.sh:204).

5. **Preservação de rede é boa, mas limitada.** Ele compara conexões ativas e rota IPv4 default, não perfis NM completos, DNS, IPv6 ou rádio. Adequado para “não houve aplicação Wi-Fi real”, não para provar ausência absoluta de toda mutação de rede. Ver [probe:195](/home/builder/totem-os/orange_pi_totem/scripts/qa/c20_connectivity_indicator_board_probe.sh:195).

**Impacto de `9526cf9`**

A mudança torna o probe mais valioso porque C21.22 agora diferencia `online/limited/offline/unknown`, usa prova bounded do serviço Dadooh e evita atribuir prova de uma rota a outro transporte. Ver [wizard:567](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:567) e [wizard:659](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:659). O custo é mais sensibilidade a rota default, backend/DNS e estado `unknown`.

**Critérios GO**

GO somente se todos forem verdadeiros:

- C21.22 aplicada e bootada; player saudável.
- `totem-open-settings.service` inativo, sem wizard/openvt rodando, sem lock/request/apply-policy.
- `/data/state/totem-settings/private-values.seed.json` ausente.
- `/tmp/c20_uinput_key_sequence.py` executável com SHA `b076857006a2ec0e9d87e183d2806f026564c47f23d2d066bc0ff601f6953b23`.
- `/dev/fb0` com virtual size >= `1024x768` e wizard em layout paisagem/invertido, não retrato.
- Rota default única/verificada por Ethernet e Dadooh health alcançável.
- Aceita-se pausar o player durante a sessão e restaurá-lo ao final.

**Critérios NO-GO**

NO-GO se qualquer item acima falhar, ou se a única placa estiver em janela onde uma parada/restart do player não é aceitável. Se rodar e falhar por `verified_ethernet_transport_missing`, `dadooh_service_not_reachable`, portrait/framebuffer ou contexto inicial inesperado, trate como inconclusivo de harness, não reprovação automática de C21.22.

Não modifiquei nada. `bash -n` passou para os scripts revisados e o working tree ficou limpo.