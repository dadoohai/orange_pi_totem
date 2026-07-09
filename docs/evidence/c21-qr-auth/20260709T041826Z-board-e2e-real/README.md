# C21 Board E2E Real QR Auth

Data: 2026-07-09.

Escopo: validar ponta a ponta o fluxo real de ativacao por codigo/QR na placa:
wizard na placa -> backend `/totem-auth` -> `home.dadooh.ai/totem/activate` ->
poll da placa -> credencial temporaria -> writer real -> retorno do player.

Resultado: **passou para o slice C21 E2E real em laboratorio**.

Evidencia principal:

- `pairing-result.public.json`: `state=authorized`, `passed=true`,
  `private_values_mode=0600`, `human_firebase_token_on_device=false`.
- `session-status.json`: `apply_mode=real-write`,
  `policy_private_source=tmp-file`, `homologation_seed_mode=false`,
  `handoff_rc=0`, `writer_rc=0`, `real_config_written=true`,
  `private_source_temp_removed=true`, `credential_values_published=false`,
  `playback=playing`.
- `config-public-check.json`: `/data/config/config.json` existe com modo
  `0640`, `api_url_present=true`, `api_key_present=true`,
  `environment_id_present=true`, `station_id_present=true`.
- `systemd-public-check.json`: `totem-open-settings.service` terminou com
  `Result=success`; `kiosky-player.service` ficou `active` com `Result=success`.
- `updatectl-status.json`: `totem-core` ficou com `current=C21.7` e
  `previous=C21.6`, mantendo caminho operacional de rollback do pacote.
- `external-public-check.json`: API `/health` e
  `home.dadooh.ai/totem/activate?...` retornaram `200` no momento da coleta.

Observacao: `wizard_rc=8` e o codigo de saida retornado por `openvt`; a rodada
nao caiu em cancelamento, pois `config.candidate.json` existia, o handoff rodou,
o writer retornou `0`, a unidade terminou limpa e o player voltou.

Privacidade:

- nenhum valor de `api_key`, `device_secret` ou token humano foi copiado para
  esta evidencia;
- os artefatos publicos indicam apenas presenca de credencial/config;
- o arquivo temporario privado do pareamento foi removido ao final.

Non-claims:

- nao valida revogacao/rollback de token no backend;
- nao valida fluxo sem internet, expirado, negado ou `already_used`;
- nao altera `player-runtime`, MPV, kernel, media-system ou field-data;
- nao substitui monitoramento/rollout por grupos em producao.
