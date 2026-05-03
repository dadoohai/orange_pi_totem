# C8.8 - primeira escrita real integrada setup -> writer/config

Status: executado em desenvolvimento. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.8 executou a primeira escrita real integrada entre o fluxo C8 de setup e o
writer C6, usando candidata privada temporaria em `/tmp`, servico parado,
backup/rollback preservados e evidencia sanitizada.

A rodada nao iniciou o player, nao reiniciou o servico e nao liberou producao.

## 2. Condicoes antes da escrita

Pre-condicoes confirmadas:

- branch `foundation-v0.1` limpa;
- self-tests relevantes passaram localmente e na placa;
- C8.7 read-only preliminar retornou `go_for_next_real_write_round`;
- arquivo privado aprovado existia em `/tmp`;
- arquivo privado tinha permissao `0600`;
- diretorio privado tinha permissao `0700`;
- candidata C8 foi gerada em `/tmp`;
- orientacao selecionada: `portrait_left`, preservada como `rotation_deg: 270`;
- candidata privada passou C5.1 `real-dry-run`;
- valores privados nao apareceram nos status/summaries sanitizados;
- autorizacao humana explicita foi recebida antes de parar servico e escrever
  em `/data/config/config.json`.

## 3. Execucao real

Sequencia executada na placa:

1. Confirmar metadados de `/tmp` e paths reais.
2. Rodar self-test do writer C6.
3. Validar C5.1 `real-dry-run` na candidata privada.
4. Observar `kiosky-player.service` como `active`.
5. Parar `kiosky-player.service`.
6. Confirmar `kiosky-player.service` como `inactive`.
7. Executar `totem_config_writer_real.py` com:
   - `--dest /data/config/config.json`;
   - `--backup-dir /data/config/backups`;
   - `--enable-real-write`;
   - `--confirm-service-stopped`;
   - `--confirm-human-approved-real-write`.
8. Confirmar writer `passed`.
9. Confirmar backup criado.
10. Confirmar config ativa escrita com permissao esperada.
11. Limpar `candidate-private.json` e `private-values.json`.
12. Rodar gate read-only final.
13. Confirmar servico ainda `inactive`.

## 4. Resultado

Resultado sanitizado:

- escrita real: concluida;
- writer C6: `passed`;
- C5.1 pre/post write: validado pelo writer;
- backup: criado;
- rollback: nao acionado, pois a escrita passou;
- `/data/config/config.json`: existe como arquivo;
- permissao da config ativa: `0640`;
- servico ao final: `inactive`;
- `candidate-private.json`: removido;
- `private-values.json`: removido;
- gate final: `passed`;
- producao: continua bloqueada.

## 5. Evidencia sanitizada

Artefatos de desenvolvimento na placa:

```text
/tmp/dadooh-c8-8-real-write/writer-status.json
/tmp/dadooh-c8-8-real-write/summary.txt
/tmp/dadooh-c8-6-handoff-preflight/handoff-preflight-status.json
/tmp/dadooh-c8-6-handoff-preflight/summary.txt
/tmp/dadooh-c8-8-gate-after-real/operational-gate-status.json
/tmp/dadooh-c8-8-gate-after-real/summary.txt
```

Todos os artefatos de evidencia ficam sob `/tmp`, com diretorios `0700` e
arquivos `0600`.

Nao foram publicados:

- `api_url`;
- `api_key`;
- `environment_id` real;
- payload;
- conteudo de `/data/config/config.json`;
- conteudo de backup;
- `candidate-private.json`;
- `private-values.json`.

## 6. Guardrails preservados

C8.8 nao:

- iniciou o player;
- iniciou `kiosky-player.service` depois da escrita;
- chamou MPV;
- alterou NetworkManager;
- executou `nmcli`;
- implementou Wi-Fi;
- chamou backend manualmente;
- leu config real via `cat`;
- copiou backup;
- publicou valores privados;
- liberou producao.

## 7. Estado operacional ao final

Estado intencional ao final da rodada:

- config real foi escrita;
- backup foi criado;
- temporarios privados foram removidos;
- evidencia sanitizada foi preservada em `/tmp`;
- `kiosky-player.service` permaneceu parado;
- player nao foi iniciado.

Esse estado prepara uma etapa seguinte de start controlado, separada da escrita
real.

## 8. Riscos remanescentes

- O player ainda nao foi iniciado com a nova config nesta rodada.
- A validacao de playback real e status `player_running` fica fora de C8.8.
- A producao continua bloqueada ate haver start controlado, smoke curto e
  criterios de rollback operacional.

## 9. Proximo passo

Proximo passo recomendado:

- C8.9 - start controlado pos-escrita real, sem mudar config, com observacao de
  servico/player, smoke curto, evidencia sanitizada e criterio explicito de
  rollback se o player nao subir corretamente.
