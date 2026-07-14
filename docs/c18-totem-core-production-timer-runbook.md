# C18 totem-core production timer runbook

Objetivo: provar que uma imagem de producao adota uma release `stable` de
`totem-core` pelo timer real, sem mudar o player, e que `no-op`, rollback e
restauracao continuam funcionais.

Este runbook nao valida nem libera `player-runtime`, nao altera
`media-system` e nao publica a release. A publicacao exata deve estar
verificada antes de tocar o timer da placa.

## Alvo Atual

- Imagem: `c18-hwdecode-prod-14` / `c18.image-prod.14`
- Image SHA256:
  `3d93f05f896c8e7c17866129a901a02803e65d7968ed69eac3987b03a4b02682`
- Release:
  `totem-core-c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704`
- Versao:
  `c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704`
- Payload SHA256:
  `ab46032fd80c37a43ee7edf2b3e3d34f1b7e17a91b457c82b7965e37a5dc0f38`
- Source commit:
  `0cfe704a598904b192036583a4ea5ac9571d0ba8`
- Rollback esperado:
  `c20.14-settings-stop-hardening-20260714T034217Z-22bd473`

Ao reutilizar o runbook para outra imagem ou release, substituir todos esses
valores e passar os overrides explicitos ao coletor e ao gate. Nao depender
dos defaults historicos das ferramentas.

## Precondicoes

1. Repo limpo, pacote e promotion evidence commitados.
2. Release GitHub exata existente, nao-prerelease, com seis assets validados.
3. O `latest` publico aponta para a release esperada.
4. Placa na imagem esperada, player ativo e `player-runtime` congelado.
5. Antes da primeira aplicacao, registrar estado de `totem-core`, timers,
   player e `LastTriggerUSec`.
6. O timer pode estar temporariamente desabilitado para isolar outro ensaio.
   Reabilita-lo somente depois das cinco precondicoes anteriores.

Copiar o coletor para `/tmp` e executar seu `--self-test` antes da campanha:

```sh
scp scripts/board/c18_totem_core_production_timer_collect.py root@<IP>:/tmp/
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py --self-test'
```

## 1. Aplicacao Pelo Timer Real

Reabilitar o timer e aguardar uma nova execucao real. A primeira aplicacao nao
pode ser iniciada manualmente:

```sh
ssh root@<IP> 'systemctl enable --now totem-update-agent.timer'
```

Confirmar que `LastTriggerUSec` avancou, o journal cita a tag exata e o estado
atual passou para a versao esperada. Entao coletar:

```sh
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py \
  --expected-image-tag c18-hwdecode-prod-14 \
  --expected-release-tag totem-core-c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704 \
  --probe-frozen-player-runtime \
  --output /tmp/c18-core-post-timer.json'
scp root@<IP>:/tmp/c18-core-post-timer.json \
  docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json
```

Validar com todos os valores explicitos:

```sh
python3 scripts/qa/c18_totem_core_production_timer_evidence_gate.py \
  --summary docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json \
  --expected-image-tag c18-hwdecode-prod-14 \
  --expected-image-version c18.image-prod.14 \
  --expected-release-tag totem-core-c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704 \
  --expected-version c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704 \
  --expected-rollback-version c20.14-settings-stop-hardening-20260714T034217Z-22bd473 \
  --expected-payload-sha256 ab46032fd80c37a43ee7edf2b3e3d34f1b7e17a91b457c82b7965e37a5dc0f38 \
  --expected-source-commit 0cfe704a598904b192036583a4ea5ac9571d0ba8 \
  --json
```

## 2. No-op

Registrar SHA256 de `state.json`, `current`, `previous` e estado do player.
Iniciar o servico uma segunda vez e confirmar `apply_noop_already_current`:

```sh
ssh root@<IP> 'systemctl start totem-update-agent.service'
```

O SHA256 do state, os dois links e o player devem permanecer inalterados. A
coleta desta fase deve ser salva como `noop-summary.json`.

## 3. Rollback

Somente depois de a aplicacao e o no-op passarem:

```sh
ssh root@<IP> '/opt/totem/bin/totem-updatectl rollback --component totem-core'
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py \
  --expected-image-tag c18-hwdecode-prod-14 \
  --expected-release-tag totem-core-c20.15-prod14-stable-alignment-20260714T201642Z-0cfe704 \
  --probe-frozen-player-runtime \
  --output /tmp/c18-core-post-rollback.json'
scp root@<IP>:/tmp/c18-core-post-rollback.json \
  docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json
```

Repetir o gate anterior adicionando:

```sh
--rollback-summary docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json
```

O rollback deve tornar C20.14 atual e manter C20.15 como `previous`, com
self-test e player verdes.

## 4. Restauracao

Reaplicar pelo mesmo servico governado:

```sh
ssh root@<IP> 'systemctl start totem-update-agent.service'
```

Coletar `restored-summary.json` e rodar o gate de resumo sem
`--rollback-summary`. C20.15 deve voltar a `current`, C20.14 deve ficar como
`previous`, o timer deve permanecer ativo e o freeze publico de
`player-runtime` deve continuar em `rc=44`.

## 5. Reboot Final

Com os dois componentes restaurados, confirmar os dois timers habilitados e
ativos, reiniciar uma vez e recoletar o estado. O fechamento exige:

- marker prod14 e configuracao persistidos;
- `totem-core` C20.15 atual e self-test verde;
- `player-runtime` C25B atual e freeze publico `rc=44`;
- player ativo, MPV em hardware decode e conteudo avancando;
- zero units falhadas e nenhum item em quarentena;
- repositorio limpo e evidencia commitada.

## Evidencia Minima

- `pre-summary.json`;
- `post-timer-summary.json`;
- `noop-summary.json` e hashes antes/depois;
- `post-rollback-summary.json`;
- `restored-summary.json`;
- `post-reboot-summary.json`;
- resultado do `c18_totem_core_production_timer_evidence_gate.py`;
- verificacao dos seis assets remotos;
- `README.md`, `SHA256SUMS` e non-claims.

O gate final e a auditoria devem reprovar qualquer fase ausente, identidade
divergente, restart inesperado do player ou tentativa de inferir liberacao de
`player-runtime` a partir deste ensaio de `totem-core`.
