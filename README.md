# Orange Pi Totem

Documentação técnica e operacional para construção, validação e evolução de uma imagem Armbian customizada para totens baseados em Orange Pi Zero 3.

## Estado atual

**Candidato A**: Armbian Build v25.11 + Debian Bookworm Minimal + kernel `6.12.58-current-sunxi64` + U-Boot `2025.04`.

Status: aprovado em boot inicial, reboots curtos, baseline de rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, criação do layout `/data`, Wi-Fi cliente 5 GHz, desativação de `bluetooth.service`, desativação de `aw859a-bluetooth.service`, preparação inicial de usuário/diretórios para a aplicação, instalação controlada do runtime mínimo (`mpv`, `ffmpeg`, `python3-requests`), validação de pré-requisitos com `/tmp/kiosky` garantido e teste manual de MPV via DRM/KMS com confirmação visual. O `kiosky-player` já foi deployado em `/opt/totem/kiosky-player`, a config privada já foi criada em `/data/config/config.json` fora do Git, e o app já rodou manualmente como usuário `totem`, baixando mídias em `/data/media/kiosky-player`, criando estado em `/data/state/kiosky-player` e status em `/tmp/kiosky-status.json`.

O Candidato A ainda não está homologado para produção. A base do sistema operacional permanece saudável, com `systemctl --failed` em `0 loaded units listed` nas rodadas recentes e sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`. O bloqueio atual está concentrado na integração app-MPV: responsividade do IPC, política do watchdog e coordenação de restart. Xorg, Wayland, compositor, Chromium, `pip` e venv continuam fora desta fase.

Pendências atuais antes de produção:

- `pip` ausente e `/opt/totem/venv` ainda sem Python/pip executáveis, por decisão desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase.
- Problema remanescente de MPV IPC/watchdog/restart ainda não resolvido.
- Serviço `systemd` da aplicação ainda não instalado/habilitado.
- Teste longo ainda não liberado.
- Root read-only ainda não validado.
- Corte seco ainda não validado.

Próximo passo técnico: repetir um A/B curto, ainda sem `systemd`, mantendo os demais campos constantes e usando `mpv_watchdog_ping_failures_before_restart=999` para observar se reiniciar por falha de ping IPC é destrutivo demais antes de liberar teste mais longo.

## Documentos principais

- [Índice e plano estratégico](docs/00_INDICE_E_PLANO_ESTRATEGICO.md)
- [Decisão técnica e justificativa](docs/01_DECISAO_TECNICA_E_JUSTIFICATIVA.md)
- [Geração da imagem base](docs/02_GERACAO_DA_IMAGEM_BASE.md)
- [Testes iniciais e evidências](docs/03_TESTES_INICIAIS_E_EVIDENCIAS.md)
- [Roadmap de produto, testes, atualização e monitoramento](docs/04_ROADMAP_PRODUTO_TESTES_ATUALIZACAO_MONITORAMENTO.md)
- [Política de atualização](docs/05_POLITICA_DE_ATUALIZACAO.md)
- [Status atual consolidado](docs/STATUS_ATUAL.md)
- [Template de evidências do Candidato A](docs/evidence/candidate-a/README.md)
- [Evolução MPV IPC/watchdog](docs/app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md)
- [Documentação consolidada](docs/DOCUMENTACAO_COMPLETA_TOTEM_ORANGEPI_ZERO3.md)

## Scripts de bancada

- `scripts/board/`: scripts para coleta de diagnóstico, snapshot de rede, stress leve, criação idempotente do layout `/data` (`config`, `media/kiosky-player`, `state/kiosky-player`, `spool/kiosky-player`, `logs/kiosky-player`) e desativação idempotente de Bluetooth.
- `scripts/remote/push_and_run.sh`: wrapper local para copiar um script de `scripts/board/` para a placa e executá-lo via SSH quando essa etapa for liberada.

## Regra operacional crítica

Não rodar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade` em campo. A base foi validada com kernel/DTB/U-Boot/BSP congelados. Atualizações devem seguir fluxo controlado por release.
