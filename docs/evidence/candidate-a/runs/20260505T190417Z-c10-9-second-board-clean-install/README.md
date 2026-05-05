# C10.9 Second Board Clean Install

Data: 2026-05-05

Repo branch: `foundation-v0.1`

Repo base HEAD durante a rodada: `cecafbf8f1d0541a3f912a99adfbae857cd6ce48`

Status: concluido. Evidencia sanitizada; host, senha, rede e identificadores
privados omitidos.

## Regras Confirmadas

- placa dev alterada: `false`
- clone de cartao/estado dev: `false`
- config real copiada/criada: `false`
- secrets publicados: `false`
- SSID/senha/IP/MAC/DNS/gateway publicados: `false`
- writer chamado: `false`
- Wi-Fi/NetworkManager alterado: `false`
- reboot sem confirmacao: `false`
- `apt upgrade/full-upgrade/dist-upgrade/armbian-upgrade`: `false`

## Comandos Executados

Local:

```bash
git status --short
git log --oneline -20
git diff --check
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
bash -n scripts/remote/run_c10_8_installer_idempotent.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json
```

C10.9:

```bash
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --prepare-only
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --inspect-base
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --install-dry-run
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --install-apply --install-runtime
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --verify
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --idempotence-check
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --config-missing-check
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --reboot-check
scripts/remote/run_c10_9_second_board_clean_install.sh <second-board> --f10-check
```

Confirmacoes humanas usadas:

```text
CONFIRMO INSTALAR APPLIANCE C10.9 NA SEGUNDA PLACA
CONFIRMO REBOOT C10.9 SEGUNDA PLACA
CONFIRMO F10 CHECK C10.9 SEGUNDA PLACA
```

## Inspect Base

- `base_compatible=true`
- `base_drift_from_dev=false`
- NetworkManager presente
- runtime ausente antes do apply: `mpv`, `ffmpeg`, `python3-requests`
- usuario/grupo `totem` ausentes antes do apply
- `/opt/totem` e `/data` ausentes antes do apply
- desktop/Chromium/Xorg/Wayland/compositor nao detectados como runtime
  proibido pelo verificador

## Dry-run Inicial

- `action_count=53`
- blockers esperados: runtime ausente (`mpv`, `ffmpeg`,
  `python3-requests`)
- `kiosky-player` ausente e `deploy_required=true`
- nenhuma mudanca aplicada

## Apply

- `status=applied`
- `changed_count=53`
- runtime instalado com `apt-get install --no-install-recommends` para pacotes
  explicitos do manifest
- `0 pacotes atualizados`
- `kiosky-player` instalado de archive do commit pinado
- config real criada: `false`
- writer chamado: `false`
- Wi-Fi/NetworkManager alterado: `false`

Pin do app:

- repo: `dadoohai/kiosky-player`
- ref: `appliance-v0.1`
- commit: `c71318a64c08e47b8426f1388b95f21364d57123`
- verificacao final: `installed_marker`

## Reboot Check

Resultado:

- SSH voltou
- `overall_status=ok`
- `ready_for_second_board=true`
- `systemctl_failed_count=0`
- `runtime_ok=true`
- `user_ok=true`
- `boot_guardrails_ok=true`
- `orientation_ok=true`
- `private_config_present=false`
- `private_config_content_read=false`
- `kiosky_player_verification_level=installed_marker`
- blockers: none

Servicos:

- `kiosky-player.service=active/enabled`
- `totem-settings-trigger.service=active/enabled`
- `totem-open-settings.service=inactive/static`
- `dadooh-visual-splash.service=active/enabled`

## Idempotencia Final

- `stable=true`
- `first_action_count=0`
- `second_action_count=0`
- `board_changed=false`
- blockers: none

## Config Missing

- `config_real_present=false`
- `public_state=config_missing`
- `config_missing_safe=true`
- `setup_process_count=0`
- `mpv_process_count=0`
- `systemctl_failed_count=0`

## F10

Primeira tentativa:

- F10 nao completou visualmente;
- estado runtime ficou sujo com `session.lock`;
- limpeza segura removeu apenas a sessao de configuracao em
  `/run/dadooh-settings` e resetou a unit one-shot.

Correcao aplicada:

- `totem_open_settings_session.sh` passa a degradar de `real-write` com
  `active-config` para `candidate-only` quando a config real ainda nao existe;
- `wait_player_running` nao bloqueia em placa sem config real.

Tentativa final:

- `opened=true`
- `closed_after_open=true`
- `session_lock_present_after=false`
- `request_present_after=false`
- `writer_called_by_runner=false`
- `config_content_read=false`
- `passed=true`

## Observacao Posterior

Apos a evidencia inicial, o humano executou novo fluxo de Configuracoes e
salvou orientacao, Wi-Fi e ambiente. A placa permaneceu visualmente em
"iniciando player".

Inspecao segura posterior, sem ler config privada e sem alterar Wi-Fi, writer
ou servicos, classificou:

- `/data/config/config.json` presente: `false`
- ultimo fluxo F10: `candidate-only`
- writer chamado: `false`
- config real escrita: `false`
- launcher state: `config_missing`
- processos reais `mpv`/player/wizard: `0`
- `systemctl_failed_count=0`
- dependencia do agregador ausente:
  `/opt/totem/bin/totem_status_render_preview.py`

Interpretacao: o problema imediato nao foi endpoint/chave invalida em uso; a
placa nao tinha config ativa. Alem disso, a falta da dependencia do agregador
impediu feedback visual publico de `config_missing`, deixando a ultima tela de
splash congelada.

## Resultado

- `ready_for_c11_read_only_readiness_audit=false`
- `ready_for_c10_9=true`
- `ready_for_image_final=false`

C10.9 valida a instalacao limpa da camada appliance em segunda placa. Imagem
final, root read-only, provisionamento real de config e player real com config
privada ficam fora desta rodada. C10.9.1 deve aplicar o refresh do manifest para
o status visual e validar provisionamento controlado da config mock real antes
de C11.0.
