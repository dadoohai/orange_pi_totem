# C8.4.0 - manutencao minima mock/local

Status: funcional/mock local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.4.0 inicia a area de manutencao minima do fluxo de setup, ainda sem
executar nenhuma acao real.

A entrega permite que uma pessoa nao tecnica veja a entrada secundaria
"Suporte / manutencao", entenda as acoes disponiveis e registre uma acao de
teste local em `/tmp`, sem terminal, shell, reset real, player real, MPV, rede
ou escrita de config real.

## 2. Por que C8.4.0 existe

C8.1 criou o setup minimo mock/local. C8.2 removeu o `environment_id` tecnico do
caminho principal. C8.3 tornou a rotacao compreensivel para operador.

C8.4.0 abre a frente de manutencao minima sem pular para operacao real. O
objetivo e validar linguagem, fluxo, confirmacao e contrato de artefatos antes
de qualquer integracao com `systemd`, player, writer real ou reset real.

## 3. Relacao com a matriz de reset

A matriz `docs/product/40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md` separa:

- reiniciar exibicao/player como acao de operador;
- reset de configuracao operacional como acao protegida por confirmacao forte;
- resets de rede, cache, factory reset e recovery como fases posteriores.

C8.4.0 representa apenas o contrato mock/local de duas acoes da matriz:

- `restart_player_mock`;
- `reset_config_mock`.

Nenhuma delas implementa a acao operacional da matriz. O status publico e o
resumo registram `real_effect: none` e guardrails indicando que nada real foi
alterado.

## 4. Acoes mock disponiveis

| Acao na UI | Action id | Confirmacao | O que simula |
| --- | --- | --- | --- |
| Reiniciar exibicao | `restart_player_mock` | Nao | Um pedido futuro de reinicio da exibicao. |
| Limpar configuracao de teste | `reset_config_mock` | Sim | Uma volta futura para configuracao pendente. |
| Voltar | UI local | Nao | Navegacao para a tela anterior. |

## 5. O que cada acao simula

`restart_player_mock` representa uma acao futura de suporte. Nesta etapa,
nenhum player e reiniciado; o resultado e apenas um registro local de sucesso
mock.

`reset_config_mock` simula que o suporte pediu a limpeza da configuracao de
teste e a volta para configuracao pendente. Nesta etapa, o resultado e apenas
um registro local de sucesso mock.

## 6. O que cada acao NAO faz

C8.4.0 nao:

- executa `systemctl`;
- inicia, para ou reinicia `kiosky-player.service`;
- mata processos;
- chama MPV;
- le `/data/config/config.json`;
- escreve em `/data`;
- escreve em `/opt`;
- apaga config real;
- apaga cache real;
- altera NetworkManager;
- executa `nmcli`;
- chama backend;
- implementa writer real;
- implementa reset real;
- libera producao.

## 7. Confirmacao forte para reset

`reset_config_mock` exige confirmacao explicita. A UI mostra:

```text
Entendo que esta é uma simulação e não apaga dados reais.
```

A API `/api/maintenance-action` tambem exige essa frase no campo
`confirmation`. Sem a confirmacao, a requisicao falha com HTTP 400 e nenhum
artefato de sucesso e gerado.

A frase de confirmacao nao e copiada para `maintenance-action-status.json` nem
para `maintenance-summary.txt`.

## 8. Contrato de status/summary

C8.4.0 reutiliza o mesmo diretorio de saida do setup C8:

```text
/tmp/dadooh-c8-1-setup-minimo
```

Escolha: manter um unico diretorio mock/local para a experiencia C8, mas com
arquivos separados para setup e manutencao.

Artefatos de setup preservados:

- `candidate-config.json`;
- `status.json`;
- `summary.txt`.

Artefatos novos de manutencao:

- `maintenance-action-status.json`;
- `maintenance-summary.txt`.

`maintenance-action-status.json` registra somente:

- schema da manutencao;
- timestamp UTC;
- action id allowlisted;
- resultado `mock_success`;
- `real_effect: none`;
- flags de guardrail;
- flags de privacidade.

`maintenance-summary.txt` e um resumo humano sanitizado. Ele nao copia payload
bruto, frase de confirmacao, token, URL privada, `environment_id`, SSID, senha,
IP, hostname, gateway, DNS, config ou backup.

## 9. Guardrails

Guardrails implementados no servidor:

- `--out-dir` precisa estar abaixo de `/tmp`;
- diretorio de saida com permissao `0700`;
- arquivos com permissao `0600`;
- escrita atomica dos artefatos;
- endpoint `/api/maintenance-action` aceita somente acoes allowlisted;
- acao desconhecida falha;
- reset sem confirmacao falha;
- nenhum comando externo e chamado;
- nenhum caminho real de config e lido;
- nenhum artefato e escrito fora de `/tmp`;
- status/summary passam por varredura simples contra vazamento de dados
  sensiveis conhecidos.

## 10. Criterios de aceite

C8.4.0 e aceito quando:

- C8.1/C8.2/C8.3 nao regridem;
- Manutencao aparece como area secundaria;
- textos deixam claro que sao acoes de teste;
- `restart_player_mock` funciona como simulacao;
- `reset_config_mock` funciona somente com confirmacao;
- reset sem confirmacao falha;
- acao desconhecida falha;
- nada executa acao real;
- nada escreve em `/data` ou `/opt`;
- nada altera servico, player, MPV ou rede;
- status/summary continuam sanitizados;
- self-test local passa;
- smoke HTTP local passa;
- validacao humana aprova a UI;
- smoke remoto seguro em `/tmp` passa;
- `git diff --check` passa;
- producao continua bloqueada.

## 11. Testes locais

Self-test:

```bash
python3 scripts/board/totem_setup_minimal_server.py --self-test
```

Servidor local:

```bash
python3 scripts/board/totem_setup_minimal_server.py \
  --bind 127.0.0.1 \
  --port 8766 \
  --out-dir /tmp/dadooh-c8-1-setup-minimo
```

Smoke HTTP esperado:

- `GET /`;
- `POST /api/candidate` com ambiente mock e `rotation_key`;
- `POST /api/maintenance-action` com `restart_player_mock`;
- `POST /api/maintenance-action` com `reset_config_mock` e confirmacao;
- `POST /api/maintenance-action` com `reset_config_mock` sem confirmacao deve
  falhar;
- `POST /api/maintenance-action` com acao desconhecida deve falhar;
- validar diretorio `0700`;
- validar arquivos `0600`;
- validar que artefatos resolvem abaixo de `/tmp`;
- validar que status/summary nao vazam dados sensiveis.

## 12. Teste remoto

O smoke remoto continua copiando somente servidor e validador para `/tmp` na
placa, sobe o servidor em `127.0.0.1`, executa self-tests e valida as acoes
mock:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O teste remoto deve provar por contrato e artefatos que:

- self-test passa na placa;
- servidor sobe em `127.0.0.1`;
- setup C8.1/C8.2/C8.3 continua funcionando;
- acoes mock funcionam;
- reset sem confirmacao falha;
- acao invalida falha;
- permissoes sao restritas;
- nenhum artefato escapa de `/tmp`;
- nenhum guardrail indica servico, player, MPV, rede, `/data` ou `/opt`
  alterados;
- snapshot de processos de player/MPV nao muda durante as acoes mock;
- servidor e encerrado ao final.

## 13. Proximos passos

- C8.4.1: refinar contrato de autorizacao/confirmacao se a linguagem de campo
  pedir ajuste.
- C8.5: integrar manutencao com writer/config somente quando a politica de
  reset real for aprovada.
- C9: retomar rede/Wi-Fi/portal apenas com adapter seguro e rollback.
- C10: factory reset, hard reset local, rollback de app e recovery avancado.
