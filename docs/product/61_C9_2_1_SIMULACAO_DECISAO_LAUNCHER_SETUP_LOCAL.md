# C9.2.1 - simulacao source-only da decisao launcher/setup local

Status: implementado como simulacao source-only. Nao altera launcher
operacional. Nao e producao.

Data: 2026-05-04

## 1. Objetivo

C9.2.1 testa o contrato C9.2 em uma matriz de decisao puramente local/source,
sem executar o launcher real, renderer real, MPV, wizard HDMI, writer, servico
ou qualquer acao operacional.

O objetivo e validar a regra:

```text
renderer xor wizard xor player
```

para os estados principais da trilha `config_missing -> setup local ->
candidata em /tmp -> etapa futura`.

## 2. Por que C9.2.1 existe

C9.2 documentou como o launcher devera chamar futuramente o setup local quando
houver HDMI conectado e config ausente/invalida. Antes de mexer no launcher
operacional, C9.2.1 cria uma simulacao pequena e auditavel da decisao.

Essa simulacao reduz risco porque:

- transforma o contrato em fixtures verificaveis;
- deixa claro quem e dono da tela em cada estado;
- explicita que sucesso do wizard ainda nao aplica config real;
- mantem writer/config real para etapa futura;
- registra display/EDID como risco paralelo, nao bloqueio da trilha principal.

## 3. Escopo

Foi criado:

```text
scripts/board/totem_launcher_setup_decision_sim.py
```

O script:

- usa apenas Python stdlib;
- define fixtures em memoria;
- nao importa `kiosky_service_launcher.sh`;
- nao executa shell operacional;
- nao chama `systemctl`;
- nao chama MPV;
- nao chama renderer;
- nao chama wizard real;
- nao chama writer;
- nao le config real;
- nao escreve em `/data` ou `/opt`;
- imprime matriz em stdout;
- possui `--self-test`.

## 4. Fora de escopo

C9.2.1 nao:

- altera launcher operacional;
- cria segundo launcher paralelo;
- integra wizard automaticamente;
- para/inicia servico;
- chama MPV;
- chama renderer real;
- chama wizard real na HDMI;
- roda writer;
- altera config real;
- escreve em `/data`;
- escreve em `/opt`;
- altera NetworkManager;
- executa `nmcli`;
- mexe em display/EDID/resolucao;
- altera `kiosky-player`;
- libera producao.

## 5. Entradas simuladas

Cada fixture usa somente campos booleanos/normalizados:

```text
display_connected
config_valid
setup_requested
wizard_result
config_valid_after_future_write
```

`config_valid_after_future_write` existe apenas para representar uma etapa
futura em que writer/config real ja teriam sido aplicados fora de C9.2.1. A
simulacao nao executa writer.

## 6. Matriz de decisao

Matriz validada pelo `--self-test`:

```text
scenario | public_state | owner | renderer | wizard | player | next_step
display_disconnected | display_missing | none | ensure_stopped | not_allowed_without_display | not_started | wait_for_display
display_connected_config_valid | starting_player | player | stop_before_player | not_started | start_player_future_operation | player_running
config_missing_setup_not_requested | config_missing | renderer | show_config_missing_status | not_requested | not_started | wait_config_retry_or_setup_trigger
config_missing_setup_requested | setup_local_running | wizard | stop_before_wizard | run_on_reserved_tty_without_shell | not_started | wait_wizard_exit
wizard_cancelled | setup_local_cancelled | renderer | return_to_config_missing_status | ended_cancelled | not_started | config_missing
wizard_candidate_ready | setup_candidate_ready | renderer | return_to_config_missing_status | ended_candidate_ready | not_started | setup_handoff_pending
config_valid_after_future_write | starting_player | player | stop_before_player | not_started | start_player_future_operation | player_running
```

## 7. Interpretacao dos estados

`display_connected=false`:

- estado publico `display_missing`;
- renderer deve estar parado;
- wizard nao e permitido sem display;
- player nao inicia.

`display_connected=true + config_valid=true`:

- renderer deve parar antes do player;
- wizard nao entra;
- player passa a ser o unico dono da tela;
- estado seguinte esperado: `player_running`.

`display_connected=true + config_valid=false + setup_requested=false`:

- estado publico `config_missing`;
- renderer mostra status;
- wizard nao entra;
- player nao inicia.

`display_connected=true + config_valid=false + setup_requested=true`:

- renderer deve parar antes do wizard;
- wizard roda na TTY reservada, sem shell;
- player nao inicia;
- estado seguinte: aguardar saida do wizard.

`wizard_cancelled`:

- operador cancelou com `q`/`Esc`;
- wizard termina;
- renderer volta para status `config_missing`;
- player nao inicia;
- nenhuma config real e escrita.

`wizard_candidate_ready`:

- wizard terminou com candidata pronta;
- handoff fica em `/tmp`;
- renderer volta para status enquanto aguarda etapa futura;
- player nao inicia porque config real ainda nao mudou.

`config_valid_after_future_write`:

- representa apenas uma etapa futura, fora desta simulacao;
- se a config real ja estiver valida depois de writer futuro, renderer para e
  player pode iniciar;
- C9.2.1 nao executa writer nem altera config.

## 8. TTY reservada

A simulacao fixa a TTY futura esperada como:

```text
tty2
```

Isso valida a intencao de C9.2:

- TTY reservada;
- exec direto do wizard;
- sem shell livre;
- sem getty/login como caminho de operador;
- retorno controlado ao launcher.

## 9. Guardrails verificados

O `--self-test` verifica que todos os cenarios mantem como `false`:

- `operational_launcher_executed`;
- `service_started`;
- `service_stopped`;
- `mpv_called`;
- `renderer_called`;
- `wizard_called_on_hdmi`;
- `writer_called`;
- `real_config_read`;
- `real_config_written`;
- `data_written`;
- `opt_written`;
- `network_changed`;
- `nmcli_called`;
- `display_changed`;
- `kiosky_player_changed`;
- `production_released`.

Tambem verifica:

- existem exatamente sete fixtures;
- cada fixture retorna o estado esperado;
- cada fixture tem no maximo um dono de tela;
- candidata pronta permanece como handoff em `/tmp`;
- config valida apos writer e representada apenas como futuro.

## 10. Comandos de validacao

Comando obrigatorio:

```text
python3 scripts/board/totem_launcher_setup_decision_sim.py --self-test
```

Para imprimir a matriz:

```text
python3 scripts/board/totem_launcher_setup_decision_sim.py
```

Para imprimir JSON:

```text
python3 scripts/board/totem_launcher_setup_decision_sim.py --json
```

## 11. Resultado

Resultado esperado de C9.2.1:

- matriz documentada;
- simulacao passa;
- nenhuma acao operacional executada;
- nenhum segundo launcher paralelo criado;
- producao continua bloqueada.

## 12. Proximos passos

Proximos passos recomendados:

- transformar esta matriz em teste source-only mais proximo do launcher, ainda
  sem executar o launcher operacional;
- definir gatilho local real de entrada no setup;
- definir politica da TTY reservada e getty;
- melhorar UX do wizard antes de operador final;
- manter writer/config real em etapa futura separada;
- manter display/EDID/resolucao em frente paralela.
