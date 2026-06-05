# C18 - Autorizacao De Update E Health Gates

Nota operacional curta para dev/IA retomar a linha C18 sem abrir caminho
acidental para update inseguro. Em caso de divergencia, o contrato vigente esta
em `docs/UPDATE_CONTRACT.md`; o baseline live fica em
`docs/product/189_C18_OTA_READINESS_GATE.md`.

## Modelo De Classes

| Classe | Inclui | Caminho de update |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, validadores, helpers de Wi-Fi/config, settings | OTA C18 manual, operador presente |
| `player-runtime` | `kiosk.py`, launchers do player, logica de start, flags de MPV, timing/sync/duracao/playlist | congelado no fluxo publico; so imagem ou thaw lab explicito |
| `media-system` | MPV, ffmpeg, hwdecode, panfrost, wrapper, HDMI/display, kernel, DTB, U-Boot, BSP | nova imagem + homologacao |
| `field-data` | config real, seed, midia, cache, playlist, estado local | fluxo operacional em `/data`; nao e release de software |

## O Que Pode Atualizar Agora

OTA C18 comum pode atualizar somente `totem-core`.

Condicoes minimas:

- comando explicito com `--component totem-core`;
- policy presente em `/data/updates/policy.json`;
- `device_track="c18-hwdecode"`;
- `allowed_components=["totem-core"]`;
- `allow_downgrade=false`;
- canal exato (`lab`, `homologation` ou `stable`), sem heranca entre canais;
- dry-run aprovado antes do apply real;
- rollback definido antes do apply;
- evidencia sanitizada, sem segredo, URL real, SSID, IP, MAC, DNS ou config
  privada.

## O Que Esta Congelado

Ficam congelados fora do OTA comum:

- `kiosky-player`;
- `player-runtime`;
- `kiosk.py`;
- `kiosky_service_launcher.sh`;
- `totem-kiosky-launcher.sh`;
- MPV, ffmpeg, libplacebo, hwdecode e wrapper de MPV;
- units/timers systemd, updater, policy de fabrica, kernel, DTB, U-Boot, BSP;
- qualquer mudanca que precise de reboot para ser verdadeira.

Tentativas publicas de apply/rollback de `kiosky-player` ou `player-runtime`
devem continuar falhando com `rc=44` enquanto nao houver thaw explicito.

## Quem Autoriza

O device autoriza tecnicamente pelo conjunto:

- manifest da release;
- policy local do device;
- canal do device;
- lista `allowed_components`;
- features exigidas pelo updater;
- gate offline de release;
- dry-run que seleciona exatamente a release esperada.

O humano autoriza operacionalmente a janela de update. Sem decisao humana
explicita, nao gerar imagem de producao, nao publicar stable, nao ligar
auto-pull, nao regravar cartao, nao fazer poweroff/reboot operacional e nao
descongelar `player-runtime`.

Para stable, a autorizacao humana precisa vir junto de evidencia JSON aprovada
`dadooh.c18.stable_promotion.v1` e do bypass controlado
`ALLOW_C18_STABLE_PROMOTION=1`. Isso nao substitui homologacao fisica.

## Health, Deep-Health E Soak

`service health` e o minimo operacional:

- `kiosky-player.service` ativo;
- `NRestarts_delta=0`;
- processo MPV esperado vivo;
- apply nao reiniciou/parou o player.

Isso prova que o servico esta de pe, mas nao prova playback nem decode.

`deep-health` prova playback curto e decode:

- MPV real pela stack C18 (`/opt/totem/hwdecode/bin/mpv` ou wrapper);
- `hwdec-current=v4l2request-copy`;
- `vo-configured=true`;
- progresso de frame observado, nao apenas `time_pos`;
- transicoes/aliases observados quando houver playlist suficiente;
- `media_load_failed=0`;
- `mpv_restart=0`;
- `ipc_timeout=0`;
- `panfrost_faults=0`;
- `mmc_timeout_reset=0`.

O coletor preferencial e
`scripts/board/c18_playback_health_collect.py`, gerando artefatos publicos
sanitizados e `dadooh.c18.playback.deep_health.v1`.

Na linha C18 atual, progresso de frame estimado e evidencia obrigatoria para
aprovar playback de video. Se uma classe futura de midia legitima nao expuser
`estimated-frame-number`, ela deve ganhar health contract proprio; nao voltar ao
criterio inseguro de aprovar apenas por `time_pos`.

`soak` e endurance, nao smoke test. Para producao/batch, o soak esperado e uma
janela longa, tipicamente 24h, com a mesma config candidata, aprovando:

- restarts zero;
- panfrost/mmc/I-O/ext4 sem erros;
- `media_load_failed=0`;
- `hard_resync=0`;
- temperatura sem throttle;
- RSS estavel;
- CPU com p95/pico registrado;
- volume de log aceitavel.

## Status Atual

Baseline de laboratorio/delivery registrado em 2026-06-05:

- imagem golden: `c18-hwdecode-lab-1o`;
- sha256:
  `07f9ee4f3f870f0fdb083eba7992a24b166939c768fc962e44a18d781117b164`;
- estado: `final_image=false`, nao stable, nao batch de producao;
- OTA manual de `totem-core` validado com apply, rollback e reapply;
- release de referencia aplicada:
  `c18.ota-core-config-missing-20260603T150429Z-2a7a327`;
- timer de update desligado;
- auto-pull fora de escopo;
- `kiosky-player` e `player-runtime` ainda congelados no fluxo publico;
- player esperado pelo fallback da imagem, com HW decode
  `v4l2request-copy`, `vo-configured=true`, `NRestarts=0`;
- deep-health real em hardware validado apos config real:
  progresso de frame presente/avancando, `media_load_failed=0`,
  `mpv_restart=0`, panfrost/mmc/ext4 `0`.
- evidencia auditavel da 1o:
  `docs/evidence/c18-update-validation/20260605T003747Z-1o-service-deep-health/`.
- ensaio lab-only de `player-runtime` em hardware validado com pacote local
  `homologation` do commit `3af11d4`, `data_root` temporario em `/tmp`,
  candidato isolado com canario local, `github_used=false`,
  `network_required=false`, apply `rc=0`, rollback `rc=0`, reconcile `rc=0`,
  CLI publico ainda congelado com `rc=44`, e deep-health do servico real
  aprovado apos restart. Esse marco foi registrado como resumo operacional da
  sessao; antes de qualquer ensaio persistente em `/data`, a evidencia deve ser
  preservada em artefatos sanitizados e auditaveis, nao apenas em prosa.

## Gates Antes De Thaw Do Player-Runtime

Antes de qualquer thaw de laboratorio:

- `scripts/qa/c18_player_runtime_release_gate.py` precisa passar no pacote real;
- pacote nao pode ser `stable`;
- payload nao pode tocar config, seed, arquivos de imagem/controle, paths
  absolutos, symlinks, hardlinks, traversal ou arquivos com cara de segredo;
- `kiosk.py` precisa compilar e preservar wrapper/HW decode no caminho efetivo
  ate `subprocess.Popen(args, ...)`;
- apply lab-only deve usar
  `scripts/qa/c18_player_runtime_lab_apply.py` com flags e env vars lab-only;
- rollback/reconcile lab-only deve usar
  `scripts/qa/c18_player_runtime_lab_rollback.py` com flags e env vars
  lab-only (`C18_PLAYER_RUNTIME_LAB_ROLLBACK=1` + `--lab-only-rollback`) antes
  de qualquer ensaio persistente em `/data`;
- `reconcile --component player-runtime` de manutencao deve exigir
  `--allow-player-runtime-maintenance` e `C18_PLAYER_RUNTIME_RECONCILE=1`; o
  boot da imagem pode passar essa autorizacao explicitamente, mas o comando nao
  deve ficar solto como API publica mutavel;
- o proximo ensaio persistente deve guardar manifest/payload SHA,
  `playback-samples.tsv`, sidecars `deep-health-*.json` e
  `playback-deep-health-public.json` sanitizados, junto de um resumo que prove
  apply, adocao pelo launcher, rollback real e fallback esperado;
- antes de commitar essa evidencia, rodar
  `scripts/qa/c18_player_runtime_evidence_gate.py --run-dir <dir>` para aplicar
  allowlist de arquivos e scan de vazamento;
- health de candidato deve usar runner lab-only isolado, sem GitHub, sem timer,
  sem auto-pull e sem policy permanente;
- quando nao houver API real no runner, o health de candidato deve usar canario
  offline explicito (`--canary-media`) sob `/tmp` ou `/data/media`, com playlist
  temporaria isolada e sem publicar o path em evidencia publica;
- em Orange Pi/DRM, validacao de candidato pode exigir janela controlada com o
  player vivo parado para liberar DRM master; isso e validacao de laboratorio,
  com restart do servico ao final, nao thaw publico nem auto-pull;
- launcher deve adotar `/data/player-runtime/current` somente com marker
  `.release_verified.json` valido, hashes conferidos, deep-health aprovado e
  identidade nao quarentenada;
- falha, marker ausente/corrompido ou hash divergente deve cair para
  `/opt/totem/kiosky-player`.

Passar esses gates ainda nao libera producao; apenas permite teste controlado
de laboratorio.

## Gates Antes De Stable

Antes de qualquer stable ou batch:

- promocao explicita `lab -> homologation -> stable`;
- homologacao fisica na placa-alvo;
- policy stable com `allow_prerelease=false`;
- evidencia `dadooh.c18.stable_promotion.v1` aprovada;
- rollback testado e documentado;
- deep-health aprovado apos update;
- soak de endurance aprovado quando a mudanca tocar player/runtime/imagem;
- decisao humana explicita sobre imagem final;
- auditoria de privacidade das evidencias.

CI, assinatura/attestation, bridge de updater, A/B de imagem e auto-pull sao
hardening futuro. Nao assumir que existem na linha C18 atual.
