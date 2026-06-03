# C18 Update Contract

Este e o contrato vigente para atualizacoes da linha C18. Documentos C14/C15/C17
sao historicos quando divergirem daqui.

Estado live/baseline validado deve ser consultado em
`docs/product/189_C18_OTA_READINESS_GATE.md`. Este contrato define regras; o 189
registra qual imagem/release esta em laboratório em cada rodada.

## Regra Principal

OTA C18 e manual/operator-triggered e restrito a `totem-core` operacional.
Mudancas em player, runtime de midia, sistema, updater, units ou imagem base
nao entram no OTA comum.

## Classes De Mudanca

| Classe | Exemplos | Caminho permitido | Rollback/fallback |
| --- | --- | --- | --- |
| `totem-core` operacional | wizard, splash, status, writer, Wi-Fi helper, config contract, settings session | OTA manual `totem-core` | `current`/`previous` em `/data/core/totem` e fallback em `/opt/totem/core-fallback/bin` |
| `player-runtime` | `kiosk.py`, `kiosky_service_launcher.sh`, logica de start do player, flags de MPV, timing/sync/duracao/playlist | nova imagem ou pacote C18-aware explicitamente homologado | imagem/cartao known-good; nao OTA comum |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, HDMI/display, kernel, DTB, U-Boot, BSP | nova imagem + homologacao | imagem/cartao known-good; sem A/B nesta linha |
| `field-data` | config real, seed, midia, playlist/cache, estado operacional | fluxo operacional em `/data`; nao release de software | writer/backup/re-sync conforme o dado |

## Fronteira Do Player

`kiosky-player` OTA esta congelado na C18. O congelamento tambem vale para
mudancas indiretas no runtime do player.

`kiosky_service_launcher.sh` e arquivo de `player-runtime`: a imagem deve
fornece-lo como arquivo fixo em `/opt/totem/bin`, e releases OTA de
`totem-core` nao devem inclui-lo em `bin/`.

Uma release `totem-core` que precisa alterar como o player sobe deve ser tratada
como frente de `player-runtime`, com imagem/homologacao ou pacote C18-aware
proprio. Nao publicar como core comum.

## Contrato De Manifest

Toda release C18 de `totem-core` deve usar `dadooh.totem.update.v1` e declarar:

- `component="totem-core"`;
- `channel` correto (`lab`, `homologation` ou `stable`);
- `created_at_utc` ISO-8601 com timezone UTC;
- `payload_sha256`;
- `requires.device="orangepizero3"`;
- `requires.base_image_min="c17.4.2"` para esta linha;
- `requires.device_track="c18-hwdecode"`;
- `requires.updater_features` contendo:
  - `c18-freeze-kiosky-player-v1`;
  - `c18-rollback-reapply-v1`;
  - `c18-safe-payload-v1`;
  - `c18-track-v1`.

Updater C18 deve rejeitar manifest sem esses campos, com track errado, feature
desconhecida, feature ausente, canal incompatível, policy ausente/invalida ou
payload inseguro.

## Policy Do Device

Policy C18 deve existir em `/data/updates/policy.json` e restringir:

```json
{
  "schema": "dadooh.totem.update.policy.v1",
  "device_track": "c18-hwdecode",
  "allowed_components": ["totem-core"],
  "allow_downgrade": false
}
```

`device_channel` e `allow_prerelease` variam por ambiente. Policy sem
`allowed_components` valido deve falhar fechada, nao assumir componente por
default.

## Gates Minimos

Antes de publicar ou promover OTA C18:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json
```

Para pacote especifico:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py \
  --package-manifest <release-dir>/dadooh-totem-core-<version>.manifest.json \
  --package-payload <release-dir>/dadooh-totem-core-<version>.tar.gz \
  --json
```

O gate deve provar, no minimo:

- `totem-core` sem `bin/kiosky_service_launcher.sh` no payload;
- manifest com contrato C18 completo;
- payload com SHA correto e sem path traversal, symlink, hardlink ou segredo;
- release GitHub publicada a partir do `source_commit` declarado no manifest,
  nunca do default branch implicito do `gh`;
- policy/service/timer C18 coerentes;
- freeze de `kiosky-player` preservado;
- scripts historicos de release de `kiosky-player` falhando por padrao, salvo
  override explicito para release `player-runtime` C18-aware homologada;
- diff OTA comum sem arquivos `player-runtime` fixos por imagem;
- sandbox apply/rollback de `totem-core` passando.

## Quando Gerar Imagem

Gerar nova imagem quando a mudanca tocar:

- `kiosk.py`;
- `kiosky_service_launcher.sh`;
- MPV/ffmpeg/hwdecode/libplacebo/wrapper de MPV;
- kernel, DTB, U-Boot, BSP, display/HDMI;
- updater `totem-updatectl`;
- systemd units/timers;
- policy de update de fabrica;
- qualquer mudanca que exige reboot ou alteracao fora de `/data/core/totem`.

## Scripts Bypass E Historicos

Scripts de SSH/rsync/hotfix direto sao ferramentas de bancada ou evidência
histórica. Eles nao sao caminho de update C18, nao substituem release GitHub e
nao devem ser usados para campo/producao.

Exemplos de bypass/lab-only:

- `scripts/remote/push_and_run.sh`;
- `scripts/remote/deploy_kiosky_player.sh`;
- `scripts/remote/apply_c15_1_1_session_hotfix.sh`;
- scripts antigos `run_c*` que copiam/aplicam mudanças diretamente na placa.

Scripts historicos de release de `kiosky-player` tambem nao liberam OTA de
player na C18. `ALLOW_C18_FROZEN_PLAYER_RELEASE=1` e apenas bypass de
reproducao legada/lab, nao aprovacao de release C18-aware. Um pacote
`player-runtime` C18-aware exige contrato, gate e homologacao novos.

Todo comando C18 de update operacional deve declarar `--component totem-core`.
Comandos sem `--component` preservam default historico/legado do updater e nao
devem ser copiados para procedimentos C18.

## Stable E Producao

`stable` nao e apenas `channel=stable`. Antes de stable/batch, exigir gate de
promocao proprio, homologacao fisica, policy stable, `allow_prerelease=false`,
rollback definido, evidencia sanitizada e decisao explicita sobre imagem final.

CI, assinatura/attestation, bridge de updater e A/B de imagem sao hardening
futuro; nao fazem parte do OTA manual imediato.
