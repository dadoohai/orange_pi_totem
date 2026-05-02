# C6.3A - config real com servico parado na placa de desenvolvimento

Data: 2026-05-02

## Objetivo

Executar a primeira escrita real de `/data/config/config.json` na placa de
desenvolvimento com `kiosky-player.service` parado, usando candidata real
privada, backup restrito, validacao antes/depois e evidencia sanitizada.

## Escopo

- Placa: desenvolvimento, sem registrar IP ou hostname.
- Placa de homologacao: fora de escopo.
- Modo: escrita real autorizada em `/data/config/config.json`.
- Servico: parado antes da escrita e mantido parado ao final.
- Player: nao iniciado.
- Backend, Wi-Fi, NetworkManager, launcher, renderer, unit systemd e
  `kiosky-player`: nao alterados.

## Comandos executados

Comandos executados de forma sanitizada:

- copia dos scripts versionados para `/tmp` na placa;
- `python3 /tmp/totem_config_contract_validate.py --self-test`;
- `python3 /tmp/totem_config_writer_real.py --self-test`;
- inspecoes read-only de metadados da candidata privada sob `/tmp`;
- inspecoes read-only de `/data`, `/data/config` e
  `/data/config/config.json`, sem ler conteudo;
- `systemctl stop kiosky-player.service`;
- `systemctl is-active kiosky-player.service`;
- validacao `real-dry-run` da candidata privada com output em `/tmp`;
- writer real com flags explicitas:
  - `--enable-real-write`;
  - `--confirm-service-stopped`;
  - `--confirm-human-approved-real-write`;
- pos-validacao por metadados, permissoes e contrato agregado;
- confirmacao final de que o servico permaneceu `inactive`.

Nao foram executados `nmcli`, `apt`, `journalctl`, testes de backend, start ou
restart de servico.

## Preflight

- Candidata privada sob `/tmp`: sim.
- Candidata regular file: sim.
- Candidata mode `600`: sim.
- Candidata dentro de repo: nao.
- `/data` existe: sim.
- `/data/config` existe: sim.
- `/data/config/config.json` existia antes da escrita: sim.
- Config anterior mode `640`: sim.
- Config anterior owner/group: `root:totem`.
- Usuario `totem` existe: sim.
- Grupo `totem` existe: sim.
- Servico antes da parada: `active`.
- Servico enabled: sim.

Conteudo da candidata e conteudo da config real nao foram impressos, copiados
para evidencia ou publicados.

## Servico

- Servico parado antes da escrita: sim.
- Estado apos `systemctl stop`: `inactive`.
- Servico final: parado.
- Player iniciado: nao.

O HDMI estava desconectado, mas esta rodada nao iniciou player nem dependeu de
saida visual.

## Real-dry-run

- `real-dry-run` passou: sim.
- `api_key_present`: true.
- `api_key_placeholder_detected`: false.
- `missing_fields_count`: 0.
- `invalid_fields_count`: 0.
- `placeholder_findings_count`: 0.

Nenhum valor real de `api_url`, `api_key`/token, `environment_id` ou
`station_id` foi publicado.

## Escrita real

- Escrita real executada: sim.
- Resultado do writer: `passed`.
- Backup criado: sim.
- Rollback: nao necessario.
- `data_written`: true.
- Validacao pre-write do writer: true.
- Validacao post-write do writer: true.

## Pos-validacao

- `/data/config/config.json` existe: true.
- Mode observado: `640`.
- Owner/group observado: `root:totem`.
- Leitura por `totem`: true.
- Gravacao por `totem`: false.
- Revalidacao ativa: true.
- `missing_fields_count`: 0.
- `invalid_fields_count`: 0.
- `placeholder_findings_count`: 0.

## Backup

- Backup-dir existe: true.
- Backup-dir mode: `700`.
- Backup-dir owner/group: `root:totem`.
- Arquivos de backup observados: 1.
- Backup mais recente mode: `600`.
- Backup mais recente owner/group: `root:totem`.

Conteudo do backup nao foi impresso, copiado para evidencia ou publicado.

## Saida sanitizada

- Out-dir do writer em `/tmp`: mode `700`.
- `writer-status.json`: mode `600`.
- `summary.txt`: mode `600`.
- Valores URI-like nos artefatos do writer: false.
- Marcadores de secret nos artefatos do writer: false.
- `api_key`/token nao foi impresso.
- `api_url` real nao foi impressa.
- `environment_id` real nao foi impresso.
- `station_id` real nao foi impresso.

## Conclusao

C6.3A foi executada com sucesso na placa de desenvolvimento. A config real foi
escrita em `/data/config/config.json` com servico parado, backup restrito,
permissoes `root:totem` `0640`, validacao antes/depois e sem rollback.

O servico permaneceu parado ao final e o player nao foi iniciado.

## Proximos passos

- Revisao humana desta evidencia e do diff.
- Decidir quando iniciar o servico em rodada separada.
- Se o servico for iniciado em rodada futura, observar apenas dados
  sanitizados e nao publicar logs ou secrets.
