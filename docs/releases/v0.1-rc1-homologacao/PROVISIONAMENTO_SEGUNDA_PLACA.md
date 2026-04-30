# Provisionamento da segunda placa - v0.1-rc1

Este roteiro e para execucao humana em bancada. Ele documenta o processo da
segunda Orange Pi Zero 3/cartao microSD e nao autoriza o Codex a usar SSH, rodar
comandos na placa ou alterar scripts durante esta consolidacao documental.

Status: homologacao, nao producao.

## Regras da rodada

- Comecar com cartao testado no H2testw.
- Nao executar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou
  `armbian-upgrade`.
- Nao ativar `systemd` da aplicacao.
- Nao publicar `api_key`, `api_url` privada, `environment_id`, `station_id`,
  nomes privados, payloads privados ou artefatos brutos.
- Nao commitar `.tar.gz`, `raw/` ou `extracted/`.
- Manter config privada em `/data/config/config.json`, fora do Git.

## 1. Cartao

1. Testar o cartao com H2testw.
2. Registrar no checklist:
   - tamanho anunciado;
   - resultado final;
   - velocidade de escrita/leitura;
   - operador;
   - data.
3. Prosseguir somente se o teste terminar sem erros.

## 2. Gravacao da imagem

Imagem base:

```text
Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58_minimal.img
```

1. Gravar a imagem no cartao com ferramenta visual de bancada.
2. Se a ferramenta oferecer verificacao pos-gravacao, habilitar.
3. Nao usar imagem clonada da placa atual.
4. Nao editar a particao manualmente antes do primeiro boot.

## 3. Primeiro boot

1. Inserir o cartao na segunda Orange Pi Zero 3.
2. Conectar fonte adequada, HDMI e rede de bancada.
3. Ligar a placa.
4. Confirmar que o boot chega ao sistema.
5. Registrar kernel, versao Armbian, RAM detectada e temperatura inicial.

Esperado:

```text
kernel 6.12.58-current-sunxi64
Armbian 25.11.1
Debian Bookworm Minimal
NetworkManager
sem desktop
```

## 4. Rede e SSH

1. Validar link de rede.
2. Validar que o canal SSH de bancada responde.
3. Nao publicar IP, hostname, SSID, nome de conexao ou topologia privada.
4. Coletar apenas resumo sanitizado para o README da rodada.

## 5. Layout `/data`

Rodar o setup de `/data` usado no Candidato A.

Diretorios esperados:

```text
/data/config
/data/media/kiosky-player
/data/state/kiosky-player
/data/spool/kiosky-player
/data/logs/kiosky-player
```

Validar ownership e permissoes de acordo com os scripts de bancada.

## 6. Usuario e diretorios do app

Criar/validar:

- usuario `totem`;
- grupo `totem`;
- grupos auxiliares existentes `audio`, `video` e `render`;
- `/opt/totem`;
- `/opt/totem/kiosky-player`;
- `/tmp/kiosky` como `totem:totem`, modo `0750`.

Nao iniciar servico da aplicacao nesta etapa.

## 7. Bluetooth

Desabilitar os servicos Bluetooth ja validados no Candidato A:

- `bluetooth.service`;
- `aw859a-bluetooth.service`.

Depois validar:

- `systemctl --failed` voltou a `0 loaded units listed`;
- Wi-Fi cliente continua funcional, se aplicavel;
- nenhum bloqueador novo apareceu no filtro critico de kernel.

## 8. Runtime minimo

Se a imagem base ainda nao tiver os pacotes de runtime, instalar somente:

- `mpv`;
- `ffmpeg`;
- `python3-requests`.

Nao instalar:

- `python3-pip`;
- `python3-venv`;
- Xorg;
- Wayland;
- compositor;
- Chromium.

Usar instalacao controlada de pacote especifico, sem upgrade amplo.

## 9. Deploy do kiosky-player

Deployar o `kiosky-player` a partir da branch `appliance-v0.1`, no commit:

```text
c71318a Add configurable MPV output flags
```

Validar:

- worktree local do app limpo antes do deploy;
- commit deployado confere com `c71318a`;
- deploy foi para `/opt/totem/kiosky-player`;
- nenhum segredo entrou no checkout.

## 10. Config privada

Criar `/data/config/config.json` somente na placa, fora do Git.

Usar como base publica:

```text
docs/app-integration/config.homologation-v0.1.example.json
```

Substituir na placa:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`, se aplicavel.

Campos candidatos obrigatorios:

```text
mpv_query_uses_fresh_ipc=true
mpv_vo=gpu
mpv_gpu_context=drm
mpv_ao=null
low_resource_mode=false
watchdog_interval_sec=10
mpv_watchdog_ping_failures_before_restart=2
mpv_watchdog_grace_after_load_sec=0
mpv_watchdog_grace_after_restart_sec=0
mpv_ipc_timeout_sec=2.0
mpv_startup_timeout_sec=10.0
hwdec=auto-safe
mpv_log_file=/tmp/kiosky/mpv.log
mpv_msg_level=all=v
mpv_debug_events=true
```

Permissao esperada:

```text
owner root:totem
mode 0640
```

## 11. Pre-requisitos do app

Rodar `check_app_prereqs` apos criar usuario, diretorios, runtime minimo,
`/tmp/kiosky` e config privada.

Resultado esperado:

- runtime minimo encontrado;
- paths appliance existentes;
- config privada legivel pelo usuario/grupo esperado;
- sem dependencia de `pip` ou venv;
- sem exigencia de desktop/compositor.

## 12. Observer de homologacao

Rodar o observer de homologacao do app real, ainda sem `systemd`, com duracao de
300s e mesma config da RC1.

Metricas esperadas:

- `MPV IPC command timeout=0`;
- `MPV IPC ping failed=0`;
- `Restarting MPV=0`;
- `MPV process started=1`;
- `Failed to load media=0`;
- todos os aliases esperados avancando `time-pos` e `estimated-frame-number`;
- `systemctl --failed=0`;
- sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`;
- sem escrita em `/opt/totem/kiosky-player`;
- sem processo remanescente real de `kiosk.py` ou `mpv`.

## 13. Nao ativar systemd

Nao executar nesta RC1:

- `systemctl enable` da aplicacao;
- `systemctl start` da aplicacao;
- instalacao de unit nova do `kiosky-player`;
- validacao de reboot automatico da aplicacao.

A validacao controlada de `systemd` fica para depois do observer de 300s e do
teste manual observado de 30 a 60 minutos.

## 14. Registro de evidencia

Para cada rodada, criar README sanitizado em `docs/evidence/candidate-a/runs/`.

Registrar somente:

- objetivo;
- commit do app;
- config candidata em campos permitidos;
- metricas agregadas;
- resultado de `systemctl --failed`;
- filtro critico de kernel;
- conclusao.

Nao registrar:

- artefatos brutos;
- paths reais de midia;
- URLs privadas;
- API keys;
- IDs privados;
- nomes privados;
- payloads da API.
