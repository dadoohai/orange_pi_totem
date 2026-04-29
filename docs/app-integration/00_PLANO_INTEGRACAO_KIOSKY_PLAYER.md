# Plano de integracao controlada do kiosky-player

## Objetivo

Preparar a primeira integracao do `kiosky-player` na imagem Candidato A sem ativar execucao automatica. Esta fase cria usuario, diretorios, permissoes e copia codigo para revisao local na placa.

Nao usar este plano para instalar dependencias, habilitar systemd, iniciar o app, iniciar MPV, chamar API real ou baixar midia real.

## Por que systemd ainda nao sera ativado

O service de sistema do `kiosky-player` ja existe como template revisavel no repositorio da aplicacao, mas ainda depende de validacao manual da stack de display da Orange Pi. Antes de `systemctl enable` ou `systemctl start`, precisamos confirmar:

- MPV instalado e executavel;
- display/compositor final e variaveis de ambiente necessarias;
- permissao do usuario `totem` nos caminhos mutaveis;
- config privada em `/data/config/config.json`;
- primeira execucao manual supervisionada sem tela preta, crash loop ou escrita em `/opt/totem`.

Ativar systemd antes desses pontos pode esconder falhas em restart loop e dificultar diagnostico.

## Ordem de integracao

1. Rodar coleta de diagnostico antes da mudanca, quando a etapa remota estiver liberada.
2. Criar usuario e grupo `totem`.
3. Criar diretorios de aplicacao e dados.
4. Rodar check de pre-requisitos sem instalar nada.
5. Copiar o codigo do `kiosky-player` para `/opt/totem/kiosky-player`.
6. Criar manualmente a config privada em `/data/config/config.json`.
7. Revisar service systemd, mas nao instalar nem habilitar.
8. Testar MPV/display manualmente.
9. Permitir primeiro run manual do app somente quando os criterios abaixo estiverem atendidos.

## Usuario e permissoes

Scripts preparados:

```bash
./scripts/remote/push_and_run.sh root@<orange-pi> scripts/board/setup_totem_user.sh
./scripts/remote/push_and_run.sh root@<orange-pi> scripts/board/setup_app_dirs.sh
./scripts/remote/push_and_run.sh root@<orange-pi> scripts/board/check_app_prereqs.sh
```

`setup_totem_user.sh` cria usuario/grupo `totem` quando ausentes, sem senha e com shell `nologin`. Se o usuario ja existir, o script nao remove nem recria.

`setup_app_dirs.sh` cria:

```text
/opt/totem
/opt/totem/kiosky-player
/opt/totem/venv
/data/config
/data/media/kiosky-player
/data/state/kiosky-player
/data/spool/kiosky-player
/data/logs/kiosky-player
/tmp/kiosky
```

O codigo em `/opt/totem` fica `root:root`. Dados mutaveis e runtime ficam `totem:totem`.

## Copia do app

Depois de validar usuario e diretorios, copiar o checkout local do `kiosky-player`:

```bash
./scripts/remote/deploy_kiosky_player.sh root@<orange-pi> /path/to/kiosky-player
```

O deploy copia somente codigo para `/opt/totem/kiosky-player`. Ele exclui `.git`, caches Python, `.venv`, cache de midia, `.env` e `config.json`. Ele nao instala dependencias, nao copia config privada, nao habilita systemd e nao inicia o app.

## Config privada

Criar `/data/config/config.json` manualmente a partir de `config.appliance.example.json` do `kiosky-player`.

Campos que devem ser preenchidos fora do Git:

```json
{
  "api_url": "https://api.example.invalid/search",
  "api_key": "replace-with-api-key",
  "environment_id": "replace-with-environment-id",
  "station_id": "replace-with-station-id"
}
```

Manter no perfil appliance:

```json
{
  "cache_dir": "/data/media/kiosky-player",
  "state_dir": "/data/state/kiosky-player",
  "status_file": "/tmp/kiosky-status.json",
  "ipc_path": "/tmp/kiosky/mpv.sock",
  "runtime_dir": "/tmp/kiosky",
  "strict_paths_enabled": true,
  "hotkeys_enabled": false,
  "config_ui_enabled": false,
  "telemetry_enabled": false,
  "sync_enabled": false
}
```

Nao registrar tokens, API keys ou environment IDs reais em evidencia publica.

## MPV e display

MPV/display ainda devem ser testados manualmente. A integracao precisa definir a stack final antes de ativar o service:

- console framebuffer, X11, Wayland ou compositor dedicado;
- variaveis como `DISPLAY` ou `WAYLAND_DISPLAY`, se aplicavel;
- permissao do usuario `totem` para acessar display/audio/input, se necessario.

## Criterios para primeiro run manual

Permitir o primeiro run manual apenas quando:

- `check_app_prereqs.sh` passar sem erros;
- `/data/config/config.json` existir e nao contiver placeholders;
- `/opt/totem/kiosky-player/kiosk.py` estiver presente e `root:root`;
- `/data/media/kiosky-player`, `/data/state/kiosky-player` e `/tmp/kiosky` forem gravaveis por `totem`;
- MPV tiver sido validado manualmente no display escolhido;
- nao houver necessidade de escrever em `/opt/totem`;
- o teste usar API/midia controlada ou modo offline planejado.

Mesmo nesse ponto, nao habilitar systemd. O primeiro run deve ser manual, supervisionado e com coleta de diagnostico antes/depois.
