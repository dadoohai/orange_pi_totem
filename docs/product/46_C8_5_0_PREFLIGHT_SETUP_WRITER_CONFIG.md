# C8.5.0 - preflight setup -> writer/config

Status: funcional/preflight local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.5.0 prepara a ponte entre o setup C8 e o writer/config C6 sem escrever
config real.

O fluxo validado nesta etapa e:

```text
setup C8
-> candidate-config.json em /tmp
-> validacao C5.1 allow-mock
-> C5.1 real-dry-run falhando por placeholders
-> relatorio sanitizado de lacunas
-> contrato de handoff para writer C6 futuro
```

Tudo continua local/offline e restrito a `/tmp`.

## 2. Por que C8.5.0 existe

C8.1-C8.4 provaram a experiencia mock/local de configuracao e manutencao, mas
ainda nao existe uma fronteira operacional segura entre "candidata gerada pelo
setup" e "config real ativa".

C8.5.0 existe para impedir um salto perigoso: pegar uma candidata mock e
entregar diretamente ao writer real. Antes de qualquer escrita, o sistema
precisa mostrar claramente o que falta, quais valores precisam vir por canal
privado e quais precondicoes operacionais ainda estao bloqueadas.

## 3. Relacao com C8.1-C8.4

- C8.1 criou o servidor local de setup e a candidata em `/tmp`.
- C8.1.1 alinhou a candidata ao contrato C5.1 e preservou `rotation_deg`.
- C8.2 trocou `environment_id` tecnico por lista mock/local.
- C8.3 refinou a escolha de orientacao sem aplicar rotacao real.
- C8.4.0 criou manutencao minima mock/local sem acao real.

C8.5.0 nao muda a UI principal. Ele adiciona um preflight de bastidor para
avaliar a candidata gerada pelo setup antes de qualquer integracao com writer.

## 4. Relacao com C5.1

C5.1 continua sendo a fonte de verdade do contrato minimo de config.

O preflight executa as duas leituras logicas do contrato:

- `allow-mock`: deve passar para confirmar que a candidata tem shape valido.
- `real-dry-run`: deve falhar nesta fase, porque a candidata ainda contem
  placeholders e valores mock.

A falha de `real-dry-run` e sucesso esperado em C8.5.0. Se uma candidata C8
mock passasse em `real-dry-run`, o preflight falharia por indicar mistura de
fase ou dados reais fora do canal aprovado.

## 5. Relacao com C6 writer real

O writer C6.2/C6.2.2 ja define o formato operacional futuro:

- validar `real-dry-run` antes de escrever;
- abortar antes de escrita se a validacao falhar;
- escrever atomicamente;
- criar backup;
- preservar rollback;
- em modo real, exigir flags explicitas, destino exato e aprovacao humana.

C8.5.0 nao chama o writer em modo real e nao usa `--enable-real-write`.

Nesta etapa, o preflight apenas registra:

- writer real bloqueado;
- writer simulado nao chamado;
- candidata ainda nao pronta para writer real;
- writer futuro deve revalidar antes de escrever;
- writer futuro deve preservar escrita atomica, backup e rollback.

## 6. Contrato de handoff

Entrada padrao:

```text
/tmp/dadooh-c8-1-setup-minimo/candidate-config.json
```

Saida padrao:

```text
/tmp/dadooh-c8-5-preflight/
```

Artefatos:

- `preflight-status.json`;
- `summary.txt`.

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

O status e o summary nao copiam a candidata completa, nao copiam valores dos
campos privados e nao copiam paths da candidata.

## 7. Campos da candidata C8

A candidata C8 preserva o contrato minimo C5.1:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`;
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

Campos extras de handoff do setup:

- `rotation_deg`;
- `setup_source`;
- `setup_environment_source`.

O preflight publica apenas contadores: quantidade de campos obrigatorios,
quantidade presente, quantidade de campos de handoff e quantidade de campos
extras. Ele nao publica nomes ou valores no status/summary.

## 8. Campos mock/placeholders

Em C8.5.0, as lacunas sao publicadas por categoria, nao por valor bruto:

- credencial de runtime privada;
- endpoint/backend privado;
- identidade local da estacao;
- ambiente ainda vindo de catalogo mock/local, quando aplicavel.

Os valores reais correspondentes devem entrar futuramente por canal seguro,
fora de Git, docs, chat e evidencia publica.

## 9. Por que real-dry-run ainda falha

A candidata C8 usa placeholders seguros para desenvolvimento:

- endpoint mock;
- credencial mock;
- identificador de estacao mock;
- ambiente escolhido de lista mock/local.

O validador C5.1 bloqueia pelo menos endpoint/credencial/estacao em
`real-dry-run`. O preflight tambem marca o ambiente mock/local como lacuna de
produto, mesmo que o contrato C5.1 atual valide apenas formato.

Essa falha impede que uma candidata de UI/prototipo vire config real por engano.

## 10. O que precisa mudar para real-dry-run passar no futuro

Antes de uma etapa real, sera necessario:

- receber endpoint real por canal privado aprovado;
- receber credencial de runtime por canal privado aprovado;
- receber ou derivar `station_id` real;
- trocar a selecao mock/local de ambiente por origem aprovada;
- preservar `rotation_deg`;
- validar a candidata completa com C5.1 `real-dry-run`;
- garantir que setup/render esteja parado ou bloqueado antes do player;
- garantir que o player nao inicia com config parcial;
- executar writer C6 com escrita atomica, backup e rollback.

## 11. Riscos antes de escrita real

- Copiar candidata mock para config ativa por engano.
- Vazar credencial, endpoint, ambiente real, paths privados ou payload em
  status/evidencia.
- Iniciar player com config parcial.
- Sobrescrever config real sem backup valido.
- Misturar setup, renderer e player competindo pelo mesmo estado operacional.
- Usar `--enable-real-write` sem aprovacao humana e sem servico bloqueado.
- Perder rollback se o writer for chamado fora do contrato C6.

## 12. Script

Script novo:

```text
scripts/board/totem_setup_writer_preflight.py
```

Uso padrao:

```bash
python3 scripts/board/totem_setup_writer_preflight.py
```

Uso explicito:

```bash
python3 scripts/board/totem_setup_writer_preflight.py \
  --candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --out-dir /tmp/dadooh-c8-5-preflight
```

Self-test:

```bash
python3 scripts/board/totem_setup_writer_preflight.py --self-test
```

## 13. Guardrails

O preflight:

- exige candidata sob `/tmp`;
- exige out-dir sob `/tmp`;
- rejeita candidata ausente;
- rejeita candidata invalida;
- rejeita candidata que nao passa `allow-mock`;
- rejeita candidata mock que passe em `real-dry-run`;
- nao chama comandos externos;
- nao chama writer real;
- nao usa `--enable-real-write`;
- nao le `/data/config/config.json`;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao chama `systemctl`;
- nao inicia ou para player;
- nao chama MPV;
- nao altera rede, NetworkManager ou backend.

## 14. Criterios de aceite

C8.5.0 e aceito quando:

- C8.1-C8.4 nao regridem;
- candidata C8 tem handoff documentado;
- `allow-mock` passa;
- `real-dry-run` falha como esperado;
- lacunas para config real ficam claras por categoria;
- nenhum secret e usado;
- nenhuma config real e lida ou escrita;
- nenhuma acao operacional e executada;
- tudo roda local e remoto em `/tmp`;
- status/summary continuam sanitizados;
- smoke remoto em `/tmp` passa;
- `git diff --check` passa;
- producao continua bloqueada.

## 15. Testes locais

Self-tests:

```bash
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_writer_preflight.py --self-test
```

Smoke local:

```bash
python3 scripts/board/totem_setup_minimal_server.py \
  --bind 127.0.0.1 \
  --port 8766 \
  --out-dir /tmp/dadooh-c8-1-setup-minimo
```

Depois gerar candidata via `POST /api/candidate` e rodar:

```bash
python3 scripts/board/totem_setup_writer_preflight.py \
  --candidate /tmp/dadooh-c8-1-setup-minimo/candidate-config.json \
  --out-dir /tmp/dadooh-c8-5-preflight
```

Validar:

- `preflight-status.json`;
- `summary.txt`;
- diretorio `0700`;
- arquivos `0600`;
- nenhuma copia de valores privados;
- nenhum artefato fora de `/tmp`.

## 16. Teste remoto

O smoke remoto copia apenas servidor, validador e preflight para `/tmp`, gera
candidata C8 e roda C8.5.0 na placa:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O teste remoto prova:

- self-tests passam na placa;
- setup C8 ainda gera candidata;
- preflight roda sobre a candidata;
- `allow-mock` passa;
- `real-dry-run` falha como esperado;
- `preflight-status.json` e `summary.txt` sao gerados;
- permissoes sao restritas;
- nada e escrito em `/data` ou `/opt`;
- nenhum servico, player, MPV, rede ou backend e alterado;
- servidor e encerrado ao final.

## 17. Proximos passos

- C8.5.1, se necessario: detalhar origem aprovada de valores privados e
  autorizacao operacional.
- C8.6 ou fase propria: testar handoff com candidata sintetica privada ainda em
  `/tmp`, sem `--enable-real-write`.
- Fase real futura: somente depois de preflight humano, canal privado aprovado,
  servico/player bloqueado, backup/rollback confirmado e evidencia sanitizada.
