# C8.1.1 - handoff setup -> contrato de config

Status: consolidacao de handoff. Funcional/mock local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.1.1 consolida a fronteira entre o setup minimo C8.1 e o contrato de config
existente de C5.1.

Objetivos:

- alinhar a candidata gerada pelo setup minimo ao contrato minimo ja validado;
- reaproveitar a validacao C5.1 sem criar uma estrategia paralela;
- representar rotacao no campo esperado pelo player/appliance futuro;
- provar que a candidata C8.1 passa em `--allow-mock`;
- provar que a candidata C8.1 ainda falha em `--real-dry-run` enquanto usa
  placeholders;
- manter escrita somente em `/tmp`.

## 2. Por que C8.1.1 existe

C8.1 provou a fatia vertical de UX: operador informa `environment_id`, escolhe
rotacao, revisa e gera uma candidata local.

A revisao seguinte mostrou dois pontos de handoff que precisavam ser
consolidados antes de C8.2/C8.3 avancarem:

- a validacao de `environment_id` estava duplicada entre C8.1 e C5.1;
- a rotacao estava em `display_rotation_degrees`, enquanto a configuracao do
  appliance/player usa `rotation_deg`.

C8.1.1 corrige esses pontos sem transformar o setup em writer real e sem tocar
rede, servico, player ou config ativa.

## 3. Relacao com C8.1

C8.1 continua sendo o fluxo funcional minimo:

```text
Configuracao pendente
-> Iniciar configuracao
-> Informar environment_id
-> Escolher rotacao
-> Revisar
-> Salvar simulado
-> Configuracao candidata pronta
```

C8.1.1 nao muda a jornada do operador. Ela endurece a candidata gerada no fim
do fluxo e registra validacao de contrato no status sanitizado.

## 4. Relacao com C5.1

C5.1 e o contrato minimo de config candidata. Ele define campos obrigatorios,
regras de paths, regra de `environment_id`, regra opcional de `station_id` e
comportamento de placeholders.

C8.1.1 passa a usar o validador C5.1 como fonte de verdade para:

- validacao de `environment_id`;
- validacao da candidata em modo `allow-mock`;
- prova de bloqueio em modo `real-dry-run`.

O setup nao copia a saida bruta do validador para `status.json` ou
`summary.txt`. Ele publica apenas resultado agregado e sanitizado.

## 5. Relacao com C6 writer real

C6 writer real continua sendo a camada que pode validar, escrever, fazer
backup e rollback de config ativa. C8.1.1 nao chama
`totem_config_writer_real.py`.

O handoff correto para C6 futuro e:

1. setup gera candidata em `/tmp`;
2. candidata passa no contrato em `allow-mock`;
3. enquanto houver placeholders, `real-dry-run` falha;
4. fase futura substitui placeholders por valores privados fora do Git/chat;
5. writer real roda em fase propria, com servico parado ou bloqueio
   equivalente e guardrails C6.

## 6. Decisoes tomadas

- Nao criar helper novo: o servidor C8.1 importa
  `totem_config_contract_validate.py` diretamente.
- Usar os placeholders oficiais de C5.1:
  - `https://api.example.invalid/search`;
  - `API_KEY_MOCK_NOT_FOR_PRODUCTION`;
  - `STATION_ID_MOCK`.
- A partir de C8.5.2, `STATION_ID_MOCK` permanece permitido como valor
  opcional/futuro e nao bloqueia `real-dry-run`; a falha esperada vem de
  `api_url`, `api_key` e ambiente mock quando aplicavel.
- Validar `environment_id` com `validate_environment_like_id()` do C5.1,
  mantendo a recusa de espaco no inicio/fim no setup.
- Trocar o campo de rotacao para `rotation_deg`.
- Manter a candidata em `/tmp/dadooh-c8-1-setup-minimo/candidate-config.json`.
- Manter `status.json` e `summary.txt` sem `environment_id` bruto, sem segredo
  e sem URL privada.
- Atualizar o script remoto para copiar tambem o validador C5.1 para `/tmp`.

## 7. Campos da candidata C8.1

A candidata C8.1.1 contem o shape minimo aceito pelo contrato C5.1:

- `api_url`;
- `api_key`;
- `environment_id`;
- `cache_dir`;
- `state_dir`;
- `status_file`;
- `ipc_path`;
- `runtime_dir`;
- `strict_paths_enabled`;
- `mpv_query_uses_fresh_ipc`;
- `mpv_vo`;
- `mpv_gpu_context`;
- `mpv_ao`;
- `low_resource_mode`.

O setup ainda pode carregar `station_id` como campo opcional/futuro para
compatibilidade e telemetria/inventario futuro, mas ele nao e requisito
bloqueante para a config minima.

Tambem contem campos de handoff do setup:

- `rotation_deg`;
- `setup_source`.

O validador C5.1 ignora campos extras que nao fazem parte do contrato minimo,
entao `rotation_deg` fica disponivel para o player futuro sem quebrar a
validacao atual.

## 8. Tratamento de rotacao

A rotacao aceita continua restrita a:

- `0`;
- `90`;
- `180`;
- `270`.

C8.1.1 grava a escolha em `rotation_deg`, que e o campo documentado para a
config appliance/player. A fase ainda nao aplica rotacao no display, renderer,
MPV ou sistema.

## 9. Validacao mock/allow-mock

A candidata C8.1.1 deve passar em C5.1 `allow-mock` porque:

- todos os campos obrigatorios existem;
- os paths de appliance sao strings sob raizes permitidas;
- `environment_id` segue a allowlist;
- `station_id`, quando presente, segue a allowlist opcional;
- placeholders sao permitidos nesse modo.

O servidor executa essa validacao em memoria antes de escrever os artefatos do
setup. O smoke remoto tambem executa o validador em `/tmp`.

## 10. Por que real-dry-run ainda deve falhar

`real-dry-run` deve falhar enquanto C8.1.1 usar placeholders. Essa falha e
esperada e desejada porque impede que uma candidata mock seja confundida com
config real.

Hoje a falha vem de:

- `api_url` com dominio `.invalid`;
- `api_key` placeholder;
- ambiente mock/local, quando a fase de produto ainda nao trouxe origem
  aprovada.

Uma fase futura so deve esperar `real-dry-run` passando depois de receber dados
privados por canal local aprovado, fora do Git, docs, chat e evidencias
publicas.

## 11. O que continua fora

C8.1.1 nao:

- implementa Wi-Fi real;
- altera NetworkManager;
- executa `nmcli`;
- cria hotspot ou portal real;
- cria QR funcional;
- integra backend;
- implementa login ou codigo de ativacao;
- escreve em `/data`;
- escreve em `/opt`;
- le `/data/config/config.json`;
- inicia ou para `systemd`;
- inicia ou para `kiosky-player.service`;
- inicia MPV;
- altera `kiosky-player`;
- altera homologacao `v0.1-rc1`;
- libera producao.

## 12. Criterios de aceite

C8.1.1 e aceito quando:

- C8.1 continua funcionando;
- self-test local passa;
- smoke HTTP local passa;
- smoke remoto em `/tmp` passa;
- candidata passa em C5.1 `allow-mock`;
- candidata falha em C5.1 `real-dry-run`;
- rotacao usa `rotation_deg`;
- `status.json` e `summary.txt` continuam sanitizados;
- nenhum artefato e escrito em `/data` ou `/opt`;
- nenhum processo fica rodando depois do smoke;
- nenhum servico e alterado;
- `git diff --check` passa.

## 13. Proximos passos

- C8.2 ainda faz sentido como selecao de ambiente mock/local, mas agora deve
  preservar o handoff C5.1.
- C8.3 ainda faz sentido como refinamento de UX de rotacao, mas o campo tecnico
  base passa a ser `rotation_deg`.
- C8.5 deve integrar setup e writer/config em tarefa propria, mantendo
  `real-dry-run`, placeholders bloqueados, dados privados fora do Git/chat e
  servico/player protegidos.
