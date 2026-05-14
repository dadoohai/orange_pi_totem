# Screen inventory

| screen_id | function | primary | secondary | confusion_risk | preview |
| --- | --- | --- | --- | --- | --- |
| splash.boot | Feedback publico de transicao: boot. | Aguardar | Nenhuma. | low | yes |
| splash.firstboot | Feedback publico de transicao: firstboot. | Aguardar | Nenhuma. | medium | yes |
| splash.preparing | Feedback publico de transicao: preparing. | Aguardar | Nenhuma. | low | yes |
| splash.player | Feedback publico de transicao: player. | Aguardar | Nenhuma. | low | yes |
| splash.setup | Feedback publico de transicao: setup. | Aguardar | Nenhuma. | low | yes |
| splash.saving | Feedback publico de transicao: saving. | Aguardar | Nenhuma. | low | yes |
| splash.config_pending | Feedback publico de transicao: config_pending. | Aguardar | Nenhuma. | low | yes |
| splash.reboot | Feedback publico de transicao: reboot. | Aguardar | Nenhuma. | low | yes |
| splash.shutdown | Feedback publico de transicao: shutdown. | Aguardar | Nenhuma. | medium | yes |
| wizard.orientation.landscape | Escolher orientacao fisica da tela. | Enter visualiza | Esc cancela | medium | yes |
| wizard.orientation.portrait | Confirmar orientacao em tela vertical. | Enter OK | B volta | Esc cancela | low | yes |
| wizard.network.choice | Escolher caminho de conexao. | Enter OK | Esc cancela | medium | yes |
| wizard.wifi.empty | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | low | yes |
| wizard.wifi.three_networks | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | low | yes |
| wizard.wifi.eighteen_page_1 | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | medium | yes |
| wizard.wifi.eighteen_page_2 | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | medium | yes |
| wizard.wifi.eighteen_page_3 | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | medium | yes |
| wizard.wifi.refreshing | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | low | yes |
| wizard.wifi.scan_failure_cached | Listar, atualizar e selecionar rede Wi-Fi local. | Enter OK | R atualiza | B/Esc volta | low | yes |
| wizard.wifi.password_hidden | Coletar senha Wi-Fi no HDMI local. | Enter OK | F2 alterna | Ctrl+B volta | Ctrl+U limpa | low | yes |
| wizard.wifi.password_visible | Coletar senha Wi-Fi no HDMI local. | Enter OK | F2 alterna | Ctrl+B volta | Ctrl+U limpa | medium | yes |
| wizard.environment | Coletar identificador de ambiente. | Enter | Nenhuma. | low | yes |
| wizard.review | Revisar escolhas antes de gravar. | Enter | B volta | medium | yes |
| wizard.saving | Indicar operacao ocupada de salvamento. | Aguardar | Nenhuma. | low | yes |
| wizard.complete | Encerrar fluxo com sucesso. | Enter | Nenhuma. | low | yes |
| wizard.cancel | Encerrar fluxo por cancelamento explicito. | Enter | Nenhuma. | low | yes |
| wizard.error | Recuperar de erro sem salvar. | Enter volta | Esc cancela | medium | yes |
| boot | Mostrar primeiro feedback de energia/boot. | Aguardar | Suporte se persistir sem mudanca. | medium | yes |
| firstboot | Cobrir preparacao tecnica inicial. | Aguardar | Suporte se nao avancar. | medium | yes |
| config_pending | Pedir configuracao local. | Pressionar F10 | Suporte remoto se teclado indisponivel. | low | yes |
| config_missing | Explicar ausencia de configuracao. | Pressionar F10 | Suporte remoto. | medium | yes |
| open_settings | Confirmar recebimento do F10. | Aguardar | Cancelar dentro do wizard. | medium | yes |
| orientation | Escolher orientacao da tela. | Enter confirma | Esc cancela. | low | yes |
| connection | Escolher caminho de conexao. | Enter confirma | Esc volta. | low | yes |
| wifi_list | Selecionar rede sintetica por sinal. | Enter escolhe | R atualiza. | medium | yes |
| wifi_password_hidden | Digitar senha sem expor valor. | Enter confirma | F2 mostra/oculta. | low | yes |
| wifi_password_visible | Mostrar senha apenas no HDMI local. | Enter confirma | F2 oculta. | medium | yes |
| wifi_wrong_password | Explicar erro de senha ou associacao. | Enter tenta novamente | Ctrl+B volta para redes. | high | yes |
| weak_wifi | Avisar risco de sinal fraco. | Escolher TEST_WIFI_STRONG | R atualiza. | medium | yes |
| environment | Coletar ambiente sintetico. | Enter confirma | Ctrl+B volta. | medium | yes |
| review | Revisar dados sinteticos antes de salvar. | Enter salva | Ctrl+B volta. | low | yes |
| saving | Mostrar salvamento em andamento. | Aguardar | Nenhuma. | medium | yes |
| complete | Confirmar sucesso. | Aguardar | Nenhuma. | low | yes |
| starting_player | Cobrir handoff para player. | Aguardar | Suporte se persistir. | medium | yes |
| loading_content | Mostrar espera por API/cache/midia. | Aguardar | Suporte se persistir. | medium | yes |
| waiting_for_api | Classificar espera por API. | Aguardar | Suporte se persistir. | high | yes |
| waiting_for_media | Classificar preparo de midias. | Aguardar | Suporte se persistir. | high | yes |
| error_no_content | Evitar tela preta quando nao ha conteudo. | Aguardar retry | Suporte. | high | yes |
| playing_status | Representar player normal sem usar midia real. | Nenhuma | F10 suporte. | low | yes |
| update_checking | Mostrar verificacao de update. | Aguardar | Suporte se persistir. | medium | yes |
| update_applying | Mostrar aplicacao de update. | Aguardar | Suporte se persistir. | high | yes |
| update_failed | Mostrar falha segura de update. | Aguardar | Suporte. | medium | yes |
| maintenance_support | Dar caminho seguro de suporte. | Coletar status | Reabrir configuracao. | medium | yes |
