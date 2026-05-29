# Board audit (sanitized) — Parts 2 & 3

Coleta SSH read-only. Sem secrets, sem URLs, sem api_url/api_key/environment_id,
sem SSID/senha, sem IP/MAC/DNS. Senha de SSH nao salva nem registrada.

## Boot / sistema
- board_image_version=c17.4.2
- kernel=6.12.58-current-sunxi64 (Armbian 25.11.1, Orange Pi Zero 3)
- boot_id_digest=50c26d6f1abe (sha256 truncado do boot_id; nao identificavel)
- uptime ~1h no momento da coleta
- board_host=redacted

## Servicos
- kiosky-player.service=active (SubState=running, NRestarts=0)
- NetworkManager=active
- ssh=active / sshd=active
- chrony.service=active ; systemd-timesyncd=inactive
- totem-core.service=inactive
- systemctl --failed: 1 unidade = `aw859a-bluetooth.service` (bluetooth; sem
  relacao com playback)
- chrony tracking: Stratum 2, System time ~0.0008s, Last offset ~-0.0008s,
  RMS offset ~0.0024s, Leap Normal => tempo estavel

## Processo do player
- unit ExecStart: `bash /opt/totem/bin/totem-kiosky-launcher.sh`
- processo Python real: `/usr/bin/python3 /opt/totem/kiosky-player/kiosk.py --config <config.json>`
- **board_player_source=/opt** (imagem assada)
- `/data/apps/kiosky-player/current` -> `releases/homolog-...-c71318a` existe mas
  e release staged, NAO ativo nesta imagem
- totem-updatectl=ausente nesta imagem

## Fingerprint do player (Parte 3)
- `/opt/totem/kiosky-player/kiosk.py`: sha256 `38ecb0de...`, size 131071,
  mtime 2026-05-14 == commit local **307d986 (C18.1)** (byte a byte)
- `/data/apps/.../current/kiosk.py` (inativo): sha256 `24539f00...`, size 119853
  == commit local **c71318a**
- repo HEAD == `d4e4c4e` (C18.2)
- assinaturas C18.2 no arquivo em execucao (/opt): resolve_exposure_duration_ms=0,
  exposureTimeMs=0, exposureTimeSeconds=0, duration_source=0; expressao antiga
  presente (1); loop-file=inf presente (1); sync_enabled key presente (10)
- **board_has_c18_2_duration_fix=false**
- **board_player_matches_local_head=false**

## MPV (sanitizado, sem URL)
MPV iniciado em modo idle/IPC (midias carregadas via loadfile no socket; nenhum
arquivo na cmdline):
```
mpv --fs --force-window=yes --idle=yes --keep-open=yes --no-terminal
    --loop-file=inf --image-display-duration=inf --no-osc --osd-level=0
    --input-ipc-server=/tmp/kiosky/mpv.sock --vo=gpu --gpu-context=drm --ao=null
    --no-input-default-bindings --video-rotate=270 --input-conf=/tmp/kiosky/hotkeys.conf
    --input-vo-keyboard=yes --hwdec=auto
```
- mpv_present=true
- **loop-file=inf presente** ; **loop-playlist ausente**
- vo=gpu, gpu-context=drm (DRM/KMS, sem desktop), ao=null

## Estado em /data/state/kiosky-player
- cache_index.json, last_success.json, launcher-status.json, playlist_last.json
- `status_file` default vazio no codigo pre-C18.2; status_file definido na config
  (config_status_file_set=true), porem a placa nao expoe `duration_source`
  (pre-C18.2)
- /tmp/kiosky: mpv.sock, hotkeys.conf, startup-feedback.svg
