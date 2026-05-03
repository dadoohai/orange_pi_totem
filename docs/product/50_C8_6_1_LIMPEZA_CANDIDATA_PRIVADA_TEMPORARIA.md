# C8.6.1 - limpeza segura da candidata privada temporaria

Status: funcional/local. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.6.1 fecha o ciclo de vida dos arquivos privados temporarios criados no
preflight C8.6.

O objetivo e remover explicitamente:

- `candidate-private.json`;
- `private-values.json`.

Depois da limpeza, devem permanecer apenas status e summary sanitizados.

## 2. Por que C8.6.1 existe

C8.6 acertou o gate de entrada privada: valores aprovados entram por arquivo
restrito em `/tmp`, a candidata privada passa C5.1 `real-dry-run` e writer real
continua bloqueado.

Mesmo com permissao `0600`, `candidate-private.json` e `private-values.json`
contem valores privados. Antes de qualquer escrita real futura, o produto
precisa provar que esses arquivos tem um ciclo de vida explicito e removivel.

## 3. Modo de limpeza

O mesmo script de C8.6 ganhou um modo explicito:

```bash
python3 scripts/board/totem_setup_private_handoff_preflight.py \
  --private-values /tmp/dadooh-c8-6-private/private-values.json \
  --out-dir /tmp/dadooh-c8-6-handoff-preflight \
  --cleanup-private-artifacts \
  --confirm-cleanup-private-artifacts
```

Sem `--confirm-cleanup-private-artifacts`, a limpeza falha.

## 4. O que e removido

O cleanup remove:

- a candidata privada temporaria no out-dir;
- o arquivo de entrada privada informado por `--private-values`.

O cleanup nao le o conteudo desses arquivos. Ele valida que os alvos estao sob
`/tmp`, rejeita alvo sob `/data`, `/opt`, `/home` ou dentro do repo quando
aplicavel, e executa apenas `unlink`.

## 5. O que permanece

No out-dir C8.6 permanecem apenas:

- `handoff-preflight-status.json`;
- `summary.txt`.

Esses arquivos sao reescritos com o status de cleanup:

- cleanup executado;
- confirmacao explicita recebida;
- candidata privada removida;
- arquivo de valores privados removido;
- contagem de arquivos privados restantes;
- writer real bloqueado;
- guardrails preservados.

Status e summary nao publicam valores, paths privados, config, payload ou logs
brutos.

## 6. Guardrails

C8.6.1:

- escreve somente em `/tmp`;
- nao escreve em `/data`;
- nao escreve em `/opt`;
- nao le `/data/config/config.json`;
- nao chama writer real;
- nao usa `--enable-real-write`;
- nao chama `systemctl`;
- nao para/inicia/reinicia servico;
- nao inicia player;
- nao chama MPV;
- nao altera NetworkManager;
- nao chama backend;
- nao usa Wi-Fi;
- nao publica valores privados.

## 7. Criterios de aceite

- Cleanup exige confirmacao explicita.
- `candidate-private.json` e removido.
- `private-values.json` e removido.
- O out-dir fica apenas com status/summary.
- Status registra `cleanup.executed=true`.
- Status registra writer real bloqueado.
- Status/summary permanecem sanitizados.
- Nada toca `/data` ou `/opt`.
- Nenhum servico, player, MPV, rede ou backend e alterado.
- Self-test passa.
- Smoke local passa.
- Smoke remoto em `/tmp` passa.
- `git diff --check` passa.

## 8. Testes locais

Self-test:

```bash
python3 scripts/board/totem_setup_private_handoff_preflight.py --self-test
```

Smoke local:

- gerar candidata C8;
- criar `private-values.json` sintetico sob `/tmp`;
- rodar C8.6 preflight;
- validar C5.1 `real-dry-run`;
- rodar cleanup C8.6.1;
- confirmar que os dois arquivos privados foram removidos;
- confirmar que so status/summary permanecem.

## 9. Teste remoto

Smoke seguro:

```bash
scripts/remote/run_c8_setup_tmp_on_dev_board.sh root@192.168.18.115
```

O smoke remoto deve provar:

- C8.6 gera candidata privada temporaria;
- C5.1 `real-dry-run` passa antes do cleanup;
- C8.6.1 remove candidata privada e arquivo de valores privados;
- status/summary de cleanup sao gerados com `0600`;
- out-dir permanece `0700`;
- nenhum valor privado aparece em status/summary;
- servico/player nao mudam de estado;
- nada toca `/data`, `/opt`, writer real, MPV, rede ou backend.

## 10. Proximos passos

- C8.7/C6 gate futuro so deve avancar com limpeza definida, canal privado
  aprovado, servico/player bloqueado, backup/rollback C6 confirmados e nova
  autorizacao humana para escrita real.
