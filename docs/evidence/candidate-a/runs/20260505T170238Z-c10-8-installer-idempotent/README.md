# C10.8 - Instalador Idempotente do Appliance

Data: 2026-05-05

Escopo: criar manifest, instalador, verificador e runner remoto para reproduzir
a camada do appliance a partir do repo.

## Regras

- segunda placa/cartao nao usado;
- imagem final nao gerada;
- apply na placa dev nao executado;
- config real nao alterada;
- conteudo da config real nao lido;
- writer nao chamado;
- Wi-Fi/NetworkManager nao alterados;
- pacotes nao instalados;
- sem `apt upgrade`, `full-upgrade`, `dist-upgrade` ou `armbian-upgrade`;
- player/kiosky-player nao alterado;
- reboot nao executado;
- secrets nao publicados.

## Repo

- branch: `foundation-v0.1`
- HEAD base durante os runners: `b97b0a77074765f8fd1c978ff9b833c20b6b6b7b`
- worktree copiado para `/tmp` ainda tinha `source_dirty_entries=5`, todos da
  implementacao C10.8 antes do commit.

## Comandos

```bash
git status --short
git log --oneline -20
git diff --check
bash -n scripts/remote/run_c10_7_reproducibility_audit.sh
python3 scripts/board/totem_settings_trigger.py --self-test
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
bash -n scripts/board/install_totem_appliance.sh
bash -n scripts/board/verify_totem_appliance.sh
bash -n scripts/remote/run_c10_8_installer_idempotent.sh
python3 -m json.tool scripts/board/totem_appliance_manifest.json
scripts/board/verify_totem_appliance.sh --self-test
scripts/board/install_totem_appliance.sh --manifest --out-dir /tmp/dadooh-c10-8-local-manifest-check
scripts/board/install_totem_appliance.sh --dry-run --out-dir /tmp/dadooh-c10-8-local-dry-run-check
scripts/board/install_totem_appliance.sh --idempotence-check --out-dir /tmp/dadooh-c10-8-local-idempotence-check
scripts/remote/run_c10_8_installer_idempotent.sh <host> --prepare-only
scripts/remote/run_c10_8_installer_idempotent.sh <host> --dry-run-dev
scripts/remote/run_c10_8_installer_idempotent.sh <host> --verify-dev
scripts/remote/run_c10_8_installer_idempotent.sh <host> --idempotence-dev-dry-run
```

## Artefatos Sanitizados em `/tmp`

- prepare-only:
  `/tmp/dadooh-c10-8-installer-idempotent/20260505T164645Z-c10-8-installer-idempotent`
- dry-run final:
  `/tmp/dadooh-c10-8-installer-idempotent/20260505T165918Z-c10-8-installer-idempotent`
- verify final:
  `/tmp/dadooh-c10-8-installer-idempotent/20260505T170057Z-c10-8-installer-idempotent`
- idempotence final:
  `/tmp/dadooh-c10-8-installer-idempotent/20260505T170238Z-c10-8-installer-idempotent`

Os artefatos copiados da placa ficam sob `remote/` nesses diretorios e contem
apenas JSON/texto sanitizado.

## Dry-run Dev

Resultado:

- `status=planned`;
- `repo_branch=foundation-v0.1`;
- `repo_head=b97b0a77074765f8fd1c978ff9b833c20b6b6b7b`;
- `repo_dirty_entries=5`;
- `action_count=7`;
- `changed_count=0`;
- `ready_for_second_board=false`;
- blocker: `kiosky_player_PIN_MISSING`.

Acoes planejadas:

- criar `/data/state/totem-appliance`;
- ajustar metadata de `/data/state/totem-display`;
- ajustar metadata de `/data/state/totem-boot-visual`;
- ajustar metadata de `/data/state/totem-settings`;
- reinstalar `/opt/totem/bin/kiosky_service_launcher.sh`;
- instalar `/opt/totem/bin/totem_wifi_local_credentials_tty.py`;
- escrever manifest instalado sanitizado.

## Verify Dev

Resultado:

- `overall_status=differences_found`;
- `ready_for_second_board=false`;
- `systemctl_failed_count=0`;
- `runtime_ok=true`;
- `user_ok=true`;
- `boot_guardrails_ok=true`;
- `orientation_ok=true`;
- `private_config_present_on_dev=true`;
- `private_config_content_read=false`;
- `kiosky_player_pin_status=PIN_MISSING`.

Blockers listados:

- `path:/data/state/totem-appliance`;
- `path:/data/state/totem-display`;
- `path:/data/state/totem-boot-visual`;
- `path:/data/state/totem-settings`;
- `script:/opt/totem/bin/kiosky_service_launcher.sh`;
- `script:/opt/totem/bin/totem_wifi_local_credentials_tty.py`;
- `kiosky_player_PIN_MISSING`.

## Idempotence Dev Dry-run

Resultado:

- `stable=true`;
- `first_action_count=7`;
- `second_action_count=7`;
- `ready_for_second_board=false`;
- blocker: `kiosky_player_PIN_MISSING`;
- `board_changed=false`.

## Conclusao

C10.8 criou o instalador e verificador idempotentes e comprovou que os modos
seguros funcionam. A segunda placa/cartao ainda nao deve comecar porque o pin
do `kiosky-player` segue ausente e a placa dev ainda tem diferencas que exigem
decisao ou apply refresh autorizado.
