# C10.7 - Reprodutibilidade Placa Dev -> Repo

Data: 2026-05-05

Status: auditoria read-only executada na placa dev. Nao e instalador, nao e
imagem, nao toca segunda placa/cartao.

Atualizacao C10.7.1: refresh read-only pos-C10.6.2 executado em 2026-05-05.
O repo estava limpo em `1089f8253c5ed1854f0d997bf05f73c87e75dbcf`, contendo
`ede0fbc Add C10.6.2 F10 settings apply flow` e
`4d65f28 Add C10.7 reproducibility audit`. O refresh incorporou o delta
C10.6.2 na matriz de reprodutibilidade, sem rodar writer, sem alterar config
real, sem alterar Wi-Fi, sem rebootar e sem tocar na segunda placa.

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
/tmp/dadooh-c10-7-reproducibility-audit/20260505T153241Z-c10-7-1-refresh/
```

Evidencia C10.7.1:

```text
docs/evidence/candidate-a/runs/20260505T153241Z-c10-7-1-reproducibility-refresh/README.md
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
HEAD C10.7 original: ae6c658550c12bfa4684b9319091878c00f3e7b0
HEAD C10.7.1 refresh: 1089f8253c5ed1854f0d997bf05f73c87e75dbcf
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
- runner C10.6.2 para apply via F10
- runner de guardrails visuais
- runner de early boot quiet
- docs/evidencia C10.6.2 sanitizados

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

No refresh C10.7.1, os arquivos C10.6.2 estavam commitados e o repo estava
limpo. Persistiram dois pontos para C10.8:

- `kiosky_service_launcher.sh` instalado na placa ainda diverge do HEAD;
- `dadooh-visual-splash.service` segue sem unit standalone versionada.

## Delta pos-C10.6.2 incorporado

C10.6.2 acrescenta ao escopo de reprodutibilidade:

- `scripts/remote/run_c10_6_2_apply_settings_from_f10.sh`;
- `scripts/board/totem_setup_visual_wizard.py` atualizado;
- `scripts/board/totem_open_settings_session.sh` atualizado;
- `scripts/board/totem-open-settings.service` atualizado;
- contrato publico `/data/state/totem-display/orientation.json`;
- `totem-settings-trigger.service`;
- `totem-open-settings.service`;
- fluxo persistente F10 -> wizard -> handoff -> writer;
- handoff privado via `totem_visual_setup_writer_handoff.py`;
- writer real via `totem_config_writer_real.py`;
- splash/transicoes lendo `orientation.json`;
- politica one-shot em `/run/dadooh-settings/apply-policy.json`;
- limpeza de politica de apply apos consumo;
- `docs/product/84_C10_6_2_APLICAR_CONFIGURACOES_VIA_F10.md`;
- evidencia sanitizada em
  `docs/evidence/candidate-a/runs/20260505T141539Z-c10-6-2-apply-settings-from-f10/README.md`.

O refresh read-only confirmou na placa:

- `orientation.json` publico existe;
- `rotation_deg=270`;
- `orientation_label=portrait_left`;
- schema `dadooh-display-orientation.v1`;
- arquivo `orientation.json` em modo `0644`, `root:root`;
- scripts instalados esperados para wizard/session/handoff/writer/trigger/splash
  estao presentes em `/opt/totem/bin`;
- `totem-settings-trigger.service` esta `active/enabled`;
- `dadooh-visual-splash.service` esta `active/enabled`;
- `apply-policy.json` nao estava presente em `/run/dadooh-settings`.

O refresh tambem observou uma condicao transitoria na placa:

- `totem-open-settings.service=activating`;
- `kiosky-player.service=inactive/enabled`;
- processo de setup presente;
- status publico em `maintenance_placeholder`;
- playback publico ainda `playing` no arquivo do player.

Portanto, C10.7.1 incorpora o delta C10.6.2 para C10.8, mas nao deve ser usado
como prova de estado final `player_running` naquele minuto. Antes de iniciar
C10.8 na placa dev, fazer um preflight read-only curto para confirmar:

- `kiosky-player.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- sem `session.lock` em `/run/dadooh-settings`;
- sem processo de setup;
- `public_state=player_running`;
- playback `playing`.

Nao executar writer para esse preflight; apenas observar.

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
| Runner C10.6.2 apply via F10 | n/a | sim | parcial | nao | OK_VERSIONADO | C10.8 deve instalar as dependencias e preservar o runner como validacao/procedimento, nao como segredo. |
| Wizard visual atualizado C10.6.2 | sim | sim | sim | nao | OK_VERSIONADO | Instalar versao commitada em `/opt/totem/bin`. |
| Sessao F10/open-settings atualizada | sim | sim | sim | nao | OK_VERSIONADO | Instalar script e unit commitados. |
| Handoff privado setup -> writer | sim | sim | sim | nao | OK_VERSIONADO | Instalar script; nao persistir candidata privada. |
| Writer real guardado | sim | sim | sim | nao | OK_VERSIONADO | Instalar script; C10.8 nao deve chamar writer nem escrever config privada. |
| Contrato publico orientation.json | sim | sim | parcial | nao | OK_VERSIONADO | Criar/validar arquivo publico seguro ou preservar se ja existir; nao ler config real. |
| Politica one-shot em `/run/dadooh-settings` | sim | sim | parcial | nao | OK_VERSIONADO | C10.8 deve garantir diretorio runtime e limpeza de politica/request temporarios. |
| Evidencia sanitizada C10.6.2 | n/a | sim | n/a | nao | OK_VERSIONADO | Manter como evidencia; nao copiar artefatos privados. |
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
- instalar o fluxo F10 persistente e C10.6.2:
  `totem_settings_trigger.py`, `totem_open_settings_session.sh`,
  `totem_setup_visual_wizard.py`, `totem_visual_setup_writer_handoff.py`,
  `totem_config_writer_real.py`, `totem_visual_splash.py` e
  `totem_wifi_nm_adapter.py`;
- aplicar guardrails visuais de boot/shutdown/transicao;
- aplicar early boot quiet allowlisted em `/boot/armbianEnv.txt`;
- criar/validar `/data/state/totem-display/orientation.json` como contrato
  publico seguro, sem ler config real;
- garantir `/run/dadooh-settings` como runtime temporario e limpar
  `apply-policy.json`, requests e locks obsoletos antes/depois dos fluxos;
- instalar runtime minimo sem `apt upgrade`, `full-upgrade`,
  `dist-upgrade` ou `armbian-upgrade`;
- instalar ou atualizar `kiosky-player` em commit/ref fixado;
- aplicar permissoes finais;
- gerar manifest com hashes, units, pacotes e ref do player;
- nao instalar secrets;
- nao escrever config real privada;
- nao embutir SSID/senha;
- nao embutir `api_url`, `api_key`, `environment_id` ou `station_id`;
- nao embutir `orientation.json` privado; o arquivo e publico e deve conter
  somente campos allowlisted;
- nao copiar midias/cache/logs/estado runtime;
- nao copiar backups de config;
- nao chamar writer durante instalacao base;
- validar idempotencia rodando duas vezes;
- rodar smoke curto read-only de servicos/status depois da instalacao.

Validar na segunda placa/cartao, depois de C10.8:

- instalador idempotente roda duas vezes sem drift;
- services finais `active/enabled` onde aplicavel;
- F10 abre Configuracoes e cancela sem shell;
- dry-run F10 passa sem writer;
- escrita real so roda em etapa autorizada separada, nao no instalador base;
- `orientation.json` propaga para splash/transicoes;
- config real e Wi-Fi dedicado continuam provisionamento de campo;
- secrets, SSID, midias, cache, logs e backups nao entram na imagem.

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
scripts/remote/run_c10_7_reproducibility_audit.sh root@192.168.1.147 --summary --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T153241Z-c10-7-1-refresh
```

Nenhum comando de instalacao, upgrade, reboot, writer, alteracao de rede,
alteracao de player, read-only ou corte seco foi executado.
