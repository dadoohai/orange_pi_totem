# Checklist de homologacao v0.1-rc1

Status: homologacao, nao producao.

## Identificacao

- [ ] Data registrada.
- [ ] Operador registrado.
- [ ] Segunda placa identificada sem publicar identificadores privados.
- [ ] Cartao microSD identificado sem publicar dados privados.
- [ ] Fonte e tela de bancada registradas.
- [ ] Imagem base registrada.
- [ ] Commit do `kiosky-player` registrado: `c71318a`.

## Cartao e imagem

- [ ] H2testw passou sem erros.
- [ ] Imagem gravada no cartao.
- [ ] Primeiro boot concluido.
- [ ] Kernel confirmado: `6.12.58-current-sunxi64`.
- [ ] U-Boot/base registrados conforme Candidato A.
- [ ] NetworkManager presente.
- [ ] Sem desktop.

## Rede

- [ ] Rede cabeada validada.
- [ ] SSH de bancada validado.
- [ ] Wi-Fi validado, se aplicavel.
- [ ] Nenhum IP, hostname, SSID ou nome privado publicado.

## Saude da base

- [ ] `systemctl --failed` retorna `0 loaded units listed`.
- [ ] Filtro critico de kernel sem `Oops`.
- [ ] Filtro critico de kernel sem `panic`.
- [ ] Filtro critico de kernel sem erro EXT4.
- [ ] Filtro critico de kernel sem remount read-only.
- [ ] Filtro critico de kernel sem `mmc timeout/reset`.
- [ ] Temperatura registrada antes do app.
- [ ] Temperatura registrada durante/depois do app.

## Layout e usuario

- [ ] `/data` existe.
- [ ] `/data/config` existe.
- [ ] `/data/media/kiosky-player` existe.
- [ ] `/data/state/kiosky-player` existe.
- [ ] `/data/spool/kiosky-player` existe.
- [ ] `/data/logs/kiosky-player` existe.
- [ ] Usuario `totem` existe.
- [ ] Diretorios do app existem em `/opt/totem`.
- [ ] `/tmp/kiosky` existe com owner/mode esperados.

## Runtime e app

- [ ] Runtime minimo instalado: `mpv`.
- [ ] Runtime minimo instalado: `ffmpeg`.
- [ ] Runtime minimo instalado: `python3-requests`.
- [ ] `python3-pip` continua fora do escopo.
- [ ] `python3-venv` continua fora do escopo.
- [ ] Xorg/Wayland/compositor/Chromium continuam fora do escopo.
- [ ] `bluetooth.service` desabilitado.
- [ ] `aw859a-bluetooth.service` desabilitado.
- [ ] `kiosky-player` deployado no commit `c71318a`.
- [ ] `check_app_prereqs` passou.

## Config privada

- [ ] `/data/config/config.json` criado fora do Git.
- [ ] `api_url` real nao foi publicada.
- [ ] `api_key` real nao foi publicada.
- [ ] `environment_id` real nao foi publicado.
- [ ] `station_id` real nao foi publicado, se aplicavel.
- [ ] `mpv_query_uses_fresh_ipc=true`.
- [ ] `mpv_vo=gpu`.
- [ ] `mpv_gpu_context=drm`.
- [ ] `mpv_ao=null`.
- [ ] `low_resource_mode=false`.
- [ ] `watchdog_interval_sec=10`.
- [ ] `mpv_watchdog_ping_failures_before_restart=2`.
- [ ] `mpv_watchdog_grace_after_load_sec=0`.
- [ ] `mpv_watchdog_grace_after_restart_sec=0`.
- [ ] `mpv_ipc_timeout_sec=2.0`.
- [ ] `mpv_startup_timeout_sec=10.0`.
- [ ] `hwdec=auto-safe`.
- [ ] `mpv_log_file=/tmp/kiosky/mpv.log`.
- [ ] `mpv_msg_level=all=v`.
- [ ] `mpv_debug_events=true`.

## Observer de 300s

- [ ] App rodou manualmente como `totem`.
- [ ] Observer 300s executado.
- [ ] `MPV IPC command timeout=0`.
- [ ] `MPV IPC ping failed=0`.
- [ ] `Restarting MPV=0`.
- [ ] `MPV process started=1`.
- [ ] `Failed to load media=0`.
- [ ] `MPV loadfile returned error=0`.
- [ ] `Media load retry failed=0`.
- [ ] Todos os 5 aliases avancaram `time-pos`.
- [ ] Todos os 5 aliases avancaram `estimated-frame-number`.
- [ ] `pause=true` nao apareceu durante janelas esperadas.
- [ ] `idle-active=true` nao apareceu durante janelas esperadas.
- [ ] EOF inesperado nao apareceu durante janelas esperadas.

## Pos-run

- [ ] Observacao humana realizada.
- [ ] Teste manual observado de 30 a 60 minutos realizado, se esta for a rodada longa.
- [ ] Temperatura final registrada.
- [ ] Sem processo remanescente real de `kiosk.py`.
- [ ] Sem processo remanescente real de `mpv`.
- [ ] Sem escrita em `/opt/totem/kiosky-player`.
- [ ] `systemctl --failed` final retorna `0 loaded units listed`.
- [ ] Filtro critico de kernel final limpo.
- [ ] Nenhum `.tar.gz`, `raw/` ou `extracted/` foi adicionado ao Git.

## Resultado final

- [ ] Aprovado para proximo passo: teste manual observado de 30 a 60 minutos.
- [ ] Bloqueado por falha documentada.
- [ ] Requer nova rodada com ajuste documentado.

Observacoes sanitizadas:

```text
Preencher sem secrets, URLs privadas, IDs privados, nomes privados ou payloads.
```
