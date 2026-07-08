# C21.2 Board Wizard Preview

Data: 2026-07-08.

Pacote aplicado na placa por OTA local governado:

- componente: `totem-core`
- versao: `c21.2-qr-pairing-wizard-ota-compatible-20260708T134735Z-20f7b20`
- apply rc: `0`
- current apos apply: `c21.2-qr-pairing-wizard-ota-compatible-20260708T134735Z-20f7b20`
- previous apos apply: `c20.9-wifi-step-copy-20260708T060338Z-34a9537`
- `kiosky-player.service`: `active`
- settings lock apos apply: ausente
- self-test do wizard na placa apos apply: `ok`

Evidencia visual gerada na placa:

- comando: `/opt/totem/bin/totem_setup_visual_wizard.py --preview-screens --out-dir /tmp/c21.2-wizard-preview`
- telas geradas: 19 SVGs em `screens/`
- tela `0012-03-environment.svg` contem `Entrar com codigo/QR`
- tela `0014-03-environment-pairing-authorized.svg` contem `Totem autorizado`
- varredura dos SVGs nao encontrou mock API key, API URL privada, environment_id privado ou station_id privado

Non-claims:

- nao e backend real;
- nao e login real em `home.dadooh.ai`;
- nao e QR escaneavel final;
- nao emite credencial real de maquina;
- nao executa escrita real de config neste slice.
