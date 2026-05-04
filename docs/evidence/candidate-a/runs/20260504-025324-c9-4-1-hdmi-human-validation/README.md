# C9.4.1 - HDMI human validation

Data: 2026-05-04

Commit: `26ac589 Add C9.4 local setup product v0`

## Comandos executados

```text
git status --short
git log --oneline -5
git diff --check
bash -n scripts/board/kiosky_service_launcher.sh
bash -n scripts/remote/run_c9_4_setup_product_v0_experiment.sh
python3 scripts/board/totem_setup_local_wizard.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --run-cancel --timeout-sec 240
scripts/remote/run_c9_4_setup_product_v0_experiment.sh root@192.168.18.115 --run-complete-scripted --timeout-sec 240
```

## Resultado cancelamento

Aprovado apos ajuste estreito.

Durante a primeira tentativa com humano ausente, o runner foi interrompido pelo
operador remoto e o servico foi restaurado manualmente. Com humano presente,
uma segunda tentativa mostrou que o cancelamento chegava como
`setup_local_failed`; a causa provavel era perda do exit code pelo `openvt`.
Foi adicionado marcador sanitizado de cancelamento em `/tmp`, sem candidata.

Resultado final:

```text
runner_result: ok (cancelled)
service_active: active
service_enabled: enabled
NRestarts: 0
player: 1
mpv: 1
renderer: 0
setup: 0
public_state: player_running
playback_state: playing
```

## Resultado conclusao

Aprovado no modo `--run-complete-scripted`.

```text
result: passed
wizard_result: candidate_ready
candidate_generated: true
service_active_after: active
service_enabled_after: enabled
NRestarts: 0
public_status_after: player_running
playback_state: playing
mpv_running: true
player: 1
mpv: 1
renderer: 0
setup: 0
C5.1 allow-mock: passed
C5.1 real-dry-run: expected_failure
```

Artefatos C9.4 confirmados na placa:

```text
/tmp/dadooh-c9-4-setup-product-v0/config.candidate.json
/tmp/dadooh-c9-4-setup-product-v0/setup-status.json
/tmp/dadooh-c9-4-setup-product-v0/summary.txt
```

## Nao alterado

- config real nao foi lida;
- config real nao foi escrita;
- writer real nao foi chamado;
- rede real nao foi alterada;
- NetworkManager nao foi modificado;
- Ethernet nao foi derrubada;
- senha Wi-Fi nao foi solicitada;
- SSID, IP, MAC, gateway e DNS nao foram publicados;
- `api_url`, `api_key`, `environment_id` real, `station_id` real e payloads
  nao foram publicados;
- logs brutos e paths privados de midia nao foram copiados;
- display/EDID/framebuffer/rotacao real nao foram alterados;
- repo `kiosky-player` nao foi alterado;
- nao houve reboot.

## Pendencia

O cancelamento por teclado local ainda precisa ser repetido com humano presente
no HDMI/teclado. A conclusao scripted validou o caminho launcher -> setup ->
candidata -> C5.1 -> restauracao do player.
