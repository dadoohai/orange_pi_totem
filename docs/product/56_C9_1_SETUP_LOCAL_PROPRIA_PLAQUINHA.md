# C9.1 - setup local na propria plaquinha

Status: implementado em desenvolvimento. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C9.1 cria um wizard local minimo para configurar o totem pela propria tela HDMI
com teclado USB.

O objetivo e provar o caminho obrigatorio de produto: o operador deve conseguir
executar o setup no proprio totem, sem depender de celular, notebook, QR code,
Chromium, desktop, compositor ou shell livre.

## 2. Correcao de premissa

C9.0 validou acesso temporario ao setup pela rede local existente. Esse caminho
continua util como apoio de bancada ou suporte, mas nao pode ser o fluxo unico.

A premissa corrigida e:

- setup local na propria tela do totem e obrigatorio;
- QR, celular, notebook e navegador externo sao caminhos auxiliares;
- o setup local deve ser controlado e nao abrir shell livre para operador.

## 3. Escopo implementado

Foi criado:

```text
scripts/board/totem_setup_local_wizard.py
```

O wizard:

- usa Python stdlib;
- usa entrada por teclado;
- roda como UI controlada em terminal local/HDMI;
- oferece selecao de ambiente mock/local;
- oferece escolha de orientacao;
- mostra revisao antes de gerar candidata;
- gera candidata apenas em `/tmp`;
- valida a candidata com C5.1 `allow-mock`;
- confirma falha esperada em C5.1 `real-dry-run` por placeholders;
- grava status/summary sanitizados;
- possui modo `--scripted` para smoke automatizado;
- possui `--self-test`.

## 4. Fluxo do operador

Fluxo minimo:

```text
Inicio do wizard local
-> Selecionar ambiente mock/local
-> Selecionar orientacao da tela
-> Revisar
-> Gerar candidata em /tmp
-> Ver resultado
```

Teclas:

- setas ou `j`/`k` movem a selecao;
- `Enter` confirma;
- `b` volta da revisao para orientacao;
- `q` ou `Esc` cancela.

Nao ha prompt de comando, campo para shell, menu de manutencao real ou acesso a
comandos operacionais.

## 5. Contrato de artefatos

Saida padrao:

```text
/tmp/dadooh-c9-1-local-wizard/
```

Arquivos:

```text
candidate-config.json
status.json
summary.txt
```

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

A candidata contem os campos necessarios para o contrato C5.1, incluindo
`rotation_deg`, mas ainda usa placeholders mock. Ela nao deve ser aplicada ao
writer.

## 6. Status e summary sanitizados

`status.json` e `summary.txt` registram somente categorias, booleans, decisoes
e contadores. Eles nao copiam:

- candidata completa;
- identificador bruto de ambiente;
- nome publico do ambiente escolhido;
- URL privada;
- credenciais;
- SSID;
- hostname;
- gateway;
- payload;
- logs brutos.

## 7. Relacao com C5.1

C9.1 reaproveita o contrato C5.1:

- `allow-mock` deve passar;
- `real-dry-run` deve falhar enquanto a candidata usa placeholders;
- a falha de `real-dry-run` e sucesso esperado nesta etapa.

Isso mantem a fronteira entre setup mock/local e config real.

## 8. Relacao com C8 e C9.0

C9.1 reaproveita a geracao de candidata do setup C8 e preserva os guardrails de
C8.1-C8.5:

- sem backend;
- sem Wi-Fi;
- sem writer;
- sem config real;
- sem servico/player;
- somente `/tmp`.

C9.0 permanece como acesso temporario auxiliar pela rede local. C9.1 passa a
ser o caminho obrigatorio de produto para setup local no proprio appliance.

## 9. Guardrails

C9.1 nao:

- escreve `/data/config/config.json`;
- toca backups;
- chama writer;
- usa `--enable-real-write`;
- le config real;
- escreve em `/data`;
- escreve em `/opt`;
- para ou inicia `kiosky-player.service`;
- inicia player;
- chama MPV;
- altera NetworkManager;
- executa `nmcli`;
- cria hotspot;
- chama backend;
- usa Chromium;
- usa desktop;
- usa compositor;
- abre shell livre.

## 10. Testes locais

Comandos locais obrigatorios:

```text
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_setup_local_wizard.py --self-test
python3 scripts/board/totem_setup_local_wizard.py --scripted --environment-key loja-a --rotation-key portrait_left --out-dir /tmp/dadooh-c9-1-local-wizard
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c9-1-local-wizard/candidate-config.json --allow-mock --out-dir /tmp/dadooh-c9-1-contract-allow-mock
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c9-1-local-wizard/candidate-config.json --real-dry-run --out-dir /tmp/dadooh-c9-1-contract-real-dry-run
bash -n scripts/remote/run_c9_1_local_wizard_tmp_on_dev_board.sh
git diff --check
```

O ultimo `real-dry-run` deve falhar com exit code `2`, porque a candidata ainda
usa placeholders.

## 11. Smoke remoto

Script remoto:

```text
scripts/remote/run_c9_1_local_wizard_tmp_on_dev_board.sh root@192.168.18.115
```

O smoke remoto:

- copia scripts para `/tmp`;
- roda self-tests;
- executa o wizard em modo `--scripted`;
- valida C5.1 `allow-mock`;
- confirma falha esperada em C5.1 `real-dry-run`;
- verifica permissoes `0700`/`0600`;
- verifica status/summary sanitizados;
- compara snapshot read-only de processos player/MPV antes/depois;
- nao altera servico, player, MPV, rede, `/data` ou `/opt`.

## 12. Criterios de aceite

Criterios:

- wizard local existe;
- operacao por teclado esta controlada;
- ambiente mock/local pode ser escolhido;
- orientacao pode ser escolhida;
- revisao existe antes de gerar candidata;
- candidata fica somente em `/tmp`;
- C5.1 `allow-mock` passa;
- C5.1 `real-dry-run` falha como esperado;
- status/summary nao vazam valores privados ou payload;
- nenhuma acao operacional e executada;
- testes locais passam;
- smoke remoto passa;
- producao continua bloqueada.

## 13. Proximos passos

Proximos passos recomendados:

- validar visualmente o wizard local na tela HDMI com teclado USB;
- definir como o setup local sera chamado em modo appliance sem expor shell
  livre;
- manter rede local/QR/navegador como caminhos auxiliares, nao substitutos;
- continuar sem escrita real ate uma etapa aprovada especifica.
