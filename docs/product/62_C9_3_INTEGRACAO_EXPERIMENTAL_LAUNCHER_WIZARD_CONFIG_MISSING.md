# C9.3 - integracao experimental launcher/wizard em config_missing

Status: implementado como integracao experimental atras de flag. Nao e
producao.

Data: 2026-05-04

## 1. Objetivo

C9.3 prova o caminho minimo em que o launcher, ao estar em `config_missing`,
consegue chamar o wizard local obrigatorio na propria tela do totem, sem shell
livre, sem iniciar player e sem disputar tela com renderer.

Esta etapa nao tenta resolver display/EDID/proporcao, nao refina a estetica do
wizard, nao chama writer e nao aplica config real.

## 2. Decisao de produto

Decisoes preservadas:

- setup local na propria plaquinha e obrigatorio;
- QR/navegador sao auxiliares;
- operador nao deve ver shell livre;
- renderer, wizard e player nao podem disputar a tela;
- problema de proporcao/display e frente paralela;
- display nao deve travar a trilha principal do setup local.

## 3. Escopo implementado

Arquivo alterado:

```text
scripts/board/kiosky_service_launcher.sh
scripts/board/totem_status_aggregate.py
```

Arquivo de teste remoto criado:

```text
scripts/remote/run_c9_3_launcher_setup_local_experiment.sh
```

A integracao no launcher fica desligada por padrao. Ela so entra quando:

```text
TOTEM_SETUP_LOCAL_ENABLED=1
```

e houver pedido explicito por:

```text
TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING=1
```

ou por arquivo de gatilho sob `/tmp`:

```text
TOTEM_SETUP_LOCAL_TRIGGER_FILE=/tmp/dadooh-setup-local.request
```

Sem essas flags, o launcher segue o comportamento anterior.

O agregador de status tambem foi ajustado para tratar estados experimentais
`setup_local_*` e `setup_candidate_ready` como estado publico seguro
`config_missing`. Isso evita que um status antigo do player seja interpretado
como `player_running` enquanto o setup experimental esta em andamento.

## 4. Variaveis experimentais

Variaveis adicionadas:

```text
TOTEM_SETUP_LOCAL_ENABLED=0
TOTEM_SETUP_LOCAL_AUTORUN_CONFIG_MISSING=0
TOTEM_SETUP_LOCAL_TRIGGER_FILE=/tmp/dadooh-setup-local.request
TOTEM_SETUP_LOCAL_WIZARD=/opt/totem/bin/totem_setup_local_wizard.py
TOTEM_SETUP_LOCAL_OUT_DIR=/tmp/dadooh-c9-3-local-wizard
TOTEM_SETUP_LOCAL_TTY=2
TOTEM_SETUP_LOCAL_MAX_RUNS=1
```

As variaveis mantem rollback simples:

```text
TOTEM_SETUP_LOCAL_ENABLED=0
```

ou ausencia da variavel retorna ao launcher anterior.

## 5. Fluxo experimental

Fluxo novo, somente atras de flag:

```text
display conectado
-> config invalida/ausente
-> write_status config_missing
-> setup_local_requested?
   -> nao:
      start_status_renderer
      sleep CONFIG_RETRY_SEC
   -> sim:
      write_status setup_local_requested
      stop_status_renderer
      confirmar CHILD_PID ausente
      validar wizard disponivel
      validar openvt disponivel
      write_status setup_local_starting
      write_status setup_local_running
      openvt -c TOTEM_SETUP_LOCAL_TTY -s -f -w -- env TERM=linux python3 wizard --out-dir /tmp/...
      exit 0 + candidate-config.json:
        write_status setup_candidate_ready
      exit 130:
        write_status setup_local_cancelled
      outro exit:
        write_status setup_local_failed
      se config real ainda invalida:
        start_status_renderer
        sleep CONFIG_RETRY_SEC
```

O player so inicia se `config_valid` passar. Como C9.3 usa config ausente ou
invalida temporaria, o player nao deve iniciar durante a etapa experimental.

## 6. Tela, TTY e shell livre

Contrato da chamada:

- TTY reservada configuravel, padrao `tty2`;
- exec direto via `openvt`;
- comando fixo do wizard;
- `TERM=linux`;
- sem `/bin/sh` para operador;
- sem getty/login como caminho de setup;
- `q`/`Esc` cancelam e retornam ao launcher;
- sucesso/cancelamento/falha retornam ao loop do launcher.

## 7. Exclusao renderer/wizard/player

Regra:

```text
renderer xor wizard xor player
```

Antes do wizard:

- `stop_status_renderer`;
- se renderer nao parar, `setup_local_failed`;
- `CHILD_PID` do app precisa estar ausente;
- wizard so roda depois desses checks.

Depois do wizard:

- se config continua invalida, renderer volta para status;
- se uma etapa futura tornar config valida, player pode iniciar;
- C9.3 nao executa essa etapa futura.

## 8. Handoff de candidata

Em sucesso:

```text
/tmp/dadooh-c9-3-local-wizard/candidate-config.json
/tmp/dadooh-c9-3-local-wizard/status.json
/tmp/dadooh-c9-3-local-wizard/summary.txt
```

Guardrails:

- candidata permanece em `/tmp`;
- writer nao e chamado;
- `/data/config/config.json` nao e lido nem escrito;
- valores privados nao sao usados;
- config real nao muda;
- candidata pronta nao significa player pronto.

## 9. Runner remoto controlado

Runner:

```text
scripts/remote/run_c9_3_launcher_setup_local_experiment.sh
```

Modo seguro:

```text
scripts/remote/run_c9_3_launcher_setup_local_experiment.sh root@192.168.18.115 --prepare-only
```

Esse modo:

- copia launcher/wizard/dependencias para `/tmp`;
- roda `bash -n` no launcher copiado;
- roda self-tests do wizard e contrato;
- nao para servico;
- nao executa launcher;
- nao ocupa HDMI.

Modo experimental:

```text
scripts/remote/run_c9_3_launcher_setup_local_experiment.sh root@192.168.18.115 --run
```

Esse modo exige a frase:

```text
Autorizo C9.3: parar temporariamente o serviço, executar launcher experimental em /tmp com config inválida e wizard local na HDMI, sem writer, com restauração do player ao final.
```

O runner `--run`:

- para temporariamente `kiosky-player.service`;
- nao altera a config real;
- executa copia do launcher em `/tmp`;
- aponta `KIOSKY_CONFIG_PATH` para arquivo inexistente em `/tmp`;
- usa renderer fake em `/tmp` para validar parada/retorno sem chamar MPV;
- cria gatilho de setup em `/tmp`;
- abre o wizard real na HDMI por TTY reservada;
- espera o operador cancelar ou gerar candidata;
- encerra a copia experimental do launcher;
- restaura `kiosky-player.service`;
- gera evidencia sanitizada em `/tmp`.

## 10. Evidencia

Diretorio remoto:

```text
/tmp/dadooh-c9-3-launcher-setup-experiment/
```

Arquivos principais:

```text
status.json
summary.txt
launcher-status.json
```

Status/summary nao copiam:

- conteudo de config;
- candidata completa;
- valores privados;
- paths de midia;
- logs brutos;
- cmdlines brutas;
- IP/SSID/gateway/hostname.

## 11. Resultado executado

Execucao `--prepare-only`:

- copiou launcher/wizard/dependencias para `/tmp`;
- `bash -n` do launcher copiado passou;
- self-tests do contrato, servidor minimo e wizard passaram;
- nao parou servico;
- nao abriu wizard;
- nao ocupou HDMI.

Execucao `--run` autorizada:

- autorizacao humana textual recebida nas execucoes;
- `kiosky-player.service` estava ativo antes;
- servico foi parado temporariamente;
- copia experimental do launcher rodou em `/tmp`;
- config foi forçada para caminho ausente em `/tmp`;
- renderer fake iniciou em `config_missing`;
- gatilho de setup em `/tmp` foi criado;
- launcher parou renderer fake antes do wizard;
- wizard abriu na HDMI/TTY2;
- primeiro teste: operador cancelou o wizard;
- segundo teste: operador concluiu o wizard e gerou candidata;
- launcher registrou cancelamento no primeiro teste e `candidate_ready` no
  segundo;
- copia experimental do launcher foi encerrada;
- servico real foi restaurado;
- estado final `active/enabled`;
- `NRestarts=0`;
- player final=1;
- MPV final=1;
- renderer real final=0.

Resultado da etapa:

- caminho `config_missing -> wizard local -> cancelamento -> status -> player`
  foi provado;
- caminho `config_missing -> wizard local -> candidate_ready em /tmp -> status
  -> player` foi provado;
- candidata foi gerada em `/tmp/dadooh-c9-3-local-wizard/`;
- writer nao foi chamado;
- config real nao foi lida nem escrita;
- `/data/config` nao foi tocado;
- renderer fake nao chamou MPV;
- status publico final voltou a `player_running`;
- playback final voltou a `playing`;
- MPV final voltou ativo;
- evidencia sanitizada ficou em `/tmp/dadooh-c9-3-launcher-setup-experiment/`.

## 12. Fora de escopo

C9.3 nao:

- aplica config real;
- roda writer;
- escreve em `/data/config`;
- usa valores privados;
- mexe em Wi-Fi/rede;
- altera NetworkManager;
- executa `nmcli`;
- altera `kiosky-player`;
- resolve display/EDID;
- refina estetica do wizard;
- libera producao.

## 13. Criterios de sucesso

Criterios:

- `config_missing` chama wizard local quando flag/gatilho estao ativos;
- wizard aparece na tela;
- operador nao recebe shell livre;
- player nao roda junto;
- renderer nao roda junto;
- candidata fica em `/tmp`;
- cancelamento volta para `config_missing/status`;
- sucesso registra `setup_candidate_ready`;
- writer nao e chamado;
- restauracao para `player_running` funciona apos retornar ao servico real;
- rollback simples: desabilitar `TOTEM_SETUP_LOCAL_ENABLED`.

## 14. Riscos

Riscos:

- fluxo ainda depende de TTY/openvt;
- wizard ainda parece terminal;
- renderer fake do runner valida contrato de parada/retorno, nao aparencia real
  do status renderer;
- display/proporcao continua risco paralelo;
- integracao real em `/opt` ainda precisa etapa propria;
- writer/config real continuam bloqueados.

## 15. Proximos passos

Proximos passos recomendados:

- repetir `--run` concluindo o wizard para validar `setup_candidate_ready` e
  candidata em `/tmp`;
- se aprovado, criar etapa futura para instalar a flag experimental de forma
  controlada ou melhorar UX antes de apresentacao;
- manter writer real, Wi-Fi, QR e display fora desta rodada.
