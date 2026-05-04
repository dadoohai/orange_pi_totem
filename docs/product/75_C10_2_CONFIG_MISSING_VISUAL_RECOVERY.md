# C10.2 - Config Missing com Wizard Visual e Writer

Status: implementado e validado em bancada com confirmacao humana explicita.

Data: 2026-05-04

## Objetivo

Validar o fluxo real de recuperacao de produto:
`config_missing` -> wizard visual local -> handoff privado -> writer real ->
config real -> start controlado do player.

## Metodo Seguro

O `config_missing` foi provocado sem mover nem apagar
`/data/config/config.json`. O runner executa uma copia temporaria do launcher
com `KIOSKY_CONFIG_PATH` apontando para um arquivo ausente sob `/tmp`.

Esse override existe apenas no processo temporario do teste, nao altera a unit
systemd e e removido ao final. A config real fica intacta ate o momento em que
o writer guardado escreve o destino aprovado.

## Implementado

- `scripts/remote/run_c10_2_config_missing_visual_recovery.sh`;
- modos `--prepare-only`, `--preflight`,
  `--run-config-missing-dry-run` e
  `--run-config-missing-real-write-start`;
- reuso do wizard visual C9.9.1;
- reuso do handoff C10.0;
- reuso do writer real C6;
- snapshots finais sanitizados.

## Validado

- `--prepare-only` passou;
- `--preflight` passou;
- `--run-config-missing-dry-run` passou sem escrever `/data/config`;
- `--run-config-missing-real-write-start` passou com a frase
  `CONFIRMO CONFIG_MISSING REAL C10.2 COM WRITER`;
- fonte privada veio da config ativa somente com confirmacao adicional
  explicita;
- wizard visual gerou candidata;
- handoff privado passou;
- C5.1 `real-dry-run` passou;
- writer real retornou `passed`;
- backup foi criado;
- config real ficou `root:totem` `0640`;
- usuario `totem` le e nao escreve;
- override temporario foi removido;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player/MPV ativos;
- renderer/setup ausentes;
- perfil Wi-Fi dedicado presente.

## Guardrails

- config real nao foi publicada;
- backup nao foi publicado;
- candidata privada nao foi publicada;
- endpoint/credencial privados nao foram publicados;
- identificador real de ambiente nao foi publicado;
- identificadores de rede nao foram publicados;
- logs brutos nao foram publicados;
- Wi-Fi/NetworkManager nao foram alterados;
- hotspot/portal nao foram criados;
- repo `kiosky-player` nao foi alterado;
- reboot nao foi chamado;
- root read-only nao foi habilitado;
- corte seco nao foi executado.

## Observacao

A config ativa foi lida apenas como fonte privada autorizada para endpoint e
credencial, sem publicar conteudo e com arquivo temporario restrito sob `/tmp`.
Essa leitura foi confirmada explicitamente pelo humano.

## Proximo Passo

C10.3 deve executar observacao curta de 30-60 minutos com config real, Wi-Fi
persistente e fluxo integrado validado. C11.0 continua reservado para auditoria
de readiness de root read-only antes de qualquer corte seco.
