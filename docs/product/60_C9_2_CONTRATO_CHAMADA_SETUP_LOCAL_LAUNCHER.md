# C9.2 - contrato de chamada do setup local pelo launcher

Status: contrato documentado. Nao implementa integracao operacional. Nao e
producao.

Data: 2026-05-04

## 1. Objetivo

C9.2 define como o launcher devera chamar futuramente o setup local em
`config_missing`, sem alterar ainda o launcher operacional.

O objetivo e transformar o resultado de C9.1 em um contrato de produto e
processo:

- setup local pela propria tela HDMI continua obrigatorio;
- teclado USB e o caminho principal local nesta fase;
- QR, rede local e navegador externo continuam caminhos auxiliares;
- nenhum shell livre deve ser exposto ao operador;
- renderer, wizard e player nao podem disputar a tela/DRM;
- candidata de setup deve ficar somente em `/tmp` ate uma etapa futura de
  writer/aplicacao real.

## 2. Por que C9.2 existe

C9.1 criou o wizard local controlado por teclado USB. C9.1.1 provou que ele
aparece na HDMI, aceita teclado, gera candidata em `/tmp` e retorna controle
ao final, mas tambem mostrou que a UX ainda parece terminal Linux/Python e nao
esta pronta para operador final.

C9.1.2 e C9.1.3 separaram o warning de imagem esticada do wizard: a distorcao
visual ja existia antes do stop/start e o padrao de contrato visual confirmou
problema de proporcao/display. Isso deve virar risco e frente futura de
display/tipo de tela, nao um bloqueador para definir como o setup sera chamado.

C9.2 existe para fechar a pergunta de arquitetura: quando o launcher estiver
em `config_missing`, qual e o contrato seguro para entregar a tela ao setup
local e depois retornar para status ou player?

## 3. Relacao com C9.1, C9.1.1 e C9.1.3

C9.1 entrega:

- `scripts/board/totem_setup_local_wizard.py`;
- UI curses controlada por teclado;
- selecao de ambiente mock/local;
- escolha de orientacao;
- revisao antes de gerar candidata;
- artefatos apenas em `/tmp`;
- `--self-test` e `--scripted`;
- sem writer, sem `/data`, sem `/opt`, sem rede e sem MPV.

C9.1.1 entrega:

- validacao humana na HDMI com teclado USB;
- uso pratico de TTY local via `openvt`;
- confirmacao de que renderer/player devem ser tratados como donos exclusivos
  da tela;
- restauracao final do player quando ele foi parado para a validacao;
- ressalva: UX ainda parece terminal.

C9.1.3 entrega:

- evidencia de distorcao de proporcao e desalinhamento da area exibida;
- indicacao de que EDID/framebuffer/MPV/escala da tela precisam de frente
  futura;
- confirmacao de que esse tema nao deve ser misturado com a decisao de chamada
  do setup pelo launcher.

## 4. Decisao de produto

Decisao C9.2:

- setup local no proprio totem e obrigatorio;
- QR, celular, notebook e navegador externo sao auxiliares;
- `config_missing` deve oferecer caminho local controlado para setup;
- a primeira tela de `config_missing` continua podendo ser uma tela Dadooh de
  status/renderizacao;
- o setup local deve ser chamado por um gatilho controlado, sem abrir shell;
- C9.2 nao implementa esse gatilho ainda.

## 5. Analise do launcher atual

O launcher operacional atual esta em:

```text
scripts/board/kiosky_service_launcher.sh
```

Fluxo atual:

```text
main
-> display_connected?
   -> nao:
      stop_status_renderer
      write_status display_missing false
      sleep DISPLAY_RETRY_SEC
   -> sim:
      handle_connected_display
        -> config_valid?
           -> sim:
              run_app_once
                stop_status_renderer
                write_status starting true
                inicia kiosk.py
                write_status running true
                refresh de status enquanto app vive
           -> nao:
              write_status config_missing true
              start_status_renderer
              sleep CONFIG_RETRY_SEC
```

Hoje o launcher decide assim:

- `display_missing`: nenhum display DRM conectado; renderer e app nao devem
  ficar ativos;
- `config_missing`: display conectado, mas config minima ausente/invalida;
  app/player nao sao iniciados e o renderer pode ocupar a HDMI;
- `player_running`: estado publico agregado quando a config e valida e o app
  esta rodando; no launcher bruto o estado correspondente e `running`.

O `config_valid` atual valida apenas existencia/leitura de config JSON e campos
minimos nao vazios. Ele nao deve ser mudado em C9.2.

## 6. Onde o wizard local entra

O ponto de entrada futuro e somente dentro do ramo:

```text
display_connected=true
config_valid=false
```

Ou seja:

- nao entra em `display_missing`;
- nao entra quando config real ja e valida;
- nao entra enquanto `kiosk.py`/MPV do player esta rodando;
- nao entra enquanto o renderer nao puder ser parado com seguranca.

O comportamento padrao em `config_missing` continua sendo mostrar status. O
wizard entra apenas quando houver um gatilho local controlado, por exemplo uma
tecla/botao/atalho futuro reconhecido pelo proprio appliance. C9.2 nao escolhe
nem implementa esse mecanismo de input; define apenas que ele deve chamar uma
rotina controlada do launcher, nao shell.

## 7. Estados propostos

Estados publicos/sanitizados propostos para uma integracao futura:

```text
display_missing
config_missing
setup_local_available
setup_local_requested
setup_local_starting
setup_local_running
setup_local_cancelled
setup_local_failed
setup_candidate_ready
setup_handoff_pending
starting_player
player_running
```

Significado:

- `setup_local_available`: display conectado, config ausente/invalida e setup
  local permitido como acao do operador;
- `setup_local_requested`: gatilho local recebido, antes de tomar a tela;
- `setup_local_starting`: renderer sendo parado e TTY sendo preparada;
- `setup_local_running`: wizard esta em controle da TTY/tela;
- `setup_local_cancelled`: operador saiu com `q`/`Esc`;
- `setup_local_failed`: erro tecnico, timeout, TTY indisponivel, renderer nao
  parou ou candidata invalida;
- `setup_candidate_ready`: candidata completa foi gerada em `/tmp`;
- `setup_handoff_pending`: candidata pronta aguarda etapa futura de writer ou
  aplicacao real.

Esses estados devem ser publicos e sanitizados. Eles nao podem incluir
identificador real de ambiente, URL, token, path de midia, IP, SSID, hostname,
payload ou cmdline bruta.

## 8. Fluxo proposto

Fluxo futuro em `config_missing`:

```text
display conectado
-> config invalida/ausente
-> write_status config_missing
-> start_status_renderer
-> aguardar retry ou gatilho local controlado

gatilho local recebido
-> write_status setup_local_requested
-> stop_status_renderer
   -> se falhar: write_status setup_local_failed e voltar config_missing
-> confirmar que player/MPV principal nao esta rodando
   -> se houver disputa: write_status setup_local_failed e voltar config_missing
-> abrir TTY reservada com wizard, sem shell
-> aguardar wizard terminar
   -> exit 0 + candidata pronta: write_status setup_candidate_ready
   -> exit 130/cancelamento: write_status setup_local_cancelled
   -> outro exit: write_status setup_local_failed
-> revalidar config real
   -> se config passou a valida por etapa futura: iniciar player
   -> se ainda falta config real: start_status_renderer e voltar config_missing
```

C9.2 nao chama writer. Mesmo quando `setup_candidate_ready` existir, o contrato
atual termina em `/tmp` e volta para status. A aplicacao real da candidata fica
para etapa futura.

## 9. Processo, TTY e tela

Contrato de TTY futuro:

- usar TTY reservada e configuravel, preferencialmente `tty2`;
- expor variavel futura como `TOTEM_SETUP_TTY=2`;
- chamar o wizard por exec direto, por exemplo via `openvt -c "$TTY" -s -f -w`
  ou unidade systemd equivalente vinculada a TTY;
- executar `env TERM=linux python3 .../totem_setup_local_wizard.py --out-dir ...`;
- nao chamar `/bin/sh`, login shell, getty interativo ou prompt de comando;
- registrar `active_tty` apenas como metadado tecnico sanitizado quando
  necessario;
- ao final, devolver controle ao loop do launcher.

O wizard deve ocupar a tela sozinho. Antes dele:

- renderer deve estar parado;
- player deve estar ausente;
- MPV principal deve estar ausente;
- nenhum outro processo temporario de tela deve estar ativo.

## 10. Como evitar shell livre

O operador nao deve receber shell em nenhum caminho de setup.

Regras:

- a TTY reservada executa apenas o comando do wizard;
- argumentos do wizard sao fixos e controlados pelo launcher;
- nao ha campo de texto para comando;
- nao ha menu de manutencao real;
- `q`/`Esc` cancelam o wizard e retornam ao launcher;
- falhas retornam para status, nao para shell;
- getty/login na TTY reservada deve estar ausente, mascarado ou nao usado pela
  integracao futura.

## 11. Como evitar disputa com renderer/player

Regra de exclusao:

```text
renderer xor wizard xor player
```

Antes de iniciar wizard:

1. chamar `stop_status_renderer`;
2. confirmar que renderer parou;
3. confirmar que `CHILD_PID` do app nao esta vivo;
4. confirmar que nao ha MPV principal esperado pelo player;
5. se qualquer confirmacao falhar, abortar para `setup_local_failed`.

Antes de iniciar player:

1. garantir que wizard terminou;
2. garantir que renderer parou;
3. revalidar config real;
4. so entao chamar `run_app_once`.

Se a config ainda estiver invalida, o launcher volta para `config_missing` e
reinicia o renderer.

## 12. Como sair ou cancelar

Saidas esperadas do wizard:

- `0`: fluxo concluido, artefatos gerados;
- `130`: operador cancelou com `q`/`Esc`;
- `1` ou `2`: erro tecnico ou validacao local falhou;
- timeout futuro: tratar como erro tecnico.

Contrato de retorno:

- cancelamento nao deixa shell aberto;
- cancelamento nao escreve config real;
- cancelamento nao apaga config real;
- cancelamento volta para tela/status `config_missing`;
- sucesso gera candidata em `/tmp` e volta para status de handoff pendente;
- falha registra motivo publico sanitizado e volta para `config_missing`.

## 13. Como impedir config parcial

C9.2 mantem a fronteira atual:

- wizard gera candidata apenas em `/tmp`;
- writer real nao e chamado;
- `/data/config/config.json` nao e lido nem escrito;
- nenhum backup e criado;
- nenhum valor privado e usado;
- candidata mock/local nao deve ser aplicada automaticamente.

Contrato futuro de handoff:

- cada execucao do setup deve usar um diretorio dedicado sob `/tmp`;
- permissoes: diretorio `0700`, arquivos `0600`;
- arquivos esperados:
  - `candidate-config.json`;
  - `status.json`;
  - `summary.txt`;
- o launcher so considera handoff valido quando `status.json` indica
  `candidate_ready` e a validacao C5.1 `allow-mock` passou;
- etapa futura de writer deve rodar nova validacao antes de qualquer escrita
  real;
- escrita real futura deve ser atomica, com backup restrito, e continuar
  exigindo autorizacao/guardrail proprio.

Nada em C9.2 promove candidata para config real.

## 14. Como registrar falha

Falhas devem virar status publico sanitizado, nao log bruto.

Motivos publicos permitidos:

- `setup_trigger_unavailable`;
- `setup_tty_unavailable`;
- `setup_renderer_stop_failed`;
- `setup_player_conflict`;
- `setup_wizard_missing`;
- `setup_wizard_cancelled`;
- `setup_wizard_failed`;
- `setup_candidate_missing`;
- `setup_candidate_invalid`;
- `setup_timeout`;
- `setup_display_lost`.

Nao registrar:

- conteudo de config;
- candidata completa;
- valores privados;
- `api_url`;
- `api_key`;
- `environment_id` real;
- cmdline bruta;
- logs brutos;
- IP, SSID, gateway ou hostname.

## 15. Display/EDID nao entra em C9.2

C9.1.3 confirmou risco de display/proporcao. C9.2 nao corrige esse problema.

Guardrail:

- nao forcar resolucao;
- nao alterar flags MPV;
- nao alterar `--geometry`;
- nao alterar `--video-unscaled`;
- nao alterar framebuffer;
- nao alterar EDID;
- nao bloquear o contrato de chamada do setup por esse tema.

O problema de tela deve virar frente futura de seletor/resolucao/tipo de tela
ou preflight visual de display. A chamada do setup pelo launcher deve apenas
preservar os metadados e nao piorar a disputa por tela.

## 16. O que nao sera implementado em C9.2

C9.2 nao:

- altera `scripts/board/kiosky_service_launcher.sh`;
- integra wizard automaticamente;
- cria gatilho real de teclado/botao;
- para/inicia servico;
- chama MPV;
- altera config real;
- roda writer;
- escreve em `/data`;
- escreve em `/opt`;
- altera NetworkManager;
- executa `nmcli`;
- tenta corrigir resolucao/EDID;
- altera flags MPV;
- altera `kiosky-player`;
- libera producao.

## 17. Criterios para futura integracao

Antes de implementar a integracao real, exigir:

- contrato C9.2 aceito;
- UX do wizard melhorada o suficiente para operador nao tecnico ou mantida
  explicitamente como fluxo de bancada;
- TTY reservada definida e testada;
- renderer para de forma confiavel antes do wizard;
- wizard sai sem deixar shell;
- cancelamento volta para `config_missing`;
- falha volta para `config_missing` com status publico;
- sucesso gera candidata apenas em `/tmp`;
- writer real continua separado em etapa propria;
- testes de `display_missing`, `config_missing`, cancelamento, erro e sucesso;
- smoke remoto com autorizacao humana explicita;
- evidencia sanitizada;
- nenhuma alteracao de config real sem etapa aprovada.

## 18. Riscos

Riscos principais:

- disputa DRM/KMS entre renderer, wizard e player;
- TTY reservada indisponivel ou com getty/login ativo;
- UX do wizard ainda parecer terminal;
- operador cancelar e nao entender o retorno ao status;
- candidata pronta ser confundida com config aplicada;
- falha de renderer impedir setup;
- setup ficar preso sem timeout futuro;
- distorcao visual de display prejudicar leitura e escolha;
- status publico vazar dados se o contrato for descumprido;
- integracao futura chamar writer cedo demais.

## 19. Proximos passos

Proximos passos recomendados:

- C9.2.1 ou C9.3: prototipo read-only/source-only da decisao do launcher, sem
  alterar o launcher operacional;
- melhorar UX visual do wizard para parecer produto, nao terminal;
- definir gatilho local de entrada no setup sem shell livre;
- definir TTY reservada e politica para getty;
- criar teste de cancelamento e retorno para `config_missing`;
- manter frente de display/resolucao separada;
- manter producao bloqueada.
