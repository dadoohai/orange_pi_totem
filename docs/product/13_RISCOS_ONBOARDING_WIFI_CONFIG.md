# Riscos - onboarding Wi-Fi/configuracao

Status: planejamento C0. Nao implementa mudancas.

Data: 2026-05-01

Este documento lista riscos de produto, operacao e seguranca para o onboarding
Wi-Fi/configuracao. Ele deve ser usado antes de qualquer implementacao de
hotspot, portal local, NetworkManager adapter, ativacao backend ou config
writer.

| Risco | Impacto | Mitigacao | Fase de teste |
| --- | --- | --- | --- |
| Derrubar SSH/bancada ao mexer em rede | Perda de acesso remoto, teste interrompido e risco de placa presa em estado ruim. | Comecar read-only, preservar Ethernet, snapshot antes/depois, prompt humano antes de alterar conexao ativa e rollback documentado. | C3, C4 |
| Salvar senha Wi-Fi em logs | Vazamento de credencial do cliente em journal, status, diagnostico ou README. | Nunca imprimir senha, mascarar entradas, revisar journal, sanitizar diagnostico e testar busca por termos sensiveis. | C2, C4, C5 |
| Vazar `api_key` ou config privada | Comprometimento de backend e ambiente do cliente. | Operador usa codigo curto, backend entrega config por canal seguro, status publico allowlisted e config privada nunca exibida. | C6, C7 |
| Portal local inseguro | Execucao indevida de comandos, exposicao de arquivos ou controle nao autorizado. | API pequena e allowlisted, sem shell, sem path arbitrario, sessoes com expiracao, CSRF/token local quando aplicavel. | C2, C5, C8 |
| Hotspot interferir em rede existente | Totem desconecta rede valida ou entra em estado ambiguo AP/cliente. | Hotspot em fase propria, regras claras de prioridade, nao desligar Ethernet, rollback de perfis NetworkManager. | C5 |
| Usuario configurar rede errada | Totem fica sem internet ou associado a rede inadequada. | Confirmacao visual, teste de conectividade, possibilidade de voltar/trocar rede e nao apagar conexao anterior valida antes da nova passar. | C4, C5 |
| Config parcial | Player inicia com config incompleta, falha em loop ou vaza erro interno. | Config writer atomico, validacao de schema antes de substituir, preservar ultima config valida e publicar erro publico. | C7 |
| Reset apagar dados uteis | Perda de evidencias, logs de suporte, config valida ou cache necessario. | Separar reset leve e factory reset, confirmacao forte, opcao de preservar diagnostico sanitizado e documentar escopo de limpeza. | C8 |
| Dependencia backend | Ativacao bloqueada se backend estiver indisponivel. | Estados publicos de retry, timeout curto, mensagens recuperaveis, suporte a Ethernet/retry e nao gravar config parcial. | C6 |
| Suporte remoto sem conectividade | Operador nao consegue ativar ou enviar diagnostico quando internet falha. | Tela local clara, diagnostico local sanitizado futuro, codigos publicos, fluxo de troca de rede e recuperacao por Ethernet em bancada. | C3, C4, C9 |
| HDMI ausente durante setup | Operador nao ve instrucao e pode assumir falha total. | `display_missing` continua sem renderer; setup fica seguro e tela reavalia estado quando HDMI voltar. | C1, C5, C9 |
| QR funcional antes do backend/portal estar pronto | Operador escaneia fluxo inexistente ou inseguro. | C1 usa apenas placeholder explicito; QR real so quando portal e seguranca estiverem prontos. | C1, C2, C5 |
| Dados privados em status publico | SSID, URL, IDs ou paths vazam por `status.json`/SVG. | Allowlist de campos, sanitizacao automatica e checagem por termos sensiveis em cada rodada. | C1-C9 |
| NetworkManager em estado ambiguo | Conexao cliente e AP competem; reboot nao recupera rede. | Adapter estreito, snapshots, perfis dedicados, rollback e testes com reboot. | C4, C5 |
| Queda de energia durante setup | Config ou perfil de rede ficam parcialmente gravados. | Escrita atomica, estados de setup recuperaveis, validacao no boot e rollback para ultima config/perfil valido. | C4, C7, C9 |
| Manutencao virar shell remoto | Superficie de ataque e risco operacional alto. | Comandos limitados e nomeados, sem shell, confirmacao forte e logs sanitizados. | C8 |

## Riscos bloqueantes antes de producao

- Qualquer vazamento de senha Wi-Fi, `api_key`, URL privada, ID privado ou
  payload privado.
- Qualquer fluxo que derrube Ethernet de bancada sem confirmacao e rollback.
- Qualquer hotspot sem criterio de desligamento e recuperacao.
- Qualquer config writer que possa deixar JSON parcial como config ativa.
- Qualquer portal local que exponha shell, path arbitrario ou stack trace.

## Evidencias esperadas por fase

- C1: screenshots/previews sanitizados, sem QR funcional.
- C2: portal mock local sem rede real e sem secrets.
- C3: diagnostico Wi-Fi read-only com prova de que nao altera conexoes.
- C4: Wi-Fi configurado em bancada com Ethernet preservada e rollback testado.
- C5: hotspot com criterios de entrada, saida, reboot e conflito AP/cliente.
- C6: ativacao por codigo com erros publicos e sem secrets na UI/logs.
- C7: config writer atomico com config invalida, queda simulada e rollback.
- C8: reset/reparo com confirmacao forte e preservacao de evidencias quando
  definido.
- C9: validacao de campo cobrindo operador nao tecnico, rede errada, internet
  ausente, HDMI ausente e recuperacao.
