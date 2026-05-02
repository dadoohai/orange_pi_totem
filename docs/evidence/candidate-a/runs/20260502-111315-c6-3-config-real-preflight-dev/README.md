# C6.3 config real preflight - desenvolvimento

Data: 2026-05-02

## Objetivo

Executar C6.3-preflight read-only na placa de desenvolvimento para inspecionar
condicoes reais antes da primeira escrita em `/data/config/config.json`.

C6.3-preflight nao escreve config real, nao usa token real, nao le conteudo de
config real, nao inicia player e nao altera servico.

## Escopo

- Placa: desenvolvimento, sem publicar IP ou hostname.
- Modo: read-only.
- Config real: conteudo nao lido.
- `/data`: sem escrita.
- NetworkManager: nao alterado.
- `systemd`: apenas consultas read-only.
- Artefatos brutos remotos: nao versionados.

## Comandos read-only executados

Leituras locais de documentacao e scripts:

```sh
sed -n '1,240p' docs/DECISIONS/ADR-0010-api-token-provisioning.md
sed -n '1,380p' docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md
sed -n '1,260p' docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md
sed -n '1,220p' docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md
sed -n '1,260p' docs/evidence/candidate-a/runs/20260502-084121-c6-2-writer-real-sim-dev-smoke/README.md
sed -n '1,360p' scripts/board/totem_config_writer_real.py
sed -n '1,360p' scripts/board/totem_config_contract_validate.py
sed -n '1,220p' scripts/board/kiosky-player.service
sed -n '1,520p' scripts/board/kiosky_service_launcher.sh
sed -n '1,700p' docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md
sed -n '1,190p' docs/product/13_RISCOS_ONBOARDING_WIFI_CONFIG.md
```

Inspecao na placa de desenvolvimento, com alvo sanitizado:

```sh
ssh <dev-board> 'sh -s'
```

O script remoto executou somente comandos read-only:

```sh
id totem
getent group totem
getent group audio
getent group video
getent group render
id -nG totem
test -e/-d/-f /data
test -e/-d/-f /data/config
test -e/-d/-f /data/config/config.json
stat -c "%a" /data
stat -c "%U" /data
stat -c "%G" /data
stat -c "%a" /data/config
stat -c "%U" /data/config
stat -c "%G" /data/config
stat -c "%a" /data/config/config.json
stat -c "%U" /data/config/config.json
stat -c "%G" /data/config/config.json
runuser -u totem -- test -r /data/config/config.json
runuser -u totem -- test -w /data/config/config.json
systemctl is-enabled kiosky-player.service
systemctl is-active kiosky-player.service
systemctl show kiosky-player.service -p ActiveState -p SubState -p FragmentPath -p User -p Group --no-pager
```

Nao foram executados `cat`, `head`, `tail`, `jq`, `grep` ou leitura do conteudo
de `/data/config/config.json`. Nao foi executado `journalctl`. Nao foi
executado `nmcli`.

## Usuario e grupos

Resultado sanitizado:

| Item | Resultado |
| --- | --- |
| usuario `totem` existe | `true` |
| grupo `totem` existe | `true` |
| grupo `audio` existe | `true` |
| grupo `video` existe | `true` |
| grupo `render` existe | `true` |
| `totem` pertence a `totem` | `true` |
| `totem` pertence a `audio` | `true` |
| `totem` pertence a `video` | `true` |
| `totem` pertence a `render` | `true` |

UID/GID e arquivos completos de usuarios/grupos nao foram publicados.

## `/data/config`

Resultado sanitizado, sem conteudo:

| Path | Exists | Type | Mode | Owner/group categoria |
| --- | --- | --- | --- | --- |
| `/data` | `true` | `dir` | `755` | `root_root` |
| `/data/config` | `true` | `dir` | `750` | `totem_totem` |
| `/data/config/config.json` | `true` | `file` | `640` | `root_totem` |

Checks de permissao:

| Check | Resultado |
| --- | --- |
| `config.json` legivel por `totem` | `true` |
| `config.json` gravavel por `totem` | `false` |

O conteudo de `/data/config/config.json` nao foi lido, copiado ou publicado.
`api_key`, token, `api_url`, `environment_id` e `station_id` reais nao foram
lidos.

## Servico

Resultado read-only:

| Campo | Resultado |
| --- | --- |
| `systemctl is-enabled` | `enabled` |
| `systemctl is-active` | `active` |
| `ActiveState` | `active` |
| `SubState` | `running` |
| `User` | `totem` |
| `Group` | `totem` |
| `FragmentPath` | `/etc/systemd/system/kiosky-player.service` |

Nenhum comando `systemctl stop/start/restart/enable/disable` foi executado.

## Launcher/config validation

Revisao da versao versionada do launcher:

- path default da config: `/data/config/config.json`;
- app iniciado com `kiosk.py --config "$CONFIG_PATH"`;
- `config_valid` exige arquivo existente, legivel e JSON objeto;
- campos obrigatorios no launcher: `api_url`, `api_key`, `environment_id`,
  `cache_dir`, `state_dir`, `status_file`, `ipc_path`;
- se `config_valid` passa e ha display conectado, `handle_connected_display`
  chama `run_app_once`;
- se config esta ausente/invalida, o launcher publica `config_missing` e nao
  chama o app principal.

## Conclusao

C6.3-preflight read-only confirmou que:

- `/data/config/config.json` ja existe;
- o arquivo esta com mode `640` e categoria `root_totem`;
- o usuario `totem` consegue ler, mas nao escrever a config;
- o servico esta `enabled` e `active/running`;
- o launcher pode iniciar o app automaticamente quando a config default e
  considerada valida.

Risco principal: escrever uma config real valida com o servico ativo pode fazer
o player iniciar antes de completar evidencia, rollback e verificacoes de
pos-escrita.

Recomendacao: C6.3 deve ocorrer com `kiosky-player.service` parado durante a
escrita real, ou com outro bloqueio operacional equivalente aprovado antes da
execucao.

## Confirmacoes

- Conteudo de config real nao foi lido.
- Nada foi escrito em `/data`.
- `/data/config` nao foi criado.
- `/data/config/config.json` nao foi escrito.
- Config real nao foi alterada.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- `systemd` nao foi alterado.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- Nenhum token real foi usado.
- Nenhum pacote foi instalado.

## Bloqueios antes de C6.3

- Aprovacao humana explicita para escrita real.
- Canal local privado para candidata real e token.
- Candidata real validada em `real-dry-run`.
- Owner/group/mode finais aprovados.
- Backup real aprovado.
- Rollback real aprovado.
- Servico parado ou bloqueio equivalente aprovado.
- Evidencia sanitizada aprovada.
