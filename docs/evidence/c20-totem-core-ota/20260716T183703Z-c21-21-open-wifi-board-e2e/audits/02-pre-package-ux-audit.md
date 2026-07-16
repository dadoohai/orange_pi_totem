**Findings**

**Alta:** nenhum bloqueador encontrado.

**Média:** cobertura ainda não prova AP aberto real. O replay é explicitamente sintético e bloqueia subprocessos/NetworkManager em [run_wizard_input_replay.py](/home/builder/totem-os/orange_pi_totem/scripts/sim/run_wizard_input_replay.py:4) e [run_wizard_input_replay.py](/home/builder/totem-os/orange_pi_totem/scripts/sim/run_wizard_input_replay.py:95). A evidência confirma isso: `networkmanager_not_called_by_replay` passa em [/tmp/m9-open-wifi-replay/summary.md](/tmp/m9-open-wifi-replay/summary.md:31), e a galeria marca `networkmanager_touched=false` / `wifi_real_changed=false` em [/tmp/m9-open-wifi-gallery/run-summary.json](/tmp/m9-open-wifi-gallery/run-summary.json:28). Isso não invalida o candidato off-board, mas não deve ser vendido como validação em AP aberto real.

**Baixa:** a tela anterior de escolha de conexão ainda mostra “Senha protegida.” em [totem_setup_visual_wizard.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:5469). O fluxo aberto em si não pede senha e as telas específicas estão corretas, mas essa copy genérica ainda carrega expectativa de senha antes de uma rede aberta.

**Sem finding:** não encontrei regressão WPA no diff. O caminho WPA segue coletando senha, preservando retry e gerando `[wifi-security] key-mgmt=wpa-psk`; rede aberta gera payload sem `psk`, keyfile sem `[wifi-security]`, e retry direto sem tela de senha.

**Veredito**

Aprovado para candidato off-board do marco. Não aprovado como evidência final de AP aberto real em placa; esse teste continua pendente. Executei apenas auditoria somente leitura e `git diff --check`, sem implementar nem reexecutar fluxos que escrevem artefatos.

## Resolução Pós-Auditoria

O finding baixo de copy foi corrigido antes do empacotamento para
`Senha somente quando necessaria.` e a correção está no tar C21.21. A limitação
de AP aberto real permanece válida e explicitamente pendente.
