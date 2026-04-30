# Orange Pi Totem

Documentação técnica e operacional para construção, validação e evolução de uma imagem Armbian customizada para totens baseados em Orange Pi Zero 3.

## Estado atual

**Candidato A**: Armbian Build v25.11 + Debian Bookworm Minimal + kernel `6.12.58-current-sunxi64` + U-Boot `2025.04`.

Status: aprovado em boot inicial, reboots curtos, baseline de rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, criação do layout `/data`, Wi-Fi cliente 5 GHz, desativação de `bluetooth.service`, desativação de `aw859a-bluetooth.service`, preparação inicial de usuário/diretórios para a aplicação, instalação controlada do runtime mínimo (`mpv`, `ffmpeg`, `python3-requests`), validação de pré-requisitos com `/tmp/kiosky` garantido e teste manual de MPV via DRM/KMS com confirmação visual. O `kiosky-player` já foi deployado em `/opt/totem/kiosky-player`, a config privada já foi criada em `/data/config/config.json` fora do Git, e o app já rodou manualmente como usuário `totem`, baixando mídias em `/data/media/kiosky-player`, criando estado em `/data/state/kiosky-player` e status em `/tmp/kiosky-status.json`.

O Candidato A ainda não está homologado para produção. A base do sistema operacional permanece saudável, com `systemctl --failed` em `0 loaded units listed` nas rodadas recentes e sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`. A fase app-MPV avançou: `mpv_query_uses_fresh_ipc=true` estabilizou IPC/watchdog/loadfile, e a saída MPV explícita `--vo=gpu --gpu-context=drm --ao=null` foi aprovada no app real por 300s na rodada `20260430-133130`, com todos os 5 aliases avançando `time-pos` e `estimated-frame-number`. Xorg, Wayland, compositor, Chromium, `pip` e venv continuam fora desta fase.

Pendências atuais antes de produção:

- `pip` ausente e `/opt/totem/venv` ainda sem Python/pip executáveis, por decisão desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase.
- Homologar a versão `v0.1-rc1` em uma segunda placa/cartão.
- Rodar teste manual observado de 30 a 60 minutos com a configuração candidata.
- Serviço `systemd` da aplicação ainda não instalado/habilitado.
- Teste longo ainda não liberado.
- Root read-only ainda não validado.
- Corte seco ainda não validado.

Próximo passo técnico: provisionar a homologação `v0.1-rc1` em uma segunda placa/cartão, repetir o observer de 300s e fazer teste manual observado de 30 a 60 minutos antes de qualquer validação controlada de `systemd`.

## Versão de homologação atual

**v0.1-rc1** é uma versão de homologação, não produção. Ela congela a base Armbian Candidato A e o `kiosky-player` no commit `c71318a Add configurable MPV output flags` para reproduzir a configuração candidata em uma segunda placa/cartão.

Documentação da release: [docs/releases/v0.1-rc1-homologacao/README.md](docs/releases/v0.1-rc1-homologacao/README.md)

## Documentos principais

- [Índice e plano estratégico](docs/00_INDICE_E_PLANO_ESTRATEGICO.md)
- [Decisão técnica e justificativa](docs/01_DECISAO_TECNICA_E_JUSTIFICATIVA.md)
- [Geração da imagem base](docs/02_GERACAO_DA_IMAGEM_BASE.md)
- [Testes iniciais e evidências](docs/03_TESTES_INICIAIS_E_EVIDENCIAS.md)
- [Roadmap de produto, testes, atualização e monitoramento](docs/04_ROADMAP_PRODUTO_TESTES_ATUALIZACAO_MONITORAMENTO.md)
- [Política de atualização](docs/05_POLITICA_DE_ATUALIZACAO.md)
- [Status atual consolidado](docs/STATUS_ATUAL.md)
- [Homologação v0.1-rc1](docs/releases/v0.1-rc1-homologacao/README.md)
- [Template de evidências do Candidato A](docs/evidence/candidate-a/README.md)
- [Evolução MPV IPC/watchdog](docs/app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md)
- [Estado atual do player MPV](docs/app-integration/05_ESTADO_ATUAL_PLAYER_MPV.md)
- [ADR-0004 runtime MPV do kiosky-player](docs/DECISIONS/ADR-0004-kiosky-player-mpv-runtime.md)
- [Documentação consolidada](docs/DOCUMENTACAO_COMPLETA_TOTEM_ORANGEPI_ZERO3.md)

## Scripts de bancada

- `scripts/board/`: scripts para coleta de diagnóstico, snapshot de rede, stress leve, criação idempotente do layout `/data` (`config`, `media/kiosky-player`, `state/kiosky-player`, `spool/kiosky-player`, `logs/kiosky-player`) e desativação idempotente de Bluetooth.
- `scripts/remote/push_and_run.sh`: wrapper local para copiar um script de `scripts/board/` para a placa e executá-lo via SSH quando essa etapa for liberada.

## Regra operacional crítica

Não rodar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade` em campo. A base foi validada com kernel/DTB/U-Boot/BSP congelados. Atualizações devem seguir fluxo controlado por release.
