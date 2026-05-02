# Riscos - onboarding Wi-Fi/configuracao

Status: planejamento C0-C6. Nao implementa mudancas.

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
| Config parcial ou substituicao sem validacao | Player inicia com config incompleta, falha em loop ou vaza erro interno. | Config writer atomico, validador dry-run antes de C6, validacao de schema e paths antes de substituir, preservar ultima config valida e publicar erro publico. | C5, C5.1, C6 |
| Mock C5 ser confundido com config real | Operador, suporte ou desenvolvimento pode tratar `config.candidate.mock.json` como configuracao ativa ou pronta para campo. | Nomear arquivos como mock, gravar somente em `/tmp`, documentar que C5 nao altera config real, validar em C5.1 e exigir C6 separado para `/data/config/config.json`. | C5, C5.1 |
| `api_key` mock virar producao | Placeholder pode ser copiado para config real e mascarar erro de provisionamento. | Usar `API_KEY_MOCK_NOT_FOR_PRODUCTION`, bloquear placeholders em `--real-dry-run`, bloquear secrets reais em evidencia, revisar antes de C6 e exigir origem real aprovada fora da UI. | C5, C5.1, C6 |
| Escrita acidental em `/data` durante C5 | Mock pode alterar config real ou deixar artefato parcial em path persistente. | Recusar `--out-dir` fora de `/tmp`, self-test de guardrails, escrita atomica apenas no out-dir e evidencia confirmando nada em `/data`. | C5 |
| Validador imprimir `api_key` em relatorio | Um dry-run pode proteger a escrita real, mas ainda vazar segredo em `summary.txt`, status, stdout ou evidencia. | C5.1 registra apenas presenca e placeholder detectado, nunca valor de `api_key`, nao copia config candidata para output e revisa ausencia de secrets. | C5.1, C6 |
| Validar apenas schema e esquecer paths | Config com campos presentes, mas paths fora do perfil appliance, pode quebrar runtime, gravar em local errado ou mascarar problema de permissao. | C5.1 valida regras de path como strings antes de C6: cache sob `/data/media`, estado sob `/data/state`, status/IPC/runtime sob `/tmp` e logs nos destinos permitidos. | C5.1, C6 |
| Placeholder C5 passar em real-dry-run | C6 pode receber `api_url`, `api_key`, `environment_id` ou `station_id` mock e parecer configurado sem estar pronto para producao. | C5.1 tem modo `--real-dry-run` que bloqueia placeholders conhecidos, dominios `.invalid`, valores vazios e rotulos de mock/test/example/placeholder. | C5.1, C6 |
| Placeholder virar producao durante C6 | Mesmo com C5/C5.1, uma config candidata pode ser promovida manualmente com valores mock ou `.invalid`. | C6.1-preflight exige `--real-dry-run` limpo antes de C6.3, bloqueio de placeholders, revisao humana e evidencia sem copiar config. | C6 |
| Dados reais passarem pelo chat | `api_key`, URL privada, IDs reais ou payload podem ficar registrados em transcript, issue, PR, README ou resumo. | C6.1-preflight exige canal local privado para dados reais, proibe envio pelo chat e aborta se a execucao depender de publicar valor real. | C6.1-preflight, C6.3 |
| Config real ser versionada | `/data/config/config.json` ou candidata real pode entrar no Git e expor secrets. | Config real e candidata real ficam fora do Git; evidencia publica apenas estados agregados; revisar `git status --short --untracked-files=all` antes de encerrar. | C6.1-preflight, C6.2, C6.3 |
| `api_key` vazar em backup ou evidencia | Backup da config real e README de rodada podem conter segredo ou facilitar copia indevida. | Backup deve ter permissoes restritas e nunca ser publicado; evidencia registra apenas existencia/resultado, sem conteudo da config ou backup. | C6 |
| Backup conter secret com permissao ampla | Um backup correto em conteudo, mas legivel por usuario indevido, expande a superficie de vazamento da `api_key`. | Preflight define owner, group e mode esperados; writer real aplica permissao restrita ao backup; C6.3 registra apenas permissao observada, sem conteudo. | C6.1-preflight, C6.2, C6.3 |
| Permissoes incorretas na config real | Player pode nao ler a config ou usuarios indevidos podem ler secrets. | C6.0 planeja owner/grupo, mode restrito, validacao na placa e bloqueio de inicio do player se a config nao for legivel pelo usuario/grupo esperado. | C6 |
| Config parcial por queda de energia | Queda durante temporario, backup ou rename pode deixar config truncada, backup parcial ou estado ambiguo. | C6.0 exige escrita atomica no mesmo diretorio, fsync de arquivo e diretorio, backup validado, deteccao de temporario/parcial no boot e rollback. | C6 |
| Launcher iniciar player antes da validacao | Player pode iniciar com config incompleta, placeholder ou permissao errada e falhar em loop. | Launcher deve iniciar player somente apos JSON valido, contrato minimo valido, paths validos, `api_key` presente, placeholders bloqueados e renderer/setup parado. | C6 |
| Player iniciar automaticamente durante escrita | Servico ativo pode perceber arquivo parcial, temporario ou config ainda nao revalidada e iniciar o player cedo demais. | C6.1-preflight exige decisao sobre servico parado, config path temporario, bloqueio do launcher ou override temporario; C6.3 aborta se esse controle nao estiver claro. | C6.1-preflight, C6.3 |
| Evidencia publicar `api_url`, `environment_id` ou `station_id` reais | Mesmo sem `api_key`, evidencia pode revelar ambiente, cliente, endpoint privado ou identificador operacional. | README de C6.3 deve ser sanitizado, com apenas passou/falhou, presenca de `api_key`, backup, permissoes e conclusao; valores reais ficam fora de chat/log/evidencia. | C6.1-preflight, C6.3 |
| C1 confundida com producao ou ativacao definitiva | Escopo documental minimo pode ser tratado como release de campo ou substituir indevidamente ativacao por codigo. | Marcar C1 como proposta/documentacao, preservar separacao RC1/desenvolvimento/producao e manter ADR-0008 como visao futura. | C1-C2 |
| Mock C2 parecer funcional em campo | Operador ou suporte pode acreditar que rede/config foram alteradas de verdade. | Rotular telas/evidencias como mock, nao usar em campo, nao ligar botoes a acoes reais e documentar que nao altera rede nem config. | C2 |
| Mock pedir senha real | Credencial real pode aparecer em tela, screenshot, journal ou evidencia. | Usar apenas senha ficticia, texto explicito "nao sera salva", nao persistir entrada e nao usar dados reais em validacao. | C2 |
| `environment_id` real aparecer em screenshot/log/evidencia C5 | Identificador operacional pode vazar em README, status mock, summary ou chat. | Usar `ENVIRONMENT_ID_MOCK`, redigir valores nao mock em textos auxiliares, nao versionar artefatos brutos de `/tmp` e manter evidencia sanitizada. | C2, C5 |
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
| Perfil de teste persistente influenciar fases futuras | Rodadas posteriores podem interpretar rede de teste como estado desejado, mascarar falhas ou alterar comportamento de reconexao. | Remover explicitamente o perfil/configuracao de teste por acao humana local quando definido, registrar resposta sanitizada e rodar C3 final sem publicar lista de conexoes. | C4, C5 |
| Esquecer pendencias C4 ao avancar C5/C6 | Config writer e onboarding podem evoluir assumindo que Wi-Fi ja esta pronto para produto, deixando reboot, falhas, adapter, credenciais e estados sem gate. | Manter backlog/gates C4 documentados em `docs/product/27_C4_WIFI_BACKLOG_E_GATES.md`, referenciar no roadmap e exigir retomada antes de produto/campo. | C4, C5, C6 |
| Tratar Wi-Fi hibrido/local como produto final | A validacao com humano fora do Codex pode ser confundida com onboarding Wi-Fi completo, mesmo sem adapter seguro, falhas controladas, reboot, internet/backend ou contrato final de estados. | Registrar C4.2/C4.5 como validacao de processo de bancada, nao produto; exigir C4.6-C4.17 antes de campo conforme backlog. | C4 |
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
- Qualquer writer mock que escreva fora de `/tmp` ou toque em `/data`.
- Qualquer dado real de C6 que precise passar por chat, issue, PR, README,
  log, diff ou resumo.
- Qualquer config real, candidata real ou backup real versionado.
- Qualquer C6.2 sem C6.1-preflight revisado.
- Qualquer C6.3 sem `--real-dry-run` limpo, backup/rollback definido, servico
  controlado e evidencia sanitizada.
- Qualquer fluxo que inicie player com `api_key` externa ausente ou mal
  provisionada.
- Qualquer backup de config publicado ou com permissao ampla.
- Qualquer launcher iniciando player antes da validacao completa da config.
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
- C5: config writer mock em `/tmp`, placeholders, self-test, validacao de
  `environment_id`, evidencia sanitizada e nenhuma config real alterada.
- C5.1: contrato e validador dry-run com placeholders bloqueados em
  `--real-dry-run`, sem imprimir `api_key` e sem escrever em `/data`.
- C6.0: plano de escrita real com pre-condicoes, permissoes, backup, rollback,
  queda de energia, criterio de inicio do player e evidencia sanitizada.
- C6.1-preflight: checklist documental de decisoes humanas, politica de
  secrets, canal local de dados reais, pontos de abortar e evidencia esperada.
- C6.2: implementacao futura do writer real, preferencialmente testada em
  `/tmp`, sem escrita real e sem secrets em logs ou artefatos versionados.
- C6.3: execucao futura em placa de desenvolvimento, com `--real-dry-run`
  limpo, backup/rollback, servico controlado, config escrita somente se
  autorizado e evidencia sanitizada.
- C7: ativacao por codigo, login ou lista de ambientes com erros publicos e sem
  secrets na UI/logs.
- C8: rotacao, troca de ambiente, manutencao/reset com confirmacao forte e
  preservacao de evidencias quando definido.
