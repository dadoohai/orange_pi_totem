# Fluxo Produto V1 - onboarding, manutencao e recuperacao

Status: fluxo detalhado de produto. Nao implementa operacao real.

Data: 2026-05-03

## 1. Escopo

Este documento detalha fluxos V1 em passos, estados, acoes do operador,
mensagens principais, comportamento tecnico esperado e pendencias.

Ele nao executa testes, nao toca placa, nao usa rede real, nao escreve config
real, nao altera launcher, renderer, `systemd`, NetworkManager ou
`kiosky-player`.

## 2. Regras gerais

- Operador nao usa terminal, SSH ou JSON.
- Token/API, segredo, URL privada, payload, IDs reais, SSID, senha, IP,
  hostname, MAC, gateway, DNS e paths privados nao aparecem em tela,
  diagnostico ou evidencia.
- Player principal e setup/manutencao nao disputam tela.
- Config parcial nao inicia exibicao.
- Erros mostram codigo publico e proxima acao segura.
- Acoes destrutivas exigem confirmacao forte.

## 3. Fluxos

### 1. Boot com config valida

| Item | Definicao |
| --- | --- |
| Passos | 1. Totem liga. 2. Mostra "Dadooh / inicializando". 3. Verifica HDMI. 4. Verifica config. 5. Config valida. 6. Para qualquer tela de setup/status operacional. 7. Inicia player. 8. Converge para `player_running`. |
| Estados | `booting` -> `starting_player` -> `player_running`. |
| Acao do operador | Nenhuma. |
| Mensagens | "Inicializando"; "Iniciando exibicao"; em operacao normal, sem overlay persistente. |
| Tecnico | Launcher valida display e config, garante que renderer/setup nao esta ativo e inicia player. |
| Pendente | Homologar reboot/autoboot longo, cache/offline e segunda placa/cartao. |

### 2. Boot com config ausente

| Item | Definicao |
| --- | --- |
| Passos | 1. Totem liga. 2. Mostra inicializacao. 3. HDMI presente. 4. Config ausente/invalida/incompleta. 5. Player fica bloqueado. 6. Tela mostra configuracao pendente. 7. Operador inicia setup guiado. |
| Estados | `booting` -> `config_missing` -> `setup_start`. |
| Acao do operador | Selecionar "Iniciar configuracao" quando existir UI funcional. |
| Mensagens | "Configuracao pendente"; "Inicie a configuracao para liberar a exibicao." |
| Tecnico | Nao iniciar `kiosk.py` nem MPV principal; renderer/status pode ocupar tela. |
| Pendente | Setup funcional, entrada em manutencao e writer integrado ao fluxo. |

### 3. Setup de conexao

| Item | Definicao |
| --- | --- |
| Passos | 1. Operador abre setup. 2. Escolhe usar rede existente, Wi-Fi ou modo futuro de setup local. 3. Insere credencial somente em UI aprovada. 4. Sistema testa conectividade. 5. Sucesso avanca; falha permite tentar de novo ou trocar rede. |
| Estados | `setup_start` -> `wifi_select` -> `wifi_password` -> `wifi_testing` -> `wifi_ok` ou `wifi_error`. |
| Acao do operador | Escolher rede, informar senha no canal seguro, tentar novamente ou voltar. |
| Mensagens | "Escolha a conexao"; "Testando conexao"; "Conexao funcionando"; "Conexao limitada". |
| Tecnico | Fase futura usa adapter NetworkManager estreito, sem shell, com rollback e evidencia sanitizada. |
| Pendente | Adapter seguro, politica de credenciais, falhas controladas e portal/hotspot futuro. |

### 4. Ativacao/provisionamento

| Item | Definicao |
| --- | --- |
| Passos | 1. Conexao esta pronta ou modo mock aprovado. 2. Operador informa codigo/login ou escolhe lista futura. 3. Backend valida autorizacao. 4. Totem recebe credencial de runtime sem exibir segredo. 5. Falha mostra erro publico e retry. |
| Estados | `activation_pending` -> `activation_ok` ou `activation_failed`. |
| Acao do operador | Informar codigo/login futuro ou pedir suporte. |
| Mensagens | "Ativar totem"; "Codigo invalido ou expirado"; "Servico indisponivel, tente novamente." |
| Tecnico | Futuro backend emite token de dispositivo/station; operador nao ve token/API. |
| Pendente | Decidir login vs codigo vs lista; contrato backend; expiracao, revogacao e rotacao. |

### 5. Selecao de ambiente

| Item | Definicao |
| --- | --- |
| Passos | 1. Sistema exibe ambientes autorizados ou campo temporario. 2. Operador escolhe. 3. Sistema valida formato/autorizacao. 4. Selecionado avanca para rotacao. |
| Estados | `environment_select` -> `environment_selected` ou `environment_invalid`. |
| Acao do operador | Escolher ambiente ou corrigir entrada manual temporaria. |
| Mensagens | "Selecione o ambiente"; "Ambiente invalido"; "Ambiente selecionado." |
| Tecnico | Valor real nao vai para status publico, diagnostico ou evidencia. |
| Pendente | Modelo final de permissao, nomes publicos e validacao backend. |

### 6. Rotacao de tela

| Item | Definicao |
| --- | --- |
| Passos | 1. UI mostra orientacoes permitidas. 2. Operador escolhe. 3. Preview indica resultado. 4. Sistema salva escolha como candidata. |
| Estados | `rotation_select` -> `rotation_preview` -> `rotation_selected`. |
| Acao do operador | Selecionar paisagem/retrato ou graus permitidos. |
| Mensagens | "Orientacao da tela"; "Confirme se a imagem esta correta." |
| Tecnico | Aplicacao tecnica ainda a decidir; deve respeitar DRM/KMS e player. |
| Pendente | Confirmar se rotacao fica em config do player, MPV, renderer ou camada propria. |

### 7. Salvar e iniciar player

| Item | Definicao |
| --- | --- |
| Passos | 1. Tela de revisao mostra dados nao sensiveis. 2. Operador confirma. 3. Writer valida candidata. 4. Escrita atomica. 5. Revalidacao. 6. Setup sai. 7. Player inicia. |
| Estados | `review` -> `config_saving` -> `config_saved` -> `starting_player` -> `player_running`. |
| Acao do operador | Confirmar salvamento ou voltar. |
| Mensagens | "Revisar configuracao"; "Salvando configuracao"; "Iniciando exibicao." |
| Tecnico | Writer preserva config anterior quando aplicavel, bloqueia placeholders e nao imprime segredo. |
| Pendente | Integrar writer real ao setup funcional e validar rollback operacional. |

### 8. Trocar ambiente depois

| Item | Definicao |
| --- | --- |
| Passos | 1. Operador entra em manutencao. 2. Escolhe "Trocar ambiente". 3. UI mostra impacto: a exibicao sera reiniciada. 4. Seleciona novo ambiente. 5. Revisa e confirma. 6. Player para, config valida e player reinicia. |
| Estados | `maintenance` -> `environment_change` -> `config_saving` -> `starting_player`. |
| Acao do operador | Confirmar troca com impacto claro. |
| Mensagens | "A exibicao sera reiniciada"; "Ambiente alterado"; "Iniciando exibicao." |
| Tecnico | Deve evitar player com config parcial; rollback se nova config falhar. |
| Pendente | Decidir quando permitir troca e quem autoriza. |

### 9. Trocar rede depois

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Trocar rede". 3. Selecionar nova rede. 4. Testar. 5. Se sucesso, aplicar. 6. Se falha, preservar rede anterior quando possivel. |
| Estados | `maintenance` -> `network_change` -> `wifi_testing` -> `wifi_ok` ou `wifi_error`. |
| Acao do operador | Escolher rede, informar credencial em UI aprovada, confirmar aplicacao. |
| Mensagens | "Trocar rede"; "Nao foi possivel conectar"; "Rede anterior preservada." |
| Tecnico | Adapter deve manter rollback e nunca apagar Ethernet/conexoes antigas por engano. |
| Pendente | C4 gates: reboot/reconexao, falhas controladas e ciclo de vida de perfis. |

### 10. Rotacionar depois

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Orientacao da tela". 3. Escolher nova orientacao. 4. Preview. 5. Confirmar. 6. Aplicar com reinicio controlado se necessario. |
| Estados | `maintenance` -> `rotation_select` -> `rotation_apply` -> `starting_player`. |
| Acao do operador | Confirmar orientacao. |
| Mensagens | "A exibicao pode reiniciar"; "Orientacao salva." |
| Tecnico | Aplicacao nao deve deixar renderer e player disputando DRM/KMS. |
| Pendente | Implementacao tecnica e criterio de rollback visual. |

### 11. Diagnostico/manutencao

| Item | Definicao |
| --- | --- |
| Passos | 1. Operador entra em manutencao. 2. Tela mostra estado publico. 3. Operador abre diagnostico. 4. Sistema gera snapshot sanitizado. 5. Operador informa codigo/resumo ao suporte ou exporta pacote seguro futuro. |
| Estados | `maintenance` -> `diagnostics`. |
| Acao do operador | Ver estado, gerar diagnostico e compartilhar apenas codigo seguro. |
| Mensagens | "Manutencao"; "Diagnostico pronto"; "Sem dados sensiveis." |
| Tecnico | Usar allowlist; nao copiar status bruto, config ou logs brutos. |
| Pendente | Definir entrada em manutencao e formato final de exportacao. |

### 12. Reiniciar player

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Reiniciar exibicao". 3. Confirmacao simples. 4. Player para. 5. Player inicia. 6. Estado final aparece. |
| Estados | `maintenance` -> `restarting_player` -> `starting_player` -> `player_running` ou `player_error`. |
| Acao do operador | Confirmar reinicio. |
| Mensagens | "A exibicao ficara indisponivel por alguns instantes." |
| Tecnico | Preserva config, rede, cache e sistema. |
| Pendente | Implementar comando limitado sem shell e com status publico. |

### 13. Reset de configuracao

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Limpar configuracao". 3. UI mostra o que sera apagado. 4. Confirmacao forte. 5. Config operacional e ativacao local sao removidas conforme politica. 6. Totem volta para setup. |
| Estados | `maintenance` -> `config_reset_confirm` -> `config_missing`. |
| Acao do operador | Confirmar conscientemente ou cancelar. |
| Mensagens | "O totem voltara para configuracao pendente." |
| Tecnico | Nao apagar cache/rede se a politica do reset de config preservar esses dados. |
| Pendente | Definir preservacao de cache/rede/diagnostico. |

### 14. Reset de rede

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Limpar rede". 3. Confirmacao forte. 4. Perfil Wi-Fi dedicado e removido. 5. Totem volta para setup de conexao. |
| Estados | `maintenance` -> `network_reset_confirm` -> `wifi_select`. |
| Acao do operador | Confirmar reset e configurar nova rede. |
| Mensagens | "A conexao atual sera removida"; "Configure uma nova rede." |
| Tecnico | Nunca apagar Ethernet ou conexoes nao pertencentes ao produto. |
| Pendente | Ciclo de vida de perfis e adapter seguro. |

### 15. Reset de cache

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao. 2. "Limpar cache". 3. UI explica que midias serao baixadas novamente. 4. Confirmacao forte. 5. Cache e temporarios de conteudo sao removidos. 6. Player revalida/baixa conteudo quando houver rede. |
| Estados | `maintenance` -> `cache_reset_confirm` -> `starting_player` ou `offline_cache_empty`. |
| Acao do operador | Confirmar ou cancelar. |
| Mensagens | "O conteudo local sera baixado novamente." |
| Tecnico | Preservar config, rede e diagnostico essencial. |
| Pendente | Definir escopo exato de cache e comportamento offline sem cache. |

### 16. Factory reset

| Item | Definicao |
| --- | --- |
| Passos | 1. Manutencao protegida. 2. "Factory reset". 3. UI mostra escopo completo. 4. Confirmacao muito forte. 5. Limpa config, rede do produto, cache e estado local conforme politica. 6. Reinicia em setup. |
| Estados | `maintenance` -> `factory_reset_confirm` -> `factory_resetting` -> `config_missing`. |
| Acao do operador | Confirmar somente com autorizacao. |
| Mensagens | "Esta acao remove a configuracao do totem"; "Sera necessario configurar novamente." |
| Tecnico | Deve preservar sistema/app base; diagnostico pode ser preservado ou exportado antes. |
| Pendente | Escopo final de dados apagados e metodo de confirmacao. |

### 17. Hard reset local

| Item | Definicao |
| --- | --- |
| Passos | 1. UI normal indisponivel ou suporte orienta reset local. 2. Operador usa metodo fisico aprovado. 3. Totem detecta sinal local. 4. Entra em recovery/setup ou executa reset definido. 5. Mostra estado publico. |
| Estados | `hard_reset_requested` -> `recovery` -> `config_missing` ou `maintenance`. |
| Acao do operador | Acionar botao, teclado USB, pendrive, arquivo de reset ou combinacao ainda a decidir. |
| Mensagens | "Modo de recuperacao"; "Configuracao pendente." |
| Tecnico | Metodo deve ser limitado, auditavel e sem shell arbitrario. |
| Pendente | Escolher metodo fisico e evitar acionamento acidental. |

### 18. Player error

| Item | Definicao |
| --- | --- |
| Passos | 1. Player falha ou status fica stale. 2. Sistema tenta recuperacao automatica. 3. Se recupera, volta para exibicao. 4. Se persiste, mostra erro publico e acoes: tentar novamente, reiniciar exibicao, diagnostico. |
| Estados | `player_error` -> `restarting_player` -> `player_running` ou `maintenance`. |
| Acao do operador | Aguardar retry, reiniciar exibicao ou abrir diagnostico. |
| Mensagens | "Exibicao temporariamente indisponivel"; "O sistema tentara reiniciar." |
| Tecnico | Limite de retry, sem loop infinito, sem log bruto em tela. |
| Pendente | Validacao visual/operacional de `player_error`. |

### 19. Sem HDMI

| Item | Definicao |
| --- | --- |
| Passos | 1. Boot ou runtime detecta display ausente. 2. Nao renderiza tela. 3. Publica estado local `display_missing`. 4. Quando HDMI volta, reavalia config e segue para player/setup. |
| Estados | `display_missing` -> `booting` -> `player_running` ou `config_missing`. |
| Acao do operador | Verificar cabo HDMI e energia da tela. |
| Mensagens | Sem tela fisica; em diagnostico: "Tela nao detectada". |
| Tecnico | Nao iniciar player/renderer sem display. |
| Pendente | Revalidar em homologacao com config real e longos. |

### 20. Sem internet/backend

| Item | Definicao |
| --- | --- |
| Passos | 1. Rede local ou backend falha. 2. Runtime tenta retry. 3. Se ha cache, player continua. 4. Setup mostra conexao limitada. 5. Operador pode tentar novamente ou trocar rede. |
| Estados | `network_limited`, `backend_unavailable`, `offline_cache`, `wifi_error`. |
| Acao do operador | Tentar novamente, trocar rede ou chamar suporte. |
| Mensagens | "Conexao limitada"; "Servico temporariamente indisponivel"; "Exibindo conteudo salvo." |
| Tecnico | Nao expor endpoint, DNS, payload ou erro bruto; separar Wi-Fi, internet e backend. |
| Pendente | Politica de teste de internet/backend e cache/offline longo. |

### 21. Restauracao de app/sistema

| Item | Definicao |
| --- | --- |
| Passos | 1. Update/app falha ou sistema nao recupera por resets menores. 2. Suporte entra em recovery. 3. Seleciona release anterior ou imagem de recuperacao. 4. Healthcheck publico. 5. Volta a player/setup ou exige factory reset. |
| Estados | `recovery` -> `app_rollback` -> `starting_player` ou `factory_reset_confirm`. |
| Acao do operador | Suporte presencial/avancado executa procedimento aprovado. |
| Mensagens | "Restaurando versao anterior"; "Sistema restaurado"; "Configuracao precisa ser refeita." |
| Tecnico | Releases versionadas, rollback atomico, healthcheck e compatibilidade de config. |
| Pendente | Politica de update/rollback, recovery image e regravacao de cartao. |
