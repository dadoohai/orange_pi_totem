# Status aggregator A1.1

Status: implementacao local nao integrada ao launcher.

Data: 2026-05-01

## Objetivo

Implementar o primeiro agregador sanitizado de status do appliance. O objetivo
e produzir um JSON publico conforme `STATUS_CONTRACT_V0.md` e um SVG local de
preview, ainda sem exibir na tela e sem iniciar MPV.

Esta etapa nao altera systemd, nao altera `kiosky-player`, nao acessa
`/dev/dri`, nao usa internet e nao toca placas.

## Entradas

O script `scripts/board/totem_status_aggregate.py` le arquivos locais quando
existem:

- `/data/state/kiosky-player/launcher-status.json`;
- `/tmp/kiosky-launcher-status.json`, como fallback;
- `/tmp/kiosky-status.json`.

Argumentos opcionais para testes locais:

- `--launcher-status`;
- `--player-status`;
- `--out-dir`;
- `--state-override`.

Quando `--launcher-status` nao e informado, o agregador tenta primeiro o status
principal em `/data` e depois o fallback em `/tmp`. O script nao le
`/data/config/config.json`, para evitar manipular configuracao privada nesta
fase.

## Saidas

Por padrao, o agregador escreve:

- `/tmp/dadooh-status/status.json`;
- `/tmp/dadooh-status/status.svg`.

O `--out-dir` deve apontar para um diretorio sob `/tmp`. Os arquivos sao
escritos de forma atomica simples e com permissao `0600`; o diretorio recebe
permissao `0700`.

## Estados suportados

Estados publicos atuais:

- `booting`;
- `display_missing`;
- `config_missing`;
- `starting_player`;
- `player_running`;
- `player_error`;
- `maintenance_placeholder`.

Mapeamento inicial:

| Entrada | Estado publico |
| --- | --- |
| launcher `display_missing` ou `display_connected=false` | `display_missing` |
| launcher `config_missing` ou campo publico `config_state=missing` | `config_missing` |
| player `playback_state=playing` ou `mpv_running=true` | `player_running` |
| launcher `running` sem player confirmado | `starting_player` |
| launcher `app_exited` ou `last_app_exit_code` inteiro | `player_error` |
| ausencia de entradas conclusivas | `booting` |

`--state-override` permite exercitar qualquer estado publico sem depender de
arquivos reais da placa.

## Sanitizacao

O agregador nao copia campos brutos dos status de origem para o JSON publico.
Ele publica apenas campos controlados:

- estado publico;
- booleano de display;
- estados publicos de rede, config, player e servico;
- codigo de erro publico;
- mensagem e dica vindas de tabela fixa;
- `device_label` generico;
- versoes publicas.

O JSON e o SVG nao devem conter `api_url`, `api_key`, `environment_id`,
`station_id`, URLs privadas, payloads privados, paths reais de midia, nomes
privados, SSID, senha, IP publico, tokens, headers ou cookies.

## Exemplos

Fixtures sanitizados:

- `scripts/board/testdata/status_aggregate/launcher-display-missing.json`;
- `scripts/board/testdata/status_aggregate/launcher-running.json`;
- `scripts/board/testdata/status_aggregate/player-running.json`;
- `scripts/board/testdata/status_aggregate/launcher-config-missing.json`;
- `scripts/board/testdata/status_aggregate/launcher-player-error.json`.

Exemplo local:

```sh
python3 scripts/board/totem_status_aggregate.py \
  --launcher-status scripts/board/testdata/status_aggregate/launcher-display-missing.json \
  --out-dir /tmp/dadooh-status-test
```

Exemplo para player rodando:

```sh
python3 scripts/board/totem_status_aggregate.py \
  --launcher-status scripts/board/testdata/status_aggregate/launcher-running.json \
  --player-status scripts/board/testdata/status_aggregate/player-running.json \
  --out-dir /tmp/dadooh-status-test
```

## Integracao futura com launcher

Na subfase A1.2, o launcher chama o agregador antes de qualquer renderer de
tela. A ordem proposta e:

1. launcher atualiza seu status bruto;
2. agregador escreve `/tmp/dadooh-status/status.json` e `status.svg`;
3. renderer futuro exibe o SVG ou asset derivado;
4. antes de iniciar o player, launcher encerra o renderer e aguarda sua saida;
5. somente entao o `kiosky-player` inicia e pode tomar DRM/KMS.

Esta etapa ainda nao implementa o renderer operacional nem altera a ordem de
processos.

## Riscos

- Um campo bruto futuro pode parecer seguro mas carregar dado privado; a regra
  continua sendo publicar apenas valores controlados.
- `config_missing` ainda depende de estado publico futuro do launcher ou de
  `--state-override`; o agregador nao inspeciona config privada.
- O SVG gerado e preview local; a exibicao real ainda precisa validar disputa
  DRM/KMS.
- Estados do player podem evoluir e exigir revisao do mapeamento.

## Validacao feita

Validacao local usada nesta etapa:

- `python3 -m py_compile scripts/board/totem_status_aggregate.py`;
- `python3 -m py_compile scripts/board/totem_status_render_preview.py`;
- smoke test escrevendo `status.json` e `status.svg` em subdiretorios de
  `/tmp/dadooh-status-test` para `display_missing`, `player_running`,
  `config_missing` e `player_error`;
- `git diff --check`.
