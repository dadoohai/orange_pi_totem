# C10.9.1 Second Board Provision

Data: 2026-05-05

Repo branch: `foundation-v0.1`

Repo base HEAD durante a rodada: `8b3f4baa12337f8a27b46a0dbe293b512a36a687`

Status: concluido. Evidencia sanitizada; host, senha, rede e identificadores
privados omitidos.

## Regras Confirmadas

- placa dev alterada: `false`
- clone de cartao/estado dev: `false`
- config real copiada da dev: `false`
- secrets publicados: `false`
- `private-values.json` copiado para evidencia: `false`
- config real publicada: `false`
- backup publicado: `false`
- SSID/senha/IP/MAC/DNS/gateway publicados: `false`
- writer chamado antes de confirmacao: `false`
- Wi-Fi/NetworkManager alterado pelo runner: `false`
- `apt upgrade/full-upgrade/dist-upgrade/armbian-upgrade`: `false`
- reboot executado: `false`

## Comandos

Local:

```bash
git status --short
git log --oneline -20
git diff --check
bash -n scripts/remote/run_c10_9_second_board_clean_install.sh
bash -n scripts/remote/run_c10_9_1_second_board_provision.sh
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_visual_setup_writer_handoff.py --self-test
```

C10.9.1:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --prepare-only
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --refresh-install
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --verify-config-missing-visual
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --run-f10-candidate-only-check
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --prepare-private-template
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --provision-real-config --private-values /tmp/dadooh-c10-9-1-private/private-values.json
scripts/remote/run_c10_9_1_second_board_provision.sh <second-board> --verify-player --private-values /tmp/dadooh-c10-9-1-private/private-values.json
```

Confirmacao humana usada:

```text
CONFIRMO PROVISIONAR CONFIG REAL C10.9.1 SEGUNDA PLACA
```

## Refresh do Manifest

- `install_refresh_done=true`
- `missing_file_fixed=true`
- `totem_status_render_preview.py` instalado em `/opt/totem/bin`
- `totem_open_settings_session.sh` atualizado
- `totem_visual_setup_writer_handoff.py` atualizado
- `totem_visual_splash.py` atualizado
- manifest instalado sanitizado atualizado
- `overall_status=ok`
- `systemctl_failed_count=0`
- config real criada durante refresh: `false`
- writer chamado durante refresh: `false`

## Config Missing Visual

- `config_real_present=false`
- `totem_status_render_preview_present=true`
- `status_aggregator_functional=true`
- `public_state=config_missing`
- `visual_message=config_pending`
- `stuck_starting_player=false`
- `config_missing_visual_ok=true`

## Candidate-only sem Config Ativa

- `visual_candidate_generated=true`
- `writer_called=false`
- `real_config_written=false`
- `public_state=config_missing`
- `visual_message=config_pending`
- `stuck_starting_player=false`
- `config_missing_visual_ok=true`
- `systemctl_failed_count=0`

Uma tentativa de provisionamento anterior foi abortada antes do writer porque o
wizard foi encerrado sem candidata. A limpeza segura removeu somente o lock de
sessao em `/run/dadooh-settings`, restaurou `kiosky-player.service` e manteve
`/data/config/config.json` ausente.

## Fonte Privada Temporaria

- private values path: `/tmp/dadooh-c10-9-1-private/private-values.json`
- directory mode: `0700`
- file mode: `0600`
- symlink refused: `true`
- `api_key_present=true`
- `api_key_placeholder=false`
- `api_url_present=true`
- `environment_id_source=wizard`
- values printed: `false`

O arquivo privado temporario foi usado apenas na segunda placa. O conteudo nao
foi copiado para evidencia e foi removido ao final do fluxo de provisionamento.

## Provisionamento Real

- `c5_real_dry_run=passed`
- `writer_called=true`
- `real_config_written=true`
- `backup_created=false`
- `permissions_ok=true`
- `config_mode=0640`
- owner/group esperado: `root:totem`
- usuario `totem` le: `true`
- usuario `totem` escreve: `false`
- `orientation_json_updated=true`
- `orientation_json_rotation_matches=true`
- `private_candidate_removed=true`
- `session_private_values_removed=true`
- `config_content_published=false`
- `credential_values_published=false`
- `environment_identifier_raw_published=false`

## Player Final

- `public_state=player_running`
- `playback=playing`
- `failure_category=none`
- `kiosk_process_count=1`
- `mpv_process_count=1`
- `renderer_process_count=0`
- `setup_process_count=0`
- `kiosky-player.service=active/enabled`
- `totem-settings-trigger.service=active/enabled`
- `totem-open-settings.service=inactive/static`
- `NRestarts=0`
- `systemctl_failed_count=0`

## Reboot Check

Reboot controlado executado apos confirmacao humana.

Resultado pos-boot:

- SSH voltou: `true`
- config real presente: `true`
- config mode: `0640`
- `permissions_ok=true`
- `public_state=player_running`
- `playback=playing`
- `failure_category=none`
- `kiosk_process_count=1`
- `mpv_process_count=1`
- `renderer_process_count=0`
- `setup_process_count=0`
- `kiosky-player.service=active/enabled`
- `totem-settings-trigger.service=active/enabled`
- `totem-open-settings.service=inactive/static`
- `dadooh-visual-splash.service=active/enabled`
- `NRestarts=0`
- `systemctl_failed_count=0`
- `kernel_critical_filter_count=0`
- raw logs collected: `false`
- secrets published: `false`

## Resultado

- `ready_for_c11_read_only_readiness_audit=true`
- `ready_for_image_final=false`

C10.9.1 valida a segunda placa com config real provisionada de forma
temporaria e controlada. Esse caminho ainda nao e o backend/login final e nao
deve embutir `api_key`, `api_url` ou `environment_id` em imagem.
