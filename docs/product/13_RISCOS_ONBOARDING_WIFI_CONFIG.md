# Riscos - onboarding Wi-Fi/configuracao

Status: planejamento C0-C2. Nao implementa mudancas.

Data: 2026-05-01

Este documento lista riscos de produto, operacao e seguranca para o onboarding
Wi-Fi/configuracao. Ele deve ser usado antes de qualquer implementacao de
hotspot, portal local, NetworkManager adapter, ativacao backend ou config
writer.

| Risco | Impacto | Mitigacao | Fase de teste |
| --- | --- | --- | --- |
| Derrubar SSH/bancada ao mexer em rede | Perda de acesso remoto, teste interrompido e risco de placa presa em estado ruim. | Comecar read-only, preservar Ethernet, snapshot antes/depois, prompt humano antes de alterar conexao ativa e rollback documentado. | C3, C4 |
| Salvar senha Wi-Fi em logs | Vazamento de credencial do cliente em journal, status, diagnostico ou README. | Nunca imprimir senha, mascarar entradas, revisar journal, sanitizar diagnostico e testar busca por termos sensiveis. | C2, C4 |
| Vazar `api_key` ou config privada | Comprometimento de backend e ambiente do cliente. | `api_key` fora da UI, fonte externa validada antes do player, status publico allowlisted e config privada nunca exibida. | C1, C5, C6, C7 |
| Portal local inseguro | Execucao indevida de comandos, exposicao de arquivos ou controle nao autorizado. | API pequena e allowlisted, sem shell, sem path arbitrario, sessoes com expiracao, CSRF/token local quando aplicavel. | C2, C7, C8 |
| Hotspot interferir em rede existente | Totem desconecta rede valida ou entra em estado ambiguo AP/cliente. | Hotspot em fase propria, regras claras de prioridade, nao desligar Ethernet, rollback de perfis NetworkManager. | Fase futura |
| Usuario configurar rede errada | Totem fica sem internet ou associado a rede inadequada. | Confirmacao visual, teste de conectividade, possibilidade de voltar/trocar rede e nao apagar conexao anterior valida antes da nova passar. | C4 |
| `environment_id` digitado errado | Totem pode apontar para ambiente incorreto ou ficar sem conteudo esperado. | Validar formato minimo, pedir confirmacao antes de salvar, nao publicar o valor em status/diagnostico e deixar validacao backend para fase futura. | C1, C5, C6 |
| `api_key` mal provisionada por env/mock/provisionamento | Operador completa a UI, mas player nao consegue operar ou falha em loop. | Preflight deve bloquear salvamento/inicio se `api_key` externa estiver ausente, publicar erro seguro e manter checklist de provisionamento separado da UI. | C1, C5, C6 |
| Config parcial ou substituicao sem validacao | Player inicia com config incompleta, falha em loop ou vaza erro interno. | Config writer atomico, validacao de schema e campos externos antes de substituir, preservar ultima config valida e publicar erro publico. | C5, C6 |
| C1 confundida com producao ou ativacao definitiva | Escopo documental minimo pode ser tratado como release de campo ou substituir indevidamente ativacao por codigo. | Marcar C1 como proposta/documentacao, preservar separacao RC1/desenvolvimento/producao e manter ADR-0008 como visao futura. | C1-C2 |
| Mock C2 parecer funcional em campo | Operador ou suporte pode acreditar que rede/config foram alteradas de verdade. | Rotular telas/evidencias como mock, nao usar em campo, nao ligar botoes a acoes reais e documentar que nao altera rede nem config. | C2 |
| Mock pedir senha real | Credencial real pode aparecer em tela, screenshot, journal ou evidencia. | Usar apenas senha ficticia, texto explicito "nao sera salva", nao persistir entrada e nao usar dados reais em validacao. | C2 |
| `environment_id` real aparecer em screenshot/log | Identificador operacional pode vazar em evidencia ou status publico. | Usar placeholders, nao registrar valores digitados, sanitizar screenshots/README e nao copiar entrada para status publico. | C2, C5 |
| Reset apagar dados uteis | Perda de evidencias, logs de suporte, config valida ou cache necessario. | Separar reset leve e factory reset, confirmacao forte, opcao de preservar diagnostico sanitizado e documentar escopo de limpeza. | C8 |
| Dependencia backend | Ativacao bloqueada se backend estiver indisponivel. | Estados publicos de retry, timeout curto, mensagens recuperaveis, suporte a Ethernet/retry e nao gravar config parcial. | C7 |
| Suporte remoto sem conectividade | Operador nao consegue ativar ou enviar diagnostico quando internet falha. | Tela local clara, diagnostico local sanitizado futuro, codigos publicos, fluxo de troca de rede e recuperacao por Ethernet em bancada. | C3, C4, C8 |
| HDMI ausente durante setup | Operador nao ve instrucao e pode assumir falha total. | `display_missing` continua sem renderer; setup fica seguro e tela reavalia estado quando HDMI voltar. | C1-C8 |
| QR funcional antes do backend/portal estar pronto | Operador escaneia fluxo inexistente ou inseguro. | C1 usa apenas placeholder explicito; QR real so quando portal e seguranca estiverem prontos. | C1, C2, C7 |
| Dados privados em status publico | SSID, URL, IDs ou paths vazam por `status.json`/SVG. | Allowlist de campos, sanitizacao automatica e checagem por termos sensiveis em cada rodada. | C1-C8 |
| Diagnostico publicar SSID, IP ou nome de conexao | Evidencia local pode vazar dados do cliente mesmo sem senha. | C3 deve publicar apenas estados agregados, omitir saida bruta, usar artefatos restritos e revisar evidencias antes de compartilhar. | C3 |
| Comando aparentemente read-only vazar dados sensiveis | `nmcli`, `ip` ou `iw` podem retornar SSID, BSSID, MAC, IP, gateway, hostname ou dominios internos. | Comandos C3 ficam em allowlist fechada, dados brutos nao sao gravados e qualquer texto auxiliar passa por sanitizacao/truncamento. | C3 |
| C3 ser usado como se fosse C4 | Suporte ou desenvolvimento pode tentar transformar diagnostico em configurador sem rollback. | Documentar C3 como read-only, bloquear comandos mutaveis por validacao interna e exigir plano humano separado para C4. | C3, C4 |
| Perder SSH durante C4 | Automacao remota pode ficar sem canal de controle durante alteracao de Wi-Fi. | Exigir Ethernet preservada, acesso fisico, operador humano presente, criterio de abortar e nenhuma insistencia remota se a sessao cair. | C4 |
| Derrubar Ethernet em C4 | Perda da linha de vida de bancada e risco de placa inacessivel. | Proibir comandos contra perfil/dispositivo Ethernet, confirmar Ethernet por C3 antes/depois e abortar se Ethernet nao estiver presente. | C4 |
| Apagar conexao antiga | Totem pode perder rede previamente funcional e dificultar recuperacao. | Criar somente perfil de teste, remover apenas `WIFI_TEST_CONNECTION_NAME`, nunca deletar conexoes antigas e revisar alvo antes de cada comando mutavel. | C4 |
| Publicar SSID ou senha em evidencia C4 | Credencial de teste ou rede real pode vazar em README, PR, issue ou logs. | Usar placeholders, rede de teste nao sensivel, senha de teste controlada, nao versionar artefatos brutos e revisar evidencia antes de compartilhar. | C4 |
| Senha aparecer em comando shell ou historico | Credencial pode ficar gravada em terminal, shell history, chat, README ou log de automacao. | Nao usar senha inline, exigir entrada interativa ou metodo aprovado, usar rede descartavel quando aplicavel e abortar se a senha puder ser registrada. | C4 |
| `nmcli --ask` via sessao remota registrar senha | Mesmo sem senha inline, prompt interativo pode ser capturado por transcript, log de ferramenta, terminal copiado ou historico operacional. | Codex nao executa comando que possa solicitar senha Wi-Fi; a acao com credencial acontece fora do agente, preferencialmente em console fisico/local. | C4 |
| Assumir que "nao inline" e suficiente | A senha pode nao estar no comando, mas ainda passar por chat, SSH gerenciado pelo agente ou transcript. | Tratar qualquer etapa de credencial como fora do Codex; usar placeholders, rede descartavel quando aplicavel e abortar se a senha passar pelo agente. | C4 |
| Prompt interativo capturado em log | Ferramentas de automacao podem registrar entrada, eco, erro, stack trace ou contexto de terminal. | Nao digitar senha em sessao controlada pelo agente, nao versionar output bruto e registrar apenas evidencia agregada depois. | C4 |
| SSID ou nome de conexao real aparecer em evidencia | Evidencia pode revelar rede interna mesmo sem publicar senha. | Usar placeholders, tratar qualquer output bruto como nao versionavel, revisar README e publicar apenas estados agregados do C3. | C4 |
| Humano colar output bruto no chat | Mesmo com credencial fora do agente, retorno humano pode expor SSID, nome real de conexao, IP, gateway, hostname, MAC, BSSID ou DNS real. | C4.2 limita respostas humanas a frases permitidas, proibe colar output bruto e usa evidencia apenas agregada do C3. | C4 |
| Humano enviar SSID ou nome real de conexao ao Codex | Mensagem humana pode vazar identificador de rede ou perfil interno. | Usar placeholders, rede de teste controlada e respostas sanitizadas como "conectou", "falhou", "perfil removido" ou "abortei". | C4 |
| Player ocupar a tela e impedir terminal local | Operador nao consegue inserir credencial fora do Codex enquanto o player continua na HDMI. | Definir canal seguro antes de nova tentativa: SSH humano fora do Codex, console fisico, tecnico local ou modo setup/manutencao futuro. | C4 |
| Falta de canal seguro levar a senha via Codex | Pressao operacional pode fazer operador tentar usar chat, transcript ou SSH gerenciado pelo agente para senha. | Se nao houver canal humano/local seguro, abortar antes de criar perfil ou conectar; Codex fica restrito a C3 e evidencia sanitizada. | C4 |
| Usar rede real de cliente cedo demais | A primeira rodada pode vazar dados ou afetar ambiente de cliente. | Primeira C4.1 deve usar rede de teste controlada e nao sensivel; rede real de cliente exige fase posterior e decisao propria. | C4 |
| Avancar para C4.1 sem acesso fisico | Falha de rollback remoto pode prender a placa em estado ruim. | C4.1 exige operador humano presente, acesso fisico, fonte/tela estaveis e aprovacao explicita antes de comandos mutaveis. | C4 |
| NetworkManager em estado ambiguo | Conexao cliente e AP competem; reboot nao recupera rede. | Adapter estreito, snapshots, perfis dedicados, rollback e testes com reboot. | C4, fase futura |
| Queda de energia durante setup | Config ou perfil de rede ficam parcialmente gravados. | Escrita atomica, estados de setup recuperaveis, validacao no boot e rollback para ultima config/perfil valido. | C4, C6, C8 |
| Manutencao virar shell remoto | Superficie de ataque e risco operacional alto. | Comandos limitados e nomeados, sem shell, confirmacao forte e logs sanitizados. | C8 |

## Riscos bloqueantes antes de producao

- Qualquer vazamento de senha Wi-Fi, `api_key`, URL privada, ID privado ou
  payload privado.
- Qualquer fluxo que derrube Ethernet de bancada sem confirmacao e rollback.
- Qualquer hotspot sem criterio de desligamento e recuperacao.
- Qualquer config writer que possa deixar JSON parcial como config ativa.
- Qualquer fluxo que inicie player com `api_key` externa ausente ou mal
  provisionada.
- Qualquer fluxo que trate `environment_id` manual como ativacao definitiva sem
  validacao e revisao de escopo.
- Qualquer mock que peca senha real ou use `environment_id` real em evidencia.
- Qualquer portal local que exponha shell, path arbitrario ou stack trace.

## Evidencias esperadas por fase

- C1: escopo, fluxo e maquina de estados documentados, sem implementacao
  operacional.
- C2: mock visual/formulario rotulado como mock, sem rede real, sem senha real,
  sem persistencia e sem valores reais em evidencia.
- C3: diagnostico Wi-Fi read-only com prova de que nao altera conexoes.
- C4: Wi-Fi configurado em bancada com Ethernet preservada e rollback testado.
- C5: config writer minimo/mock com erro de `api_key` externa ausente.
- C6: config writer real atomico com config invalida, queda simulada e
  rollback.
- C7: ativacao por codigo, login ou lista de ambientes com erros publicos e sem
  secrets na UI/logs.
- C8: rotacao, troca de ambiente, manutencao/reset com confirmacao forte e
  preservacao de evidencias quando definido.
