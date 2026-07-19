# C18 totem-core production timer runbook

Objetivo: provar que uma imagem de producao adota uma release `stable` de
`totem-core` pelo timer real, sem mudar o player, e que `no-op`, rollback e
restauracao continuam funcionais.

Este runbook nao valida nem libera `player-runtime`, nao altera
`media-system` e nao publica a release. A publicacao exata deve estar
verificada antes de tocar o timer da placa.

## Alvo Atual

- Imagem: `c18-hwdecode-prod-19-c26` / `c18.image-prod.19-c26`
- Image SHA256:
  `991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`
- Release:
  `totem-core-c26.17-product-stable-20260719T193306Z-0e02019-actions`
- Versao:
  `c26.17-product-stable-20260719T193306Z-0e02019-actions`
- Payload SHA256:
  `0bbd935fc4a589f65438f380acecdb8d38c1877bd14cf0ba53dd16bd12f823d3`
- Source commit:
  `0e02019a83b092a0915ca6dfa9a020fc33f6a341`
- Rollback esperado:
  `c26.16-local-recovery-20260719-5df9521-final-guarded-actions`

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

Reabilitar o timer e aguardar uma nova execucao real. O disparo usado para
provar o timer nao pode ser iniciado manualmente:

```sh
ssh root@<IP> 'systemctl enable --now totem-update-agent.timer'
```

Se o timer for habilitado depois que `OnBootSec` ja passou, o systemd pode
mostra-lo como `active (elapsed)` e sem proximo disparo. Isso nao prova o timer
e nao autoriza substituir a prova natural por um start manual. Registrar o diagnostico e
reiniciar a placa com o timer ja habilitado; depois do boot, aguardar o disparo
real e confirmar `LastTriggerUSec` novo.

Se a release exata ja estiver em `current`, o disparo natural pode terminar em
`apply_noop_already_current`. Nesse caso, a campanha tambem precisa conter uma
aplicacao publica mutante da mesma release pelo mesmo servico governado, com
rollback anterior e hashes preservados. O no-op natural prova agendamento,
consulta e selecao; a execucao separada prova a mutacao. Nenhuma das duas deve
ser apresentada isoladamente como prova de todo o ciclo.

Confirmar que `LastTriggerUSec` avancou, o journal cita a tag exata e o estado
atual passou para a versao esperada. Entao coletar:

O gate exige que os timestamps UTC do download e do `apply_success`/no-op da
mesma release ocorram depois de `LastTriggerUSec` e dentro da janela curta de
correlacao. Um trigger antigo somado a um
`systemctl start` manual posterior deve reprovar, mesmo quando ambos aparecem
no mesmo journal.

```sh
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py \
  --expected-image-tag c18-hwdecode-prod-19-c26 \
  --expected-release-tag totem-core-c26.17-product-stable-20260719T193306Z-0e02019-actions \
  --probe-frozen-player-runtime \
  --output /tmp/c18-core-post-timer.json'
scp root@<IP>:/tmp/c18-core-post-timer.json \
  docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json
```

Validar com todos os valores explicitos:

```sh
python3 scripts/qa/c18_totem_core_production_timer_evidence_gate.py \
  --summary docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json \
  --expected-image-tag c18-hwdecode-prod-19-c26 \
  --expected-image-version c18.image-prod.19-c26 \
  --expected-release-tag totem-core-c26.17-product-stable-20260719T193306Z-0e02019-actions \
  --expected-version c26.17-product-stable-20260719T193306Z-0e02019-actions \
  --expected-rollback-version c26.16-local-recovery-20260719-5df9521-final-guarded-actions \
  --expected-payload-sha256 0bbd935fc4a589f65438f380acecdb8d38c1877bd14cf0ba53dd16bd12f823d3 \
  --expected-source-commit 0e02019a83b092a0915ca6dfa9a020fc33f6a341 \
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
  --expected-image-tag c18-hwdecode-prod-19-c26 \
  --expected-release-tag totem-core-c26.17-product-stable-20260719T193306Z-0e02019-actions \
  --probe-frozen-player-runtime \
  --output /tmp/c18-core-post-rollback.json'
scp root@<IP>:/tmp/c18-core-post-rollback.json \
  docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json
```

Repetir o gate anterior adicionando:

```sh
--rollback-summary docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json
```

O rollback deve tornar C26.16 atual e manter C26.17 como `previous`, com
self-test e player verdes.

## 4. Restauracao

Reaplicar pelo mesmo servico governado:

```sh
ssh root@<IP> 'systemctl start totem-update-agent.service'
```

Coletar `restored-summary.json` e rodar o gate de resumo sem
`--rollback-summary`. C26.17 deve voltar a `current`, C26.16 deve ficar como
`previous`, o timer deve permanecer ativo e o freeze publico de
`player-runtime` deve continuar em `rc=44`.

## 5. Reboot Final

Com os dois componentes restaurados, confirmar os dois timers habilitados e
ativos, reiniciar uma vez e recoletar o estado. O fechamento exige:

- marker prod19 e configuracao persistidos;
- `totem-core` C26.17 atual e self-test verde;
- `player-runtime` C25B atual e freeze publico `rc=44`;
- player ativo, MPV em hardware decode e conteudo avancando;
- zero units falhadas e nenhum item em quarentena;
- repositorio limpo e evidencia commitada.

O gate `c18_totem_core_production_timer_evidence_gate.py` valida uma operacao e
depende do journal do apply/no-op no boot atual. Nao apresenta-lo como gate de
reboot: depois da reinicializacao, ele deve ficar apenas como diagnostico se o
journal anterior nao estiver disponivel. O fechamento pos-reboot usa o resumo
persistido do core, os gates verdes coletados antes do reboot e uma nova prova
de estado/player.

## Evidencia Minima

- `pre-summary.json`;
- `post-timer-summary.json`;
- `noop-summary.json` e hashes antes/depois;
- `post-rollback-summary.json`;
- `restored-summary.json`;
- `post-reboot-core-summary.json` e `post-reboot-player.json`;
- resultado do `c18_totem_core_production_timer_evidence_gate.py`;
- verificacao dos seis assets remotos;
- `README.md`, `SHA256SUMS` e non-claims.

O gate final e a auditoria devem reprovar qualquer fase ausente, identidade
divergente, restart inesperado do player ou tentativa de inferir liberacao de
`player-runtime` a partir deste ensaio de `totem-core`.
