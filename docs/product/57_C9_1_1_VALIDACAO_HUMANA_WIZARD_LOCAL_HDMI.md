# C9.1.1 - validacao humana do wizard local HDMI

Status: passou tecnicamente com ressalvas de UX e warning visual
pos-restauracao. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C9.1.1 valida o wizard C9.1 na propria placa, com tela HDMI e teclado USB,
para observar a experiencia real de operador.

Esta etapa nao integra o wizard ao launcher, nao chama automaticamente em
`config_missing` e nao transforma o setup local em servico permanente.

## 2. Por que existe

C9.1 provou o caminho tecnico do wizard local. C9.1.1 existe para testar o
mesmo fluxo fora do SSH e fora do modo scripted, usando o hardware real que o
operador tera em campo:

- tela HDMI;
- teclado USB;
- navegacao por teclas;
- leitura das mensagens na distancia real;
- cancelamento/saida;
- geracao de candidata apenas em `/tmp`.

## 3. Escopo

Foi criado:

```text
scripts/remote/run_c9_1_1_hdmi_wizard_validation.sh
```

O script:

- copia o wizard e dependencias para `/tmp`;
- roda self-tests;
- verifica disponibilidade de `openvt`;
- observa estado do servico de forma read-only;
- observa processos por categoria, sem PID/cmdline em evidencia;
- pode preparar a validacao sem iniciar o wizard;
- pode abrir o wizard em uma TTY local da HDMI;
- valida artefatos gerados em `/tmp`;
- valida C5.1 `allow-mock`;
- confirma falha esperada de C5.1 `real-dry-run`;
- gera evidencia sanitizada em `/tmp`.

## 4. Modos de execucao

Preparacao segura, sem abrir wizard e sem parar player:

```text
scripts/remote/run_c9_1_1_hdmi_wizard_validation.sh root@192.168.18.115 --prepare-only
```

Execucao HDMI sem autorizacao de parada:

```text
scripts/remote/run_c9_1_1_hdmi_wizard_validation.sh root@192.168.18.115
```

Se o player/MPV estiver ativo, esse modo bloqueia antes de parar qualquer
servico e registra que e necessaria autorizacao humana explicita.

Execucao HDMI com parada temporaria autorizada:

```text
scripts/remote/run_c9_1_1_hdmi_wizard_validation.sh root@192.168.18.115 --allow-temporary-player-stop
```

Esse modo so deve ser usado depois de autorizacao humana explicita. Se o
servico estava ativo, o script para `kiosky-player.service`, roda o wizard na
TTY local e tenta restaurar o estado ativo ao final.

## 5. Artefatos

Wizard:

```text
/tmp/dadooh-c9-1-1-local-wizard-hdmi/
candidate-config.json
status.json
summary.txt
```

Evidencia sanitizada:

```text
/tmp/dadooh-c9-1-1-hdmi-validation/
status.json
summary.txt
```

Validacoes C5.1:

```text
/tmp/dadooh-c9-1-1-contract-allow-mock/
/tmp/dadooh-c9-1-1-contract-real-dry-run/
```

Permissoes esperadas:

- diretorios `0700`;
- arquivos `0600`.

## 6. Checklist humano

Durante a validacao, o humano deve responder:

- a tela ficou legivel?
- parece produto ou terminal?
- navegacao por teclado funciona?
- operador entende ambiente, orientacao e revisao?
- ha linguagem tecnica demais?
- consegue cancelar/sair?
- candidata foi gerada em `/tmp`?

As respostas humanas nao sao inferidas pelo script. O status registra esses
itens como pendentes ate o humano reportar.

## 7. Guardrails

C9.1.1 nao:

- integra com launcher;
- chama automaticamente em `config_missing`;
- altera config real;
- roda writer;
- le `/data/config/config.json`;
- escreve `/data/config/config.json`;
- toca backups;
- escreve em `/data`;
- escreve em `/opt`;
- altera rede/Wi-Fi;
- cria hotspot;
- executa `nmcli`;
- chama backend;
- chama MPV diretamente;
- usa Chromium, desktop ou compositor;
- abre shell livre para operador.

Parada temporaria do player so e permitida com autorizacao humana explicita e
deve ser restaurada ao estado combinado ao final.

## 8. Privacidade

Status e summary nao copiam:

- candidata completa;
- valores privados;
- `api_url`;
- `api_key`;
- identificador bruto de ambiente;
- payload;
- IP;
- SSID;
- hostname;
- gateway;
- logs brutos;
- PID/cmdline de processos.

## 9. Criterios de aceite

Criterios:

- preparacao remota passa;
- wizard aparece na HDMI quando executado;
- teclado USB navega pelo fluxo;
- operador consegue revisar e gerar candidata;
- operador consegue cancelar/sair;
- candidata fica apenas em `/tmp`;
- C5.1 `allow-mock` passa;
- C5.1 `real-dry-run` falha como esperado;
- estado do player e restaurado se parada temporaria foi autorizada;
- evidencia sanitizada e gerada;
- nenhuma config real e alterada;
- producao continua bloqueada.

## 10. Resultado observado

Validacao humana:

- a tela do wizard apareceu na HDMI e ficou legivel;
- a navegacao por teclado USB funcionou;
- a linguagem esta aceitavel para esta fase;
- tecnicamente, o fluxo pareceu rodar;
- visualmente, ainda parece um terminal Linux/Python interativo;
- um operador nao tecnico provavelmente nao entenderia bem o que esta
  acontecendo;
- portanto, C9.1.1 nao aprova UX final nem pronto para operador.

Resultado tecnico sanitizado:

- runner C9.1.1 retornou `passed`;
- candidata foi gerada em `/tmp`;
- C5.1 `allow-mock` passou;
- C5.1 `real-dry-run` falhou como esperado por placeholders;
- servico foi restaurado para `active`;
- servico permaneceu `enabled`;
- `NRestarts=0`;
- player observado: `1`;
- MPV observado: `1`;
- renderer observado: `0`;
- artefatos e evidencias ficaram em `/tmp`;
- arquivos de candidata/status/summary com permissao `0600`;
- diretorios de evidencia com permissao `0700`;
- config real nao foi lida ou alterada.

Diagnostico read-only pos-restauracao:

- active TTY observado: `tty1`;
- framebuffer observado: `1360,768`, `32` bpp, rotate `0`;
- HDMI observado como `connected` e `enabled`;
- MPV observado com `--vo=gpu`, `--gpu-context=drm`, `--ao=null` e fullscreen;
- `--geometry` e `--video-unscaled` nao foram observados;
- o diagnostico nao encontrou servico quebrado, restart loop, player ausente,
  MPV ausente ou renderer concorrendo com player;
- o diagnostico nao explica sozinho a percepcao de midia esticada.

Evidencia sanitizada:

```text
/tmp/dadooh-c9-1-1-hdmi-validation/status.json
/tmp/dadooh-c9-1-1-hdmi-validation/summary.txt
/tmp/dadooh-c9-1-1-post-restore-diagnostic/status.json
/tmp/dadooh-c9-1-1-post-restore-diagnostic/summary.txt
```

Warning importante:

- apos restaurar o player, a midia pareceu visualmente com proporcao diferente
  ou mais esticada;
- ainda nao esta claro se o efeito veio do wizard, troca de TTY, stop/start do
  servico, modo de video ou outro efeito colateral;
- isso deve ser tratado como possivel regressao visual a investigar antes de
  considerar o setup local pronto para operador final.

## 11. Proximos passos

Depois da validacao humana:

- investigar o warning visual de proporcao pos-restauracao com diagnostico
  controlado e sem alterar config real;
- ajustar visual/copy para reduzir aparencia de terminal antes de UX final;
- definir o rito futuro para chamar o setup local sem expor shell livre;
- ainda nao integrar automaticamente ao launcher ou `config_missing` sem nova
  etapa aprovada.
