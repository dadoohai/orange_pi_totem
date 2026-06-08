# Orange Pi Totem

Documentação técnica e operacional para construção, validação e evolução de uma imagem Armbian customizada para totens baseados em Orange Pi Zero 3.

## Estado C18 OTA

Baseline atual de laboratório/delivery: `c18-hwdecode-lab-1t` (C18 HW decode +
OTA `totem-core` validado end-to-end + fundação segura para thaw futuro de
`player-runtime`, com boot reconcile ordenado por `/data`, boot-state auditavel
e crash-boundary offline no caminho real de `player-runtime`). O OTA C18 comum é
manual/operator-triggered e restrito a
`totem-core`; `kiosky-player`, `player-runtime`, launcher do player,
MPV/hwdecode, display, kernel, systemd e updater ficam fora desse fluxo e
exigem imagem/homologação ou um pacote C18-aware explicitamente aprovado.

Evidencia hardware da golden atual:
`docs/evidence/c18-update-validation/20260605T093008Z-1t-coldboot-deep-health/`.
Ela promove a imagem `1t`, mas nao valida thaw publico de `player-runtime`,
adocao de release `/data`, power-loss fisico, auto-pull, stable/producao ou
soak.

Primeiro trial lab-only persistente de `player-runtime` em `/data`:
`docs/evidence/c18-update-validation/20260605T052805Z-1r-player-runtime-data-trial/`.
Ele prova apply local, adocao temporaria por marker/hash, deep-health com o
servico usando `/data`, rollback com quarentena e retorno ao fallback de
imagem. Ainda nao e thaw publico, GitHub publish, auto-pull, stable/producao,
cold-boot/power-loss nem rollback A->B entre duas releases de `/data`.

Trial lab-only A->B->A de `player-runtime` em `/data`:
`docs/evidence/c18-update-validation/20260605T060200Z-1r-player-runtime-data-aba-trial/`.
Ele prova uma release A ja ativa em `/data`, apply local da release B, adocao
real de B pelo servico, deep-health, rollback com quarentena de B e retorno para
A como `previous` real em `/data`. Ainda nao e thaw publico, GitHub publish,
auto-pull, stable/producao, cold-boot/power-loss ou soak.

M6 decisivo lab-only de `player-runtime` em `/data`:
`docs/evidence/c18-update-validation/20260608T011301Z-1t-player-runtime-m6-data-coldboot-trial/`.
Ele prova A->B->A em `/data` com reboot controlado, B adotada de
`/data/player-runtime/current`, marker verificado, deep-health do candidato B
apos cold-boot e rollback para A real em `/data`. O release gate atual aceita
essa evidencia em modo `decisive`. Ainda nao e thaw publico, GitHub publish,
auto-pull, stable/producao, power-loss fisico ou soak.

Fonte única do contrato: [docs/UPDATE_CONTRACT.md](docs/UPDATE_CONTRACT.md).
Guia curto de autorização e health gates:
[docs/UPDATE_AUTHORIZATION_HEALTH.md](docs/UPDATE_AUTHORIZATION_HEALTH.md).
Gate obrigatório antes de publicar/aceitar uma release OTA:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json
```

Esse gate deve falhar se o diff corrente tocar arquivos de `player-runtime` ou
player fixos por imagem. Nessa frente, a falha e intencional: a mudanca deixa de
ser OTA comum de `totem-core` e exige imagem/homologacao ou release C18-aware
separada.

## Estado historico pre-C18

**Candidato A**: Armbian Build v25.11 + Debian Bookworm Minimal + kernel `6.12.58-current-sunxi64` + U-Boot `2025.04`.

Status: aprovado em boot inicial, reboots curtos, baseline de rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, criação do layout `/data`, Wi-Fi cliente 5 GHz, desativação de `bluetooth.service`, desativação de `aw859a-bluetooth.service`, preparação inicial de usuário/diretórios para a aplicação, instalação controlada do runtime mínimo (`mpv`, `ffmpeg`, `python3-requests`), validação de pré-requisitos com `/tmp/kiosky` garantido e teste manual de MPV via DRM/KMS com confirmação visual. O `kiosky-player` já foi deployado em `/opt/totem/kiosky-player`, a config privada já foi criada em `/data/config/config.json` fora do Git, e o app já rodou manualmente como usuário `totem`, baixando mídias em `/data/media/kiosky-player`, criando estado em `/data/state/kiosky-player` e status em `/tmp/kiosky-status.json`.

Esta secao preserva o historico pre-C18/Candidato A. Ela nao e o baseline
vigente de delivery; para C18, usar a secao "Estado C18 OTA" acima e os docs
`UPDATE_CONTRACT.md`, `UPDATE_AUTHORIZATION_HEALTH.md` e
`189_C18_OTA_READINESS_GATE.md`.

O Candidato A ainda não está homologado para produção. A base do sistema operacional permanece saudável, com `systemctl --failed` em `0 loaded units listed` nas rodadas recentes e sem `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`. A fase app-MPV avançou: `mpv_query_uses_fresh_ipc=true` estabilizou IPC/watchdog/loadfile, e a saída MPV explícita `--vo=gpu --gpu-context=drm --ao=null` foi aprovada no app real por 300s na rodada `20260430-133130`, com todos os 5 aliases avançando `time-pos` e `estimated-frame-number`. Na placa de desenvolvimento, `systemd` start/stop, autoboot com HDMI conectado e launcher para HDMI ausente/reconexão também foram aprovados. Xorg, Wayland, compositor, Chromium, `pip` e venv continuam fora desta fase.

Na frente produto/UX, a Fase A foi concluida em desenvolvimento e B1 refinou a
tela publica Dadooh para `config_missing`: "Configuracao pendente" foi validada
por observacao humana na placa de desenvolvimento. Wi-Fi setup, hotspot, QR
code, portal local e onboarding ainda nao foram implementados.

Atualizacao de desenvolvimento: alem do marco status/splash B1, a frente C6
validou config real + `player_running` na placa de desenvolvimento. C6.3A
escreveu `/data/config/config.json` com servico parado, backup restrito e
permissoes `root:totem` `0640`; C6.4 iniciou o servico controladamente e passou
em observer curto de 120s com `player_running`, playback `playing`, MPV ativo e
`NRestarts=0`. Testes longos e homologacao continuam pendentes, e producao
permanece bloqueada.

Pendências atuais antes de produção:

- `pip` ausente e `/opt/totem/venv` ainda sem Python/pip executáveis, por decisão desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase.
- Homologar a versão `v0.1-rc1` em uma segunda placa/cartão.
- Rodar teste manual observado de 30 a 60 minutos com a configuração candidata.
- Repetir a validação de `systemd`/autoboot/HDMI ausente na placa de homologação antes de produção.
- Teste longo ainda não liberado.
- Root read-only ainda não validado.
- Corte seco ainda não validado.

Próximo passo técnico: manter duas frentes separadas. A homologação `v0.1-rc1` segue em segunda placa/cartão; a evolução de produto/UX segue sem alterar a configuração candidata da RC1.

## Marco atual de desenvolvimento

O marco status/splash B1 esta documentado em
[docs/product/11_MARCO_DESENVOLVIMENTO_STATUS_SPLASH.md](docs/product/11_MARCO_DESENVOLVIMENTO_STATUS_SPLASH.md).
Ele consolida `systemd`, launcher, status aggregator, `config_missing` e a tela
Dadooh B1 como desenvolvimento pos-RC1.

O marco C6 config real + `player_running` esta documentado em
[docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md](docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md).
Ele consolida C6.3A/C6.4 como desenvolvimento, nao homologacao e nao producao.

A RC1 continua sendo homologacao separada:
[docs/releases/v0.1-rc1-homologacao/README.md](docs/releases/v0.1-rc1-homologacao/README.md).
Status/splash B1 e C6 config real + `player_running` nao liberam producao;
producao permanece bloqueada ate novas validacoes.

## Próxima fase: produto/UX

C0/C1/C2/C3/C4/C5/C6 evoluiram como frente produto/UX depois da RC1. C0 fica
preservado como planejamento historico, mas nao deve ser lido isoladamente como
a proxima fase atual. Proximos desenvolvimentos devem ser escolhidos a partir
do roadmap produto/UX atual, do status consolidado e do marco C6.5, sem misturar
desenvolvimento com homologacao.

Testes longos ficam em fila de homologacao separada:
[docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md](docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md).

Estratégia: [docs/product/01_ESTRATEGIA_PRODUTO_UX.md](docs/product/01_ESTRATEGIA_PRODUTO_UX.md)

Planejamento C0: [docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md](docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md)

Esta frente é separada da RC1/homologação. A RC1 continua dedicada a reproduzir a base técnica validada em outra placa/cartão antes de qualquer produção.

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
- [Contrato C18 de atualização](docs/UPDATE_CONTRACT.md)
- [Autorização C18 de update e health gates](docs/UPDATE_AUTHORIZATION_HEALTH.md)
- [Diagnóstico operacional e incidentes de campo](docs/OPERATIONS_DIAGNOSTICS.md)
- [Readiness C18 OTA](docs/product/189_C18_OTA_READINESS_GATE.md)
- [Modelo operacional C18 OTA](docs/product/191_C18_OTA_OPERATING_MODEL.md)
- [Continuidade C18 historica](docs/product/188_C18_STATUS_E_CONTINUIDADE.md)
- [Status atual consolidado](docs/STATUS_ATUAL.md)
- [Estratégia produto/UX](docs/product/01_ESTRATEGIA_PRODUTO_UX.md)
- [Roadmap implementação produto/UX](docs/product/02_ROADMAP_IMPLEMENTACAO_PRODUTO.md)
- [Conclusão da Fase A status/splash](docs/product/08_FASE_A_CONCLUSAO.md)
- [Planejamento Fase B status visual e manutenção mínima](docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md)
- [Marco desenvolvimento status/splash](docs/product/11_MARCO_DESENVOLVIMENTO_STATUS_SPLASH.md)
- [Marco C6 config real + player_running](docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md)
- [Fila de homologação e testes longos](docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md)
- [Planejamento C0 onboarding Wi-Fi/configuração](docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md)
- [Riscos onboarding Wi-Fi/configuração](docs/product/13_RISCOS_ONBOARDING_WIFI_CONFIG.md)
- [Homologação v0.1-rc1](docs/releases/v0.1-rc1-homologacao/README.md)
- [Template de evidências do Candidato A](docs/evidence/candidate-a/README.md)
- [Evolução MPV IPC/watchdog](docs/app-integration/04_EVOLUCAO_MPV_IPC_WATCHDOG.md)
- [Estado atual do player MPV](docs/app-integration/05_ESTADO_ATUAL_PLAYER_MPV.md)
- [ADR-0004 runtime MPV do kiosky-player](docs/DECISIONS/ADR-0004-kiosky-player-mpv-runtime.md)
- [ADR-0007 launcher, status agregado e splash Dadooh](docs/DECISIONS/ADR-0007-status-splash-launcher.md)
- [ADR-0008 onboarding Wi-Fi/configuração](docs/DECISIONS/ADR-0008-onboarding-wifi-config.md)
- [ADR-0009 configuração mínima por environment_id](docs/DECISIONS/ADR-0009-minimal-config-environment-id.md)
- [ADR-0010 provisionamento de token/API](docs/DECISIONS/ADR-0010-api-token-provisioning.md)
- [Documentação consolidada](docs/DOCUMENTACAO_COMPLETA_TOTEM_ORANGEPI_ZERO3.md)

## Scripts de bancada

- `scripts/board/`: scripts para coleta de diagnóstico, snapshot de rede, stress leve, criação idempotente do layout `/data` (`config`, `media/kiosky-player`, `state/kiosky-player`, `spool/kiosky-player`, `logs/kiosky-player`) e desativação idempotente de Bluetooth.
- `scripts/remote/push_and_run.sh`: helper de bancada/lab para copiar e executar scripts via SSH. Ele bypassa o contrato C18 e não é caminho de update em campo.

## Regra operacional crítica

Não rodar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade` em campo. A base foi validada com kernel/DTB/U-Boot/BSP congelados. Atualizações de player/core devem seguir [docs/UPDATE_CONTRACT.md](docs/UPDATE_CONTRACT.md); documentos C14/C15/C17 e scripts remotos são históricos/lab quando divergirem desse contrato.
