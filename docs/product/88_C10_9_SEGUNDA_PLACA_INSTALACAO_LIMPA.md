# C10.9 - Segunda Placa por Instalacao Limpa

Data: 2026-05-05

Status: instalacao limpa executada na segunda placa/cartao; follow-up
obrigatorio aberto antes de C11.0. A placa dev nao foi alterada.

## Objetivo

Validar que uma segunda placa com Armbian base limpa vira o appliance Dadooh
usando somente o repo, o instalador idempotente e o pin do `kiosky-player`, sem
clonar estado da placa dev.

## Bootstrap Manual de Bancada

Antes de C10.9, o humano ja havia feito apenas o bootstrap tecnico minimo:

- senha inicial de `root`;
- rede/SSH;
- comunicacao do endereco de acesso ao operador.

Esse fluxo nao e experiencia final de produto. A imagem final C12.0 deve
eliminar esse bootstrap tecnico.

## Instalado por Script

O runner criado foi:

```bash
scripts/remote/run_c10_9_second_board_clean_install.sh
```

Modos implementados:

- `--prepare-only`
- `--inspect-base`
- `--install-dry-run`
- `--install-apply`
- `--verify`
- `--idempotence-check`
- `--config-missing-check`
- `--f10-check`
- `--reboot-check`
- `--provision-real-config`

O apply instalou:

- usuario/grupo `totem`;
- grupos opcionais `audio`, `video`, `render`;
- layout `/opt/totem`, `/opt/totem/bin` e `/data`;
- scripts board versionados;
- units systemd versionadas;
- guardrails visuais de boot;
- `orientation.json` publico seguro;
- manifest instalado sanitizado;
- runtime minimo explicito: `mpv`, `ffmpeg`, `python3-requests`;
- `kiosky-player` a partir do pin do manifest.

O runtime foi instalado com `apt-get install --no-install-recommends` para
pacotes explicitos. Nao houve `apt upgrade`, `full-upgrade`,
`dist-upgrade` ou `armbian-upgrade`.

## Kiosky-player

Pin usado:

- repo: `dadoohai/kiosky-player`;
- ref: `appliance-v0.1`;
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`;
- install path: `/opt/totem/kiosky-player`.

O runner gerou um `git archive` local desse commit e instalou somente a arvore
do app. Metadados `.git`, config privada, `.env`, arquivos com nome de segredo
e cache de midia foram excluidos/recusados. A verificacao final usa marcador
sanitizado em `/data/state/totem-appliance/kiosky-player-installed.json`, com
`verification_level=installed_marker`.

## Nao Copiado da Placa Dev

Nao foi copiado da placa dev:

- config real;
- secrets;
- SSID/senha;
- IP/MAC/DNS/gateway;
- hostname;
- midias/cache;
- logs brutos;
- backups;
- payloads privados;
- estado runtime de player/setup.

Tambem nao houve writer, provisionamento real de config, alteracao de Wi-Fi ou
uso de imagem clonada.

## Resultados

Inspect base:

- `base_compatible=true`;
- `base_drift_from_dev=false`;
- NetworkManager presente;
- runtime inicialmente ausente: `mpv`, `ffmpeg`, `python3-requests`;
- `/opt/totem` e `/data` inicialmente ausentes;
- usuario/grupo `totem` inicialmente ausentes.

Apply:

- `status=applied`;
- runtime minimo instalado;
- `kiosky-player` pinado instalado;
- config real nao criada;
- writer nao chamado;
- Wi-Fi/NetworkManager nao alterado;
- reboot nao chamado no apply.

Reboot controlado:

- SSH voltou;
- `verify` pos-boot: `overall_status=ok`;
- `systemctl_failed_count=0`;
- runtime ok;
- boot guardrails ok;
- orientation ok;
- config real ausente e conteudo nao lido;
- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `dadooh-visual-splash.service=active/enabled`.

Idempotencia final:

- `stable=true`;
- `first_action_count=0`;
- `second_action_count=0`;
- `blockers: none`.

Config ausente:

- `config_real_present=false`;
- `public_state=config_missing`;
- `config_missing_safe=true`;
- `setup_process_count=0`;
- `mpv_process_count=0`;
- `systemctl_failed_count=0`.

F10:

- primeira tentativa encontrou bug em placa limpa: a unit chamava a sessao em
  modo `real-write` com fonte `active-config`, mas nao havia config real.
- o script `totem_open_settings_session.sh` foi corrigido para degradar para
  `candidate-only` quando `/data/config/config.json` nao existe;
- o refresh aplicou somente esse script versionado;
- tentativa final: `opened=true`, `closed_after_open=true`,
  `session_lock_present_after=false`, `request_present_after=false`,
  `passed=true`.

## Estado Final

- appliance instalado por script;
- nada clonado da placa dev;
- sem config real;
- sem secrets;
- verify final ok;
- idempotencia final estavel;
- config_missing seguro;
- F10 abre Configuracoes e cancela limpo;
- reboot controlado passou;
- `systemctl_failed_count=0`.

## Observacao Pos-Instalacao

Apos a rodada, o humano abriu novamente Configuracoes, salvou orientacao,
Wi-Fi e ambiente, e a placa permaneceu visualmente em "iniciando player".
Inspecao segura posterior mostrou:

- `/data/config/config.json` continuava ausente;
- o fluxo F10 em placa limpa gerou candidato, mas permaneceu em
  `candidate-only`;
- `writer_called=false` e `real_config_written=false`;
- launcher em `config_missing`;
- sem processos reais de player/MPV/wizard em execucao;
- `systemctl_failed_count=0`;
- o agregador de status falhava por dependencia nao instalada:
  `totem_status_render_preview.py` ausente em `/opt/totem/bin`.

Conclusao: C10.9 validou a instalacao da camada appliance, mas ainda nao valida
ativacao por config real nem feedback visual correto depois de "Salvar" em
placa limpa.

## Pronto para C11.0

C10.9 isoladamente nao deveria avancar para C11.0 read-only readiness audit sem
uma rodada curta C10.9.1.

## Resolucao em C10.9.1

C10.9.1 concluiu o follow-up:

- refresh instalou `totem_status_render_preview.py`;
- `config_missing` passou a gerar feedback visual `config_pending`;
- `candidate-only` sem config ativa nao chama writer e nao fica em
  "Iniciando player";
- provisionamento real controlado usou arquivo privado restrito em `/tmp`;
- C5.1 real-dry-run passou;
- writer real escreveu `/data/config/config.json`;
- permissoes ficaram `root:totem 0640`;
- temporarios privados foram removidos;
- player final ficou `public_state=player_running` e `playback=playing`;
- reboot controlado pos-provisionamento passou com config presente,
  `public_state=player_running`, `playback=playing`, `systemctl_failed_count=0`
  e `kernel_critical_filter_count=0`;
- `systemctl_failed_count=0`.

Com C10.9.1, a segunda placa fica pronta para C11.0 read-only readiness audit.

Pendencias que permanecem fora de C10.9/C10.9.1:

- transformar o bootstrap tecnico inicial em experiencia final de imagem;
- auditar read-only/root overlay;
- gerar imagem final;
- validar estrategia de artefato local/offline para `kiosky-player` se a
  producao nao puder depender de checkout local ou rede.
