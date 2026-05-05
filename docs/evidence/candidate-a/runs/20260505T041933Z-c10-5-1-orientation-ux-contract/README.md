# C10.5.1 Orientation UX Contract

Data: 2026-05-05

Commit base: `f608d0e Add C10.5 visual boot rotation UX`

## Comandos

```bash
git status --short
git log --oneline -10
git diff --check
python3 scripts/board/totem_setup_visual_wizard.py --self-test
python3 scripts/board/totem_visual_splash.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_config_contract_validate.py --self-test
bash -n scripts/remote/run_c10_5_visual_boot_rotation.sh
bash -n scripts/remote/run_c10_3_product_surface_v0.sh
bash -n scripts/remote/run_c10_5_1_orientation_ux_contract.sh
python3 scripts/board/totem_setup_visual_wizard.py --scripted --rotation-key portrait_left --network-step configured_wifi --environment-id <synthetic> --out-dir /tmp/dadooh-c10-5-1-scripted-check
python3 scripts/board/totem_setup_visual_wizard.py --scripted --rotation-key landscape --network-step configured_wifi --environment-id <synthetic> --out-dir /tmp/dadooh-c10-5-1-scripted-check-landscape
scripts/remote/run_c10_5_1_orientation_ux_contract.sh root@192.168.18.115 --prepare-only
scripts/remote/run_c10_5_1_orientation_ux_contract.sh root@192.168.18.115 --preview-orientation-flow
scripts/remote/run_c10_5_1_orientation_ux_contract.sh root@192.168.18.115 --run-complete-portrait
scripts/remote/run_c10_5_1_orientation_ux_contract.sh root@192.168.18.115 --run-complete-landscape
scripts/remote/run_c10_5_1_orientation_ux_contract.sh root@192.168.18.115 --preview-splash-orientations
```

## Resultado

- self-tests locais: passaram;
- `git diff --check`: limpo;
- runner C10.5.1 `--prepare-only`: passou;
- candidato sintetico portrait: `rotation_deg=270`, `layout_mode=portrait`;
- candidato sintetico landscape: `rotation_deg=0`, `layout_mode=landscape`;
- splash aceita contrato de orientacao: `rotation_deg` e `layout_mode` em status sanitizado;
- `--preview-orientation-flow`: passou;
- `--run-complete-portrait`: passou com `rotation_deg=270`;
- `--run-complete-landscape`: passou com `rotation_deg=180`;
- `--preview-splash-orientations`: passou com `rotation_deg` `0`, `90`, `180` e `270`;
- C5.1 `allow-mock`: passou nos fluxos com candidata;
- C5.1 `real-dry-run`: falhou como esperado por placeholders.

## Estado Final

- servico: `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player=1;
- MPV=1;
- renderer=0;
- setup=0.

## Guardrails

- `real_config_read=false`;
- `real_config_written=false`;
- `writer_called=false`;
- `wifi_changed=false`;
- `network_changed=false`;
- `root_read_only_enabled=false`;
- `power_cut_tested=false`;
- nenhum dado sensivel ou identificador real foi publicado nesta evidencia.

## Pendente

- ajustes finos de design visual podem seguir em rodada futura;
- guardrails persistentes de boot/shutdown ficam para C10.5.2.
