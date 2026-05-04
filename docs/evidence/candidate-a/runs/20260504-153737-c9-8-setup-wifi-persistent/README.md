# C9.8 Setup Wi-Fi Persistente - Evidencia Sanitizada

Data: 2026-05-04

Base antes do commit C9.8: `0d6074d`

## Comandos

- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --prepare-only`
- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --run-cancel`
- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --run-complete-with-wifi-persistent`
- snapshot tardio sanitizado de servico, processos, status publico e perfil dedicado

## Cancelamento

- wizard abriu no HDMI/TTY com pausa operacional do player;
- cancelamento foi observado;
- candidata nao foi gerada;
- rede nao foi alterada;
- servico restaurado `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- player/MPV ativos ao final;
- renderer/setup ausentes.

## Conclusao Persistente

- wizard concluiu com Wi-Fi persistente dedicado;
- credenciais foram digitadas localmente no totem;
- `wifi_activation_result=success`;
- `rollback_after_test=not_requested`;
- perfil dedicado final presente;
- `dedicated_profile_persistent=true`;
- secrets temporario removido;
- candidata gerada;
- C5.1 `--allow-mock` passou;
- C5.1 `--real-dry-run` falhou como esperado por placeholders;
- `network_changed=true`.

## Estado Final Tardio

- servico `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player=1;
- MPV=1;
- renderer=0;
- setup=0;
- perfil dedicado presente;
- SSH permaneceu acessivel.

## Nao Alterado

- `/data/config/config.json` nao foi lido;
- `/data/config/config.json` nao foi escrito;
- writer real nao foi chamado;
- hotspot nao foi criado;
- portal nao foi criado;
- reboot nao foi chamado;
- `kiosky-player` nao foi alterado.

## Privacidade

Esta evidencia nao inclui candidata bruta, environment_id real, SSID, senha,
IP, MAC, BSSID, gateway, DNS, hostname, nome real de conexao, UUID, api_key,
api_url real, paths privados ou logs brutos.
