# C18 totem-core production timer runbook

Objetivo: provar uma placa bootada da imagem `c18-hwdecode-prod-1` aplicando a
release stable de `totem-core` pelo timer de producao, mantendo o player ativo e
rollbackando depois.

Este runbook nao valida `player-runtime` auto-pull, nao thaw `player-runtime` e
nao altera `media-system`.

## Alvo

- Imagem: `c18-hwdecode-prod-1`
- Image SHA256:
  `9b10788031b9bf4884cd49169799b56d995fa56f8cb185c846bb7b485e1dc89e`
- Release:
  `totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1`
- Versao:
  `c18.ota-core-prod-20260705T184013Z-ccaf5a1`
- Payload SHA256:
  `613d9d6d1099636d7ca956c72e3927d502f1281068f8b0830b2d5f3ba2af0355`

## Preparacao

1. Gravar a imagem no microSD com Armbian Imager ou `dd`.
2. Bootar a placa com rede.
3. Aguardar o timer production disparar. A imagem usa `OnBootSec=10min` e
   `RandomizedDelaySec=10min`; aguarde pelo menos 25 minutos apos boot.
4. Nao aplicar manualmente a release antes da coleta pos-timer.

## Coleta Pos-Timer

Copiar o coletor para a placa e rodar com o probe de freeze:

```sh
scp scripts/board/c18_totem_core_production_timer_collect.py root@<IP>:/tmp/
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py --probe-frozen-player-runtime --output /tmp/c18-prod-timer-summary.json'
scp root@<IP>:/tmp/c18-prod-timer-summary.json docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json
```

Validar:

```sh
python3 scripts/qa/c18_totem_core_production_timer_evidence_gate.py \
  --summary docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json \
  --json
```

## Rollback

Depois da coleta pos-timer passar, executar rollback de `totem-core`:

```sh
ssh root@<IP> '/opt/totem/bin/totem-updatectl rollback --component totem-core'
ssh root@<IP> 'python3 /tmp/c18_totem_core_production_timer_collect.py --probe-frozen-player-runtime --output /tmp/c18-prod-rollback-summary.json'
scp root@<IP>:/tmp/c18-prod-rollback-summary.json docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json
```

Validar o marco completo:

```sh
python3 scripts/qa/c18_totem_core_production_timer_evidence_gate.py \
  --summary docs/evidence/c18-update-validation/<RUN>/post-timer-summary.json \
  --rollback-summary docs/evidence/c18-update-validation/<RUN>/post-rollback-summary.json \
  --json
```

## Criterio De Fechamento

O marco fecha quando o gate acima passa e a evidencia e commitada com:

- `post-timer-summary.json`;
- `post-rollback-summary.json`;
- README curto com horario, placa, imagem, release e non-claims;
- arvore limpa;
- `scripts/qa/c18_ota_release_gate.py --json` verde.

