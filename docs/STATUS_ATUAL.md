# Status Atual

Data: 2026-04-30

## Resumo executivo

O Candidato A avancou da validacao de base para uma versao de homologacao `v0.1-rc1`, ainda nao producao. A placa passou por boot inicial, reboots curtos, rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, layout `/data`, Wi-Fi cliente 5 GHz e desativacao dos servicos Bluetooth conhecidos sem regressao observada. O Wi-Fi cliente 5 GHz permaneceu funcional apos as desativacoes de Bluetooth/AW859A. Tambem foi feita a preparacao inicial de usuario/diretorios para o `kiosky-player`, a instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, a garantia de `/tmp/kiosky`, a aprovacao do `check_app_prereqs.sh` e o teste manual de MPV via DRM/KMS com confirmacao visual HDMI.

O app ja foi deployado em `/opt/totem/kiosky-player`, a config privada ja foi criada em `/data/config/config.json` fora do Git, e o `kiosk.py` ja rodou manualmente como usuario `totem`. O app baixou midias em `/data/media/kiosky-player`, criou estado em `/data/state/kiosky-player`, criou status em `/tmp/kiosky-status.json`, nao escreveu em `/opt/totem/kiosky-player` durante os probes e encerrou sem processos reais remanescentes depois do timeout controlado.

Ainda nao ha homologacao para producao. A camada OS continua saudavel: `systemctl --failed` permaneceu em `0 loaded units listed` e as rodadas recentes nao mostraram `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`. O bloqueio app-MPV curto foi resolvido para a candidata atual: `mpv_query_uses_fresh_ipc=true` estabilizou IPC, pings, restart e `loadfile`, e a saida explicita `--vo=gpu --gpu-context=drm --ao=null` fez todos os 5 aliases avancarem `time-pos` e `estimated-frame-number` no app real por 300s. A configuracao aprovada na rodada `20260430-133130` vira base da homologacao `v0.1-rc1` em segunda placa/cartao.

## Composicao do Candidato A

- Armbian Build v25.11.
- Debian Bookworm Minimal.
- Orange Pi Zero 3.
- Kernel `6.12.58-current-sunxi64`.
- U-Boot `2025.04`.
- BSP congelado com `BSPFREEZE=yes`.
- Rede gerenciada por NetworkManager.
- Desktop ausente.

## O que foi aprovado

- Boot inicial.
- Reboots curtos.
- Baseline de rede cabeada/NetworkManager.
- Stress leve CPU/RAM de 30 minutos.
- Criacao idempotente do layout `/data`.
- Wi-Fi cliente 5 GHz com conexao NetworkManager existente, mantido funcional apos desabilitar Bluetooth/AW859A.
- Desativacao de `bluetooth.service` sem regressao observada.
- Desativacao de `aw859a-bluetooth.service` com `systemctl --failed` voltando para `0 loaded units listed`.
- Criacao de usuario/grupo `totem` e diretorios iniciais para a aplicacao.
- Instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, sem upgrades/removes e sem tocar em kernel/Armbian.
- `/tmp/kiosky` criado como `totem:totem`, modo `0750`.
- `check_app_prereqs.sh` aprovado apos o runtime minimo e a garantia de `/tmp/kiosky`.
- MPV manual aprovado via DRM/KMS direto, com `vo=drm` e `vo=gpu --gpu-context=drm` funcionando como root e como usuario `totem`, e com confirmacao visual HDMI.
- Deploy manual do `kiosky-player` em `/opt/totem/kiosky-player`.
- Criacao da config privada em `/data/config/config.json`, fora do Git e sem publicacao de secrets.
- Primeiro run manual do app como usuario `totem`, aprovado com ressalvas: o app iniciou, baixou midias, criou estado/status, exibiu algumas midias e permaneceu ativo ate o timeout controlado.
- Instrumentacao de diagnostico MPV/IPC e logs MPV por geracao, sem publicar conteudo sensivel.
- Confirmacao de que os probes manuais nao escreveram em `/opt/totem/kiosky-player`.
- Confirmacao recorrente de `systemctl --failed` em `0 loaded units listed` nas rodadas de app.
- Confirmacao recorrente de ausencia de `Oops`, `panic`, erro EXT4, remount read-only e `mmc timeout/reset` nas rodadas de app.
- `mpv_query_uses_fresh_ipc=true` validado como candidata principal para estabilizar consultas IPC do watchdog: `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0` e `Failed to load media=0` na rodada fresh IPC.
- Midias e transicoes manuais testadas sem evidencia de corrupcao de arquivo ou falha basica de DRM/KMS.
- Matriz de flags MPV isolou a menor alteracao candidata atual: saida explicita `--vo=gpu --gpu-context=drm --ao=null`.
- Observer de 300s do app real aprovado com commit `c71318a`, `mpv_query_uses_fresh_ipc=true`, `mpv_vo=gpu`, `mpv_gpu_context=drm`, `mpv_ao=null` e `low_resource_mode=false`: timeouts, falhas de ping, restarts e falhas de load ficaram em 0; todos os 5 aliases avancaram `time-pos` e frame.

## Rodadas recentes do kiosky-player

- Primeiro run manual: app iniciou como `totem`, atualizou playlist, baixou 5 arquivos de midia, criou estado/status e exibiu algumas midias. Aprovado com ressalvas por 21 `MPV IPC unresponsive` e 5 `Failed to load media`.
- Analise do primeiro run: reforcou a hipotese de watchdog/IPC/restart, com base saudavel e status final `playing`/`mpv_running=true`.
- Run instrumentado: adicionou `mpv_log_file`, `mpv_msg_level` e `mpv_debug_events`; manteve 21 `MPV IPC unresponsive`, aumentou falhas de load para 10 e mostrou 31 restarts/32 processos MPV.
- Logs por geracao: preservou 32 logs `mpv-g*.log`; `MPV IPC startup wait complete` foi 32/32, enfraquecendo falha de startup do IPC e concentrando o problema na responsividade posterior.
- A/B timeout IPC 5s: reduziu levemente pings/timeouts, mas manteve 31 restarts/32 processos MPV e piorou `Failed to load media` para 13; timeout agressivo puro ficou menos provavel.
- Watchdog threshold 2: reduziu `Restarting MPV` de 31 para 18, `MPV process started` de 32 para 19 e `Failed to load media` de 10 para 7; confirmou que watchdog agressivo era parte do problema.
- Threshold 2 com reset por geracao: corrigiu a semantica do contador e trouxe ganho pequeno; restaram timeouts e 3 `Bad file descriptor`.
- Coordenacao IPC/restart com commit `9bdb38c`: zerou `Bad file descriptor` e `MPV IPC command send failed`, reduziu `Restarting MPV` para 13, `MPV process started` para 14, `Failed to load media` para 2 e `Media load retry failed` para 0. Naquele momento, o problema remanescente ainda era `MPV IPC ping failed`/`MPV IPC command timeout` frequente.
- Midia isolada suspeita: o alias `<media-path:e7efe47f02>` tocou com `vo=null` e via DRM/KMS como usuario `totem`, encerrando por EOF; a hipotese de arquivo corrompido perdeu forca.
- Transicao manual de midia: `loadfile` sequencial controle -> suspeita -> controle retornou `success` para os tres aliases e nao reproduziu a falha anterior de `loadfile`.
- Playlist watchdog sem app: playlist completa, duracoes configuradas e pings concorrentes passaram com `loadfile success=5`, ping timeout 0 e base OS limpa.
- MPVController playlist probe: `load_file` passou 5/5 sem restart, mas `ping()` e `get_property()` pelo socket persistente do controller deram timeouts; isso apontou para a estrategia de IPC persistente.
- Fresh IPC query com commit `8c3b420`: `mpv_query_uses_fresh_ipc=true` estabilizou a rodada do app real, com `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1` e `Failed to load media=0`.
- Playback observer do app real: com IPC estabilizado, o observador externo mostrou que 4 aliases ficavam no primeiro frame, apesar de `pause=false`, `idle-active=false` e `eof-reached=false`; somente `<media-path:e7efe47f02>` avancou `time-pos` e frame.
- Flags progress probe: as 4 midias problematicas nao avancaram com flags app/low-resource atuais, nem removendo isoladamente `--correct-pts=no` ou `--video-sync=audio`; todas avancaram com o perfil simples aprovado.
- `low_resource_mode=false`: removeu as flags low-resource fortes do app, mas nao resolveu o problema visual; os mesmos 4 aliases continuaram sem avancar no app real.
- Remaining flags matrix: remover isoladamente `--loop-file=inf`, `--keep-open=yes`, `--image-display-duration=inf` ou adicionar `--no-config` nao resolveu; V5, adicionando `--vo=gpu --gpu-context=drm --ao=null`, fez os aliases problematicos avancarem e preservou o alias que ja funcionava.
- Observer do app real com saida MPV explicita e commit `c71318a`: a configuracao candidata passou por 300s com `MPV IPC command timeout=0`, `MPV IPC ping failed=0`, `Restarting MPV=0`, `MPV process started=1`, `Failed to load media=0` e todos os 5 aliases avancando `time-pos`/frame. Sem `systemd`, sem escrita em `/opt`, sem processo remanescente real e com OS limpa.

## O que foi alterado na placa

- Criado layout persistente em `/data`.
- Criado usuario/grupo `totem`.
- Criados diretorios de aplicacao em `/opt/totem`, `/data/.../kiosky-player` e `/tmp/kiosky`.
- Ajustado ownership de diretorios mutaveis para `totem:totem` onde previsto.
- Usuario `totem` adicionado aos grupos existentes `audio`, `video` e `render`.
- Instalados pacotes de runtime `mpv`, `ffmpeg` e `python3-requests` com `--no-upgrade --no-install-recommends`.
- Criado `/tmp/kiosky` como `totem:totem`, modo `0750`.
- `bluetooth.service` foi desabilitado.
- `aw859a-bluetooth.service` foi desabilitado e o estado falhado foi limpo.
- Deployado `kiosky-player` em `/opt/totem/kiosky-player`, com a rodada aprovada usando commit `c71318a Add configurable MPV output flags`.
- Criada config privada em `/data/config/config.json`, fora do Git.
- Atualizados temporariamente campos de diagnostico/controle da config privada para probes curtos, sem publicar conteudo da config.
- Criados/preservados arquivos de midia em `/data/media/kiosky-player`.
- Criados/preservados arquivos de estado em `/data/state/kiosky-player`.
- Criado/copiado status temporario em `/tmp/kiosky-status.json` durante os probes.
- Criados logs temporarios do MPV em `/tmp/kiosky` durante as rodadas instrumentadas.

Nenhum servico systemd da aplicacao foi instalado, habilitado ou iniciado. Nenhum comando `apt` foi executado nas rodadas recentes de app. A auditoria dos probes nao encontrou escrita em `/opt/totem/kiosky-player` apos o inicio do app.

## O que ainda esta pendente

- `pip` ausente por decisao desta fase.
- `/opt/totem/venv` ainda sem `bin/python` e `bin/pip` executaveis, esperado enquanto `python3-pip`/venv ficam fora.
- `python3-pip` e `python3-venv` continuam fora desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase; nao ha indicacao atual para instala-los apos o teste MPV via DRM/KMS.
- Homologar a configuracao `v0.1-rc1` em uma segunda placa/cartao.
- Repetir observer de 300s na segunda placa/cartao com a config candidata aprovada.
- Fazer teste manual observado de 30 a 60 minutos antes de liberar qualquer teste de `systemd`.
- Unit systemd da aplicacao ainda nao instalada/habilitada na placa.
- Teste longo do app ainda nao liberado.
- Root read-only ainda nao validado.
- Corte seco ainda nao validado.

## Proximos 3 passos tecnicos

1. Homologar `v0.1-rc1` em segunda placa/cartao com a imagem base e o `kiosky-player` no commit `c71318a`.
2. Rodar teste manual observado de 30 a 60 minutos com a mesma configuracao candidata.
3. Depois disso, preparar validacao controlada da unit `systemd` da aplicacao, ainda sem root read-only e sem corte seco.

## Regras que continuam proibidas

Nao executar na placa:

- `apt upgrade`
- `apt full-upgrade`
- `apt dist-upgrade`
- `armbian-upgrade`

## Artefatos brutos

Os artefatos brutos `.tar.gz` permanecem fora do Git. Eles podem existir localmente como arquivos ignorados para auditoria, mas nao devem ser adicionados ao repositorio.
