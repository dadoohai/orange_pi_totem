# C8.6-preflight - handoff real controlado sem escrita real

Status: preflight local/controlado. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.6-preflight define e exercita o rito minimo para transformar uma candidata
C8 mock/local em uma candidata privada temporaria, validada por C5.1
`real-dry-run`, sem executar escrita real.

Esta etapa:

- usa valores privados apenas a partir de arquivo restrito sob `/tmp`;
- gera candidata privada temporaria em `/tmp`;
- valida C5.1 `real-dry-run`;
- observa pre-condicoes de servico/player sem alterar estado;
- registra autorizacao humana de preflight, nao de escrita real;
- mantem writer real bloqueado.

## 2. Por que C8.6 existe

C8.5.0 mostrou que a candidata mock deve falhar em `real-dry-run`. C8.5.1
provou com valores sinteticos que o shape pode passar. C8.5.2 corrigiu o
contrato para deixar `station_id` fora do caminho critico.

C8.6 prepara o proximo gate: como usar valores privados reais sem publica-los
e sem acionar C6 em modo real. O objetivo ainda e abortar antes de qualquer
escrita operacional.

## 3. Rito de valores privados

Valores privados reais nunca devem entrar em Git, docs, chat, comando,
evidencia publica ou status/summary.

Origem permitida para este preflight:

```text
/tmp/dadooh-c8-6-private/private-values.json
```

O arquivo deve ter permissao `0600`, estar fora do repositorio e conter apenas
os valores aprovados localmente:

- endpoint privado;
- credencial de runtime;
- identificador de ambiente aprovado;
- `station_id` opcional, apenas se for necessario para inventario/telemetria.

O script exige confirmacao explicita de que a origem privada foi aprovada para
preflight. Essa confirmacao nao autoriza escrita real.

## 4. Script

Script:

```text
scripts/board/totem_setup_private_handoff_preflight.py
```

Entrada padrao:

```text
/tmp/dadooh-c8-1-setup-minimo/candidate-config.json
/tmp/dadooh-c8-6-private/private-values.json
```

Saida padrao:

```text
/tmp/dadooh-c8-6-handoff-preflight/
```

Artefatos:

- `candidate-private.json`;
- `handoff-preflight-status.json`;
- `summary.txt`.

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

## 5. Candidata privada temporaria

`candidate-private.json` contem valores privados e por isso deve ficar apenas
em `/tmp`, fora de evidencia e fora do repo.

A candidata privada:

- preserva os campos C8, incluindo `rotation_deg`;
- substitui endpoint, credencial e ambiente pelos valores privados aprovados;
- preserva `station_id` opcional quando ele nao for fornecido;
- passa C5.1 `real-dry-run`;
- nao e entregue ao writer nesta etapa.

## 6. Status e summary sanitizados

`handoff-preflight-status.json` e `summary.txt` nao copiam:

- candidata fonte;
- arquivo de valores privados;
- candidata privada;
- endpoint;
- credencial;
- identificador de ambiente;
- `station_id`;
- paths da candidata;
- output bruto de servico;
- output bruto de processos.

Eles publicam apenas contadores, categorias, booleans e decisoes de handoff.

## 7. Pre-condicoes de servico/player

C8.6 observa pre-condicoes sem mudar estado:

- chama somente comandos `systemctl` read-only allowlisted:
  - `systemctl is-active kiosky-player.service`;
  - `systemctl is-enabled kiosky-player.service`;
- nao chama `start`, `stop`, `restart`, `enable` ou `disable`;
- observa processos relevantes via `/proc` sem publicar linha de comando;
- registra apenas categorias e contadores.

Se servico/player nao estiverem bloqueados, o preflight ainda pode ser
concluido, mas o status marca ponto de aborto antes de escrita real.

## 8. Writer continua bloqueado

C8.6 nao chama `totem_config_writer_real.py`.

Tambem nao usa:

- `--enable-real-write`;
- `--confirm-service-stopped`;
- `--confirm-human-approved-real-write`.

O handoff fica em estado `preflight_only_abort_before_writer`. Um writer futuro
deve revalidar C5.1, preservar backup/rollback e exigir aprovacao humana
separada.

## 9. Pontos de aborto

Abortar antes de qualquer escrita real se:

- valores privados precisarem aparecer em chat, docs, comandos ou evidencia;
- arquivo privado nao estiver sob `/tmp`;
- arquivo privado estiver dentro do repo;
- candidata privada falhar C5.1 `real-dry-run`;
- servico/player nao estiverem bloqueados para escrita real;
- humano nao aprovar a etapa real futura;
- backup/rollback C6 nao estiverem confirmados;
- evidencia futura exigir config, backup, payload ou valores privados.

## 10. Guardrails

C8.6:

- escreve somente em `/tmp`;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao le `/data/config/config.json`;
- nao chama writer real;
- nao usa `--enable-real-write`;
- nao para/inicia/reinicia servico;
- nao inicia player;
- nao chama MPV;
- nao altera NetworkManager;
- nao chama backend;
- nao usa Wi-Fi;
- nao publica valores privados.

## 11. Testes locais

Self-tests:

```bash
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_setup_minimal_server.py --self-test
python3 scripts/board/totem_setup_writer_preflight.py --self-test
python3 scripts/board/totem_setup_real_synthetic_candidate.py --self-test
python3 scripts/board/totem_setup_private_handoff_preflight.py --self-test
```

Smoke local:

- gerar candidata C8 em `/tmp`;
- criar arquivo privado sintetico em `/tmp`;
- rodar C8.6 com confirmacao de preflight;
- validar C5.1 `real-dry-run` na candidata privada;
- confirmar permissoes `0700`/`0600`;
- confirmar sanitizacao de status/summary;
- confirmar writer real bloqueado.

## 12. Teste remoto

Smoke seguro:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O teste remoto deve provar:

- self-tests passam na placa;
- setup C8 gera candidata;
- C8.5.0 continua bloqueando candidata mock;
- C8.5.1 continua passando com candidata real-sintetica;
- C8.6 gera candidata privada temporaria em `/tmp`;
- C8.6 valida C5.1 `real-dry-run`;
- status/summary nao vazam valores;
- nenhum servico, player, MPV, rede, `/data` ou `/opt` e alterado;
- servidor e encerrado ao final.

## 13. Proximos passos

- C8.6.1, se necessario: revisar linguagem operacional e limpeza segura da
  candidata privada temporaria.
- C8.7/C6 gate futuro: somente depois de aprovacao humana para escrita real,
  servico/player bloqueado, writer C6 revalidando, backup e rollback
  confirmados.
