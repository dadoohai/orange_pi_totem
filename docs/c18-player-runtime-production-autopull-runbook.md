# C18 player-runtime production auto-pull

Objetivo: provar separadamente que uma imagem production busca e adota o alvo
exato autorizado, consegue voltar/restaurar e permanece limpa em playback por
uma janela continua que cubra falhas tardias, sem abrir `latest`.

## Alvo atual - prod14

- version: `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`
- payload SHA256:
  `b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d`
- tag:
  `player-runtime-c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`
- autorizacao: `scripts/board/player_runtime_production_autopull.json`
- verificacao remota existente:
  `docs/evidence/c18-update-validation/20260714T171607Z-c25b-existing-release-verification/publication-verification.json`
- imagem prevista: `c18-hwdecode-prod-14` / `c18.image-prod.14`
- baseline: o mesmo C25B embutido na imagem, adotado por
  `/opt/totem/kiosky-player` sem links em `/data/player-runtime`;
- modo do gate: `image-fallback-reapply`.

A prod13 provou download/verificacao reais, mas iniciou o health antes da
publicacao inicial do status. A espera production agora e oito segundos e o
canario isolado cobre warm-up, observacao e duas coletas de margem sem reiniciar
no meio da avaliacao. Os limites do health permanecem inalterados. A quarantine
dessa tentativa nao e limpa: a gravacao da prod14 inicia a topologia final sem
herdar esse estado.

## Ordem

1. Gate global verde, repo limpo e imagem production offline validada.
2. Confirmar branch, tag e os tres assets exatos ja publicados com o publisher
   exact-target em `--verify-existing`.
3. Salvar a evidencia dessa verificacao C25B, inclusive hashes baixados e
   `latest` inalterado. O bloco `verification` deve registrar zero criacao de
   release, tres assets baixados, tag/commit exatos e draft/prerelease falsos.
   Nao republicar o release que ja existe.
4. Gravar a prod14. Antes do primeiro disparo, provar que `current` e
   `previous` estao ausentes e que o launcher adotou o C25B embutido da
   imagem. O timer deve estar `enabled` e `active` durante a coleta `pre`; se
   foi pausado para concluir o primeiro setup, reativa-lo antes dessa coleta.
5. Coletar `pre`, registrar `LastTriggerUSec` e aguardar o disparo real do
   timer. Nao iniciar a service manualmente no primeiro apply. Coletar
   `post_apply` somente depois que `LastTriggerUSec` mudar, a service terminar
   com sucesso e C25B for adotado por `/data/player-runtime/current`.
   O perfil production aguarda 8 segundos antes da janela estrita de health do
   candidato. O canario dura pelo menos toda essa espera, a observacao e duas
   coletas de margem. Esse desenho cobre a publicacao inicial do status sem
   criar um segmento terminal curto e sem alterar os
   limites do deep-health nem aceitar candidato sem reproducao real.
6. Rodar novamente a unit para provar `noop` sem alterar state/symlinks nem
   reiniciar o player.
7. Rodar `rollback-player-runtime-authorized` para o fallback da imagem e
   coletar `rollback`. `current` e `previous` devem voltar a ficar ausentes e o
   processo deve expor `KIOSKY_APP_DIR=/opt/totem/kiosky-player`.
8. Restaurar C25B por uma nova execucao do apply exato, nao por um segundo
   rollback. Coletar `restored` com `--deep-health-duration-sec 600`. Depois do
   restore, aguardar status `playing`, MPV ativo e item atual antes de iniciar a
   janela continua.
9. Copiar cada snapshot junto de seu diretorio `<fase>-deep-health`, sem
   separar os arquivos ou alterar nomes. Cada fase usa um diretorio novo e
   vazio; o coletor recusa reutilizar um diretorio que ja contenha evidencia.
10. Rodar `c18_player_runtime_production_autopull_evidence_gate.py` sobre as
   cinco coletas, a evidencia de publicacao e os quatro artefatos exatos, com:
   `--roundtrip-mode image-fallback-reapply`, identidade prod14 e baseline
   version/payload C25B explicitos. Passar tambem
   `--expected-image-marker-sha256` com o SHA256 obtido da extracao offline da
   imagem prod14 auditada, nunca recalculado a partir da propria coleta da
   placa. Depois commitar a evidencia com arvore limpa.

## Invocacao canonica prod14

O operador deve copiar o coletor atual para um diretorio novo da placa e usar
tambem os dois modulos irmaos usados pelo deep-health. Os tres arquivos devem
ficar juntos no mesmo diretorio:

- `c18_player_runtime_production_autopull_collect.py`;
- `c18_playback_health_collect.py`;
- `c18_playback_health_summary.py`.

Usar sempre estes parametros. Nao usar os defaults historicos prod8/C23:

```bash
E2E=/tmp/c18-prod14-e2e
COLLECT="$E2E/c18_player_runtime_production_autopull_collect.py"
TAG=c18-hwdecode-prod-14
MARKER=/etc/dadooh/c18-hwdecode-prod-14-image

python3 "$COLLECT" --phase pre --output "$E2E/pre.json" \
  --expected-image-tag "$TAG" --marker-path "$MARKER" --probe-freeze \
  --deep-health-output-dir "$E2E/pre-deep-health"

PRE_TRIGGER="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["systemd"]["timer"]["show"]["LastTriggerUSec"])' \
  "$E2E/pre.json")"
while [ "$(systemctl show totem-player-runtime-update-agent.timer \
  -p LastTriggerUSec --value)" = "$PRE_TRIGGER" ]; do sleep 1; done
while systemctl is-active --quiet \
  totem-player-runtime-update-agent.service; do sleep 1; done
python3 "$COLLECT" --phase post_apply --output "$E2E/post_apply.json" \
  --expected-image-tag "$TAG" --marker-path "$MARKER" --probe-freeze \
  --deep-health-output-dir "$E2E/post_apply-deep-health"

systemctl start totem-player-runtime-update-agent.service
python3 "$COLLECT" --phase noop --output "$E2E/noop.json" \
  --expected-image-tag "$TAG" --marker-path "$MARKER" --probe-freeze \
  --deep-health-output-dir "$E2E/noop-deep-health"

/opt/totem/bin/totem-updatectl rollback-player-runtime-authorized \
  --authorization /data/updates/player-runtime-production-autopull.json \
  --reason production_authorized_rollback
python3 "$COLLECT" --phase rollback --output "$E2E/rollback.json" \
  --expected-image-tag "$TAG" --marker-path "$MARKER" --probe-freeze \
  --deep-health-output-dir "$E2E/rollback-deep-health"

systemctl start totem-player-runtime-update-agent.service
python3 "$COLLECT" --phase restored --output "$E2E/restored.json" \
  --expected-image-tag "$TAG" --marker-path "$MARKER" --probe-freeze \
  --deep-health-duration-sec 600 \
  --deep-health-output-dir "$E2E/restored-deep-health"
```

Cada comando deve terminar com `rc=0`; nao reutilizar diretorios. Antes dessa
sequencia, validar boot, expansao, identidade SSH, wizard/configuracao e player
embutido sem links `current`/`previous`. Depois do gate das cinco fases, fazer
um reboot separado e repetir marcador, adocao e playback estrito. O gate local
deve receber explicitamente todos os arquivos acima, identidade prod14,
target/baseline C25B, `--roundtrip-mode image-fallback-reapply`,
`--require-freeze-probe` e `--min-continuous-restored-sec 600`. A invocacao
local completa e:

```bash
RUN=/path/to/copied-prod14-e2e
REL=releases/player-runtime/c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4
PUB=docs/evidence/c18-update-validation/20260714T171607Z-c25b-existing-release-verification/publication-verification.json

python3 scripts/qa/c18_player_runtime_production_autopull_evidence_gate.py \
  --authorization scripts/board/player_runtime_production_autopull.json \
  --publication-evidence "$PUB" \
  --manifest "$REL/dadooh-player-runtime-c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4.manifest.json" \
  --payload "$REL/dadooh-player-runtime-c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4.tar.gz" \
  --release-gate "$REL/c18-player-runtime-release-gate.json" \
  --pre "$RUN/pre.json" --post-apply "$RUN/post_apply.json" \
  --noop "$RUN/noop.json" --rollback "$RUN/rollback.json" \
  --restored "$RUN/restored.json" \
  --expected-image-tag c18-hwdecode-prod-14 \
  --expected-image-version c18.image-prod.14 \
  --expected-image-marker-sha256 ef56eec47a977bb4f0d8d3f50a7934ae0ac5b1219fa52eaccb76f8483c4fb8f2 \
  --expected-updater-sha256 3c39aa4dcda793eb52a9eeebbe6c03e38d1a8c2080c8814ea938ae21e559b282 \
  --target-version c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4 \
  --baseline-version c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4 \
  --baseline-payload-sha256 b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d \
  --roundtrip-mode image-fallback-reapply \
  --expected-rollback-reason production_authorized_rollback \
  --max-player-restarts 0 --require-freeze-probe \
  --min-continuous-restored-sec 600 --json
```

## Resultado exigido

- C25B veio da tag GitHub exata e tem hashes/marker corretos;
- o trigger do timer ocorreu depois do pre e a unit teve nova invocacao para o
  apply e para o no-op;
- os arquivos reais de amostras/deep-health acompanham cada fase e seus hashes
  batem com o snapshot;
- os cinco sidecars `deep-health-*.json` produzidos pelo coletor acompanham cada
  fase;
- player e HW decode passam deep-health apos apply, rollback e restauracao;
- o `restored` final cobre ao menos 10 minutos continuos, com amostras reais,
  zero `media_load_failed`, restart interno, restart de servico, acao de
  watchdog ou falha de IPC;
- no-op nao muda state, current ou previous;
- rollback reinicia e verifica o player antes de reportar sucesso;
- CLI generico de player-runtime continua bloqueado com `rc=44`;
- o probe `rc=44` executa o caminho publico exato
  `/opt/totem/bin/totem-updatectl rollback --component player-runtime`;
- o marcador production e arquivo regular no caminho esperado e seu conteudo
  bruto bate com o hash previamente extraido da imagem auditada;
- timer de `totem-core` continua independente;
- rollback realmente adotou o player embutido da imagem, nao apenas removeu
  symlinks;
- restauracao foi um novo apply e uma nova invocacao, nao um rollback
  mascarado;
- estado final: C25B `current`, `previous` ausente e alvo fora de quarantine.

Non-claims: nao e `latest` amplo, stable de qualquer pacote futuro, rollout por
grupos, assinatura consumida no device ou atualizacao de media-system. O gate
offline detecta evidencia ausente/inconsistente, mas nao torna artefatos
coerentemente fabricados resistentes a adulteracao sem attestation no device.

## Historico

Mecanica C22 fechada em 2026-07-10 na imagem prod7. O timer real aplicou C22 a
partir do bridge, o no-op nao alterou estado, o rollback voltou ao bridge e a
segunda troca restaurou C22. As cinco janelas curtas passaram deep-health e
freeze `rc=44`.

Uma auditoria posterior encontrou restart interno do MPV entre/depois dessas
janelas. A reavaliacao atual preserva `mechanics_passed=true`, mas bloqueia
`product_distribution_cleanliness_passed` porque o `restored` original durou
somente 30 segundos. Essa separacao e o requisito continuo formam o schema v2
do gate. C23 e a recaptura continua de 10 minutos fecham essa claim.

C23 fechou o auto-pull remoto na prod8 em modo legado
`data-previous-roundtrip`, com bridge real como `previous`. O modo continua
disponivel para novas coletas nessa topologia. Os snapshots C23 sao registros
historicos imutaveis e hoje reprovam sob a semantica mais nova do gate de
autorizacao; nao devem ser reclassificados nem usados para descrever a topologia
limpa da prod14.

Evidencia:
`docs/evidence/c18-update-validation/20260710T190539Z-prod7-m5-production-autopull-c22/`.
