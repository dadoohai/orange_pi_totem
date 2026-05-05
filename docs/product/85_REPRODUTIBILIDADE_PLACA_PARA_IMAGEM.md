# C10.7 - Reprodutibilidade Placa Dev -> Repo

Data: 2026-05-05

Status: auditoria read-only executada na placa dev. Nao e instalador, nao e
imagem, nao toca segunda placa/cartao.

## Pergunta

O estado atual validado na placa dev esta totalmente descrito/versionado no
repo?

Resposta: nao.

A placa dev esta operacional e a maior parte dos componentes de produto esta
descrita no repo, mas ainda nao existe um instalador idempotente unico que
reproduza a placa em outro cartao. A auditoria tambem encontrou drift entre
placa, HEAD commitado e worktree local.

## Runner

Foi criado:

```bash
scripts/remote/run_c10_7_reproducibility_audit.sh
```

Modos:

- `--prepare-only`
- `--audit-board`
- `--audit-repo`
- `--compare`
- `--summary`

O runner exige host como argumento e coleta somente categorias, booleanos,
hashes de arquivos allowlisted e metadados sanitizados. Ele nao para servico,
nao altera config, nao chama writer, nao altera rede, nao instala pacotes, nao
executa `apt`, nao reboota e nao coleta logs brutos.

Artefatos sanitizados:

```text
/tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z/
```

## Snapshot da Placa

- board/modelo: `OrangePi Zero3`
- Armbian: `25.11.1`, board `orangepizero3`, branch `current`
- Debian: `bookworm`
- kernel: `6.12.58-current-sunxi64`
- `systemctl --failed`: `0`
- runtime presente: `mpv`, `ffmpeg`, `python3-requests`, `network-manager`
- desktop/Chromium/Xorg/Wayland/compositor: nao detectados
- usuario/grupo `totem`: presentes
- grupos `totem`: `totem`, `audio`, `video`, `render`
- `kiosky-player.service`: `active/enabled`
- `totem-settings-trigger.service`: `active/enabled`
- `totem-open-settings.service`: `inactive/static`
- `dadooh-visual-splash.service`: `active/enabled`
- playback publico: `playing`
- processos: player `1`, MPV `1`, renderer `0`, setup `0`
- Wi-Fi dedicado persistente: presente, sem publicar SSID/rede
- config real: presente, `root:totem` `0640`, usuario `totem` le e nao escreve
- boot quiet guardrails: aplicados
- gettys de produto observados: `tty1` e `tty2` inativos/desabilitados

Observacao: `/data/state/totem-display` nao existia no snapshot. C10.8 deve
decidir se cria um `orientation.json` publico padrao ou se ausencia segue como
estado valido ate o primeiro fluxo de configuracao.

## Snapshot do Repo

```text
branch: foundation-v0.1
HEAD: ae6c658550c12bfa4684b9319091878c00f3e7b0
```

Inventario versionado:

- `scripts/board`: 60 arquivos
- `scripts/remote`: 29 arquivos
- systemd units versionadas: 3
- docs produto: 98 arquivos
- docs release/homologacao: 3 arquivos
- exemplos de config: 1

Capacidades presentes:

- setup de usuario/grupo `totem`
- setup de layout `/data`
- setup de diretorios de app
- check de prerequisitos runtime
- deploy do `kiosky-player`
- runner de trigger persistente F10
- runner de guardrails visuais
- runner de early boot quiet

Capacidades ausentes:

- instalador idempotente unico do appliance
- manifest/ref fixado do `kiosky-player`
- unit standalone versionada para `dadooh-visual-splash.service`

## Drift Encontrado

- `/opt/totem/bin/kiosky_service_launcher.sh`: difere do HEAD e tambem do
  worktree local; possivel drift real da placa.
- `/opt/totem/bin/totem_open_settings_session.sh`: bate com worktree sujo, mas
  nao com HEAD.
- `/opt/totem/bin/totem_setup_visual_wizard.py`: bate com worktree sujo, mas
  nao com HEAD.
- `/etc/systemd/system/totem-open-settings.service`: bate com worktree sujo,
  mas nao com HEAD.
- `/opt/totem/bin/totem_wifi_local_credentials_tty.py`: existe no repo, mas nao
  foi encontrado em `/opt/totem/bin`.
- `/etc/systemd/system/dadooh-visual-splash.service`: existe e esta ativo na
  placa, mas nao existe como `.service` standalone versionado.

## Tabela Placa vs Repo

| Item | Presente na placa | Presente no repo | Reproduzivel por script hoje | Privado/nao entra na imagem | Classificacao | Acao necessaria |
| --- | --- | --- | --- | --- | --- | --- |
| Base OS Armbian/Debian minimal e kernel | sim | sim | nao | nao | FALTA_SCRIPT_INSTALACAO | C10.8 deve transformar a fundacao documentada em instalador/manifest verificavel. |
| Runtime minimo mpv/ffmpeg/python3-requests/NetworkManager | sim | sim | nao | nao | FALTA_SCRIPT_INSTALACAO | Falta instalacao idempotente sem `apt upgrade`. |
| Ausencia de desktop/Chromium/Xorg/Wayland/compositor | sim | sim | nao | nao | FALTA_SCRIPT_INSTALACAO | C10.8 deve validar ausencia e impedir instalacao de camada grafica. |
| Usuario e grupo totem | sim | sim | sim | nao | OK_VERSIONADO | Consolidar no instalador idempotente. |
| Layout /data config/media/state/logs | sim | sim | sim | nao | OK_VERSIONADO | Consolidar permissoes finais no instalador. |
| /opt/totem/bin scripts allowlisted | 13/14 | sim | nao | nao | POSSIVEL_DRIFT_PLACA | Resolver drift antes da segunda placa. |
| Systemd kiosky-player.service | sim | sim | sim | nao | OK_VERSIONADO | Unit bate com HEAD. |
| Systemd totem-settings-trigger.service | sim | sim | sim | nao | OK_VERSIONADO | Unit bate com HEAD. |
| Systemd totem-open-settings.service | sim | sim | nao | nao | POSSIVEL_DRIFT_PLACA | Bate com worktree sujo, nao com HEAD. |
| Systemd dadooh-visual-splash.service | sim | nao | nao | nao | FALTA_SCRIPT_INSTALACAO | Versionar ou gerar deterministicamente no C10.8. |
| Trigger F10 persistente | sim | sim | sim | nao | OK_VERSIONADO | Incluir instalacao/habilitacao no C10.8. |
| Guardrails visuais boot/shutdown/transicao | sim | sim | sim | nao | OK_VERSIONADO | Transformar runner reversivel em etapa idempotente. |
| Early boot quiet em `/boot/armbianEnv.txt` | sim | sim | sim | nao | OK_VERSIONADO | Aplicar/validar flags allowlisted no instalador. |
| Wi-Fi dedicado persistente | sim | sim | nao | sim | ESTADO_PRIVADO_NAO_IMAGEM | Provisionamento de campo/local; nao entra na imagem. |
| Config real `/data/config/config.json` | sim | sim | nao | sim | ESTADO_PRIVADO_NAO_IMAGEM | Nao entra na imagem; usar writer protegido. |
| Secrets | nao | sim | nao | sim | NAO_DEVE_ENTRAR_IMAGEM | Manter fora de repo, imagem e artefatos. |
| Midias/cache em `/data/media` | sim | sim | nao | sim | ESTADO_PRIVADO_NAO_IMAGEM | Nao clonar midias; sincronizar em runtime. |
| Estado/logs runtime | sim | sim | nao | sim | ESTADO_TEMPORARIO | Criar diretorios; nao copiar conteudo runtime/logs. |
| `kiosky-player` em `/opt/totem/kiosky-player` | sim | sim | nao | nao | FALTA_SCRIPT_INSTALACAO | Deploy existe, mas falta pin/manifest. |
| Commit/ref fixado do `kiosky-player` | nao | nao | nao | nao | FALTA_SCRIPT_INSTALACAO | Registrar origem e ref exatos. |
| Player public_state/playback apos reboot | sim | sim | nao | nao | ESTADO_TEMPORARIO | Validar por smoke curto no C10.8; nao copiar status runtime. |
| `/data/state/totem-display/orientation.json` | nao | sim | parcial | nao | PRECISA_DECISAO | Definir default publico ou aceitar ausencia ate configuracao. |
| Read-only/root overlay e corte seco | nao | nao | nao | nao | NAO_DEVE_ENTRAR_IMAGEM | Fora desta rodada. |
| Instalador idempotente unico do appliance | nao | nao | nao | nao | FALTA_SCRIPT_INSTALACAO | Escopo direto de C10.8. |

## Respostas Diretas

Os scripts em `/opt/totem/bin` vieram do repo?

Parcialmente. A maioria bate com HEAD. `kiosky_service_launcher.sh` parece
drift real da placa; `totem_open_settings_session.sh` e
`totem_setup_visual_wizard.py` batem com worktree sujo, nao com commit.

As units systemd instaladas existem no repo?

Parcialmente. Tres units existem no repo. `totem-open-settings.service` bate
com worktree sujo, nao com HEAD. `dadooh-visual-splash.service` esta na placa,
mas nao existe como unit standalone versionada.

Os guardrails de boot estao documentados e scriptaveis?

Sim, por C10.5.2/C10.5.3, mas C10.8 deve transformar runner de bancada em etapa
idempotente.

O trigger F10 persistente e reproduzivel?

Sim em termos de scripts/units versionados e estado da placa. Deve entrar no
C10.8 como instalacao/habilitacao idempotente.

O layout `/data` e reproduzivel?

Parcialmente sim. Existem scripts, mas o instalador final ainda precisa unificar
layout, ownership e modes finais.

As permissoes `root:totem` `0640` da config real sao reproduziveis?

A politica esta descrita e o writer aplica metadados, mas a config real e
privada e nao entra na imagem. C10.8 deve criar diretorios e validar a regra.

O `kiosky-player` esta fixado em commit/ref?

Nao de forma verificavel. A placa tem app em `/opt/totem/kiosky-player`, mas
sem metadata Git no diretorio.

O Wi-Fi dedicado, config real e secrets entram na imagem?

Nao. Wi-Fi dedicado e config real sao provisionamento de campo/bancada. Secrets
ficam fora de repo, imagem e artefatos.

## Conclusao

Ainda nao da para preparar a segunda placa/cartao por script com garantia de
reproducibilidade completa.

Antes disso, e necessario executar C10.8 para criar instalador idempotente,
resolver drift de scripts/units, fixar origem/ref do `kiosky-player`, separar
estados privados/temporarios e gerar manifest verificavel.

## C10.8 Recomendado

C10.8 - Instalador idempotente do appliance.

Escopo proposto:

- criar usuario/grupo `totem`;
- garantir grupos `audio`, `video`, `render`;
- criar layout `/data`;
- instalar `/opt/totem`;
- instalar scripts de `scripts/board` em `/opt/totem/bin`;
- instalar services systemd versionados;
- habilitar services necessarios;
- aplicar guardrails visuais de boot/shutdown/transicao;
- aplicar early boot quiet allowlisted em `/boot/armbianEnv.txt`;
- instalar runtime minimo sem `apt upgrade`, `full-upgrade`,
  `dist-upgrade` ou `armbian-upgrade`;
- instalar ou atualizar `kiosky-player` em commit/ref fixado;
- aplicar permissoes finais;
- gerar manifest com hashes, units, pacotes e ref do player;
- nao instalar secrets;
- nao escrever config real privada;
- nao embutir SSID/senha;
- nao copiar midias/cache/logs/estado runtime;
- validar idempotencia rodando duas vezes;
- rodar smoke curto read-only de servicos/status depois da instalacao.

## Comandos Executados

```bash
git status --short
git log --oneline -15
git diff --check
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
rg --files scripts/board
rg --files scripts/remote
bash -n scripts/remote/run_c10_7_reproducibility_audit.sh
scripts/remote/run_c10_7_reproducibility_audit.sh root@192.168.1.147 --summary --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
scripts/remote/run_c10_7_reproducibility_audit.sh --audit-repo --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
scripts/remote/run_c10_7_reproducibility_audit.sh --compare --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
```

Nenhum comando de instalacao, upgrade, reboot, writer, alteracao de rede,
alteracao de player, read-only ou corte seco foi executado.
