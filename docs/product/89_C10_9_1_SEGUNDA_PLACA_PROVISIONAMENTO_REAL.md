# C10.9.1 - Segunda Placa Provisionamento Real Controlado

Data: 2026-05-05

Status: concluido na segunda placa/cartao. A placa dev nao foi alterada.

## Objetivo

Resolver os deltas observados apos C10.9 e validar a segunda placa com config
real provisionada de forma temporaria, sem copiar estado da placa dev e sem
publicar secrets.

C10.9 instalou a camada appliance sem secrets. C10.9.1 executa apenas o refresh
necessario, corrige feedback visual de `config_missing`, valida o fluxo
`candidate-only` sem config ativa e provisiona uma config real controlada com
arquivo privado temporario.

## Runner

Runner criado:

```bash
scripts/remote/run_c10_9_1_second_board_provision.sh
```

Modos implementados:

- `--prepare-only`
- `--refresh-install`
- `--verify-config-missing-visual`
- `--run-f10-candidate-only-check`
- `--prepare-private-template`
- `--provision-real-config`
- `--verify-player`
- `--reboot-check`

## Refresh

O refresh do instalador aplicou apenas diferencas versionadas e seguras:

- instalou `totem_status_render_preview.py` em `/opt/totem/bin`;
- atualizou `totem_open_settings_session.sh`;
- atualizou `totem_visual_setup_writer_handoff.py`;
- atualizou `totem_visual_splash.py`;
- atualizou `/usr/local/sbin/dadooh-visual-splash.py`;
- escreveu manifest instalado sanitizado.

Nao chamou writer, nao criou config real, nao alterou Wi-Fi, nao instalou
pacotes e nao rebootou. O verify apos refresh ficou `overall_status=ok`.

## Config Missing Visual

Antes, a falta de `totem_status_render_preview.py` impedia o agregador de gerar
o status visual publico e a tela podia ficar presa no splash "Iniciando
player".

Depois do refresh:

- `totem_status_render_preview_present=true`;
- `status_aggregator_functional=true`;
- `public_state=config_missing`;
- `visual_message=config_pending`;
- `stuck_starting_player=false`;
- `config_missing_visual_ok=true`.

## Candidate-only sem Config Ativa

Quando nao ha `/data/config/config.json` e nao ha fonte privada aprovada para o
writer, o fluxo nao tenta parecer que aplicou configuracao:

- gera candidata visual;
- nao chama writer;
- nao escreve config real;
- retorna para `config_missing`;
- exibe feedback publico de configuracao pendente;
- nao fica preso em "Iniciando player".

Foi tambem endurecida a limpeza de `session.lock` para remover locks de sessao
sob `/run` ou `/tmp` em saidas antecipadas, sem tocar arquivos fora da area
allowlisted.

## Fonte Privada Temporaria

O provisionamento real usou a opcao A:

```text
/tmp/dadooh-c10-9-1-private/private-values.json
```

Politica:

- diretorio `0700`;
- arquivo `0600`;
- recusa symlink;
- nao imprime valores;
- nao copia o arquivo para evidencia;
- `api_key` obrigatoria;
- `api_url` temporariamente no arquivo, porque ainda nao ha fonte real
  versionada/default adequada;
- `environment_id` vem do wizard visual.

Esse caminho e apenas para desenvolvimento/homologacao. A imagem final nao deve
conter `api_key`, `api_url`, `environment_id` real nem config real privada.

## Writer Real

Com confirmacao humana explicita, o fluxo executou:

- wizard visual;
- handoff privado;
- C5.1 real-dry-run;
- writer real;
- escrita atomica de `/data/config/config.json`;
- permissoes `root:totem 0640`;
- validacao de leitura pelo usuario `totem`;
- bloqueio de escrita pelo usuario `totem`;
- atualizacao de `orientation.json`;
- remocao de temporarios privados.

Resultado:

- `c5_real_dry_run=passed`;
- `writer_called=true`;
- `real_config_written=true`;
- `permissions_ok=true`;
- `private_candidate_removed=true`;
- `session_private_values_removed=true`;
- `config_content_published=false`;
- `credential_values_published=false`.

Nao havia config anterior na segunda placa, portanto `backup_created=false` e
esperado.

## Player

Estado final observado:

- `public_state=player_running`;
- `playback=playing`;
- `failure_category=none`;
- `kiosk_process_count=1`;
- `mpv_process_count=1`;
- `renderer_process_count=0`;
- `setup_process_count=0`;
- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `NRestarts=0`;
- `systemctl_failed_count=0`.

## Reboot Controlado

Com autorizacao humana, C10.9.1 executou reboot controlado da segunda placa.

Estado pos-boot:

- SSH voltou;
- config real presente com modo `0640`;
- `public_state=player_running`;
- `playback=playing`;
- `failure_category=none`;
- `kiosk_process_count=1`;
- `mpv_process_count=1`;
- `renderer_process_count=0`;
- `setup_process_count=0`;
- `kiosky-player.service=active/enabled`;
- `totem-settings-trigger.service=active/enabled`;
- `totem-open-settings.service=inactive/static`;
- `dadooh-visual-splash.service=active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`;
- `kernel_critical_filter_count=0`.

## Proximo Passo

C10.9.1 deixa a segunda placa pronta para C11.0 read-only readiness audit.

Ainda fora deste escopo:

- backend/login final de ativacao;
- imagem final;
- root read-only;
- corte seco;
- estrategia de artefato offline/produtivo para `kiosky-player`;
- remocao do bootstrap tecnico manual da imagem final.

## Atualizacao C10.10

C10.10 consolidou o provisionamento privado de bancada em ferramenta e runbook:

- helper: `scripts/board/totem_private_values_prepare.py`;
- runner C10.9.1: modo `--validate-private-values`;
- runbook: `docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`;
- manifest RC: `releases/installable-rc/manifest.md`.

O helper cria template, valida permissoes `0700/0600`, recusa symlink e publica
somente booleans sanitizados. Ele nao imprime `api_key`, nao despeja `api_url`
literal e mantem `environment_id` como dado do wizard. C10.10 nao reprovisiona
a placa e nao altera config real.
