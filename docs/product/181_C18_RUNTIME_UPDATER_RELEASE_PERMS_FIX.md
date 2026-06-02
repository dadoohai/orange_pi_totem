# 181 — C18.RUNTIME.3 Updater Release-Permissions Fix (remote updates never took effect)

> Regras atuais de atualizacao C18 estao consolidadas em
> [docs/UPDATE_CONTRACT.md](../UPDATE_CONTRACT.md). Este documento permanece
> como historico/evidencia de bugfix.

Rodada de **correcao** do mecanismo de auto-update (C14 pull updater). Durante a
validacao em hardware (C17.4.2) descobriu-se que **publicar uma release no GitHub
NAO troca o player que roda na placa** — a release e baixada e "aplicada", mas o
player continua rodando `/opt`. Causa: permissoes do diretorio de release. Fix
**em repo**, validado com teste local; **sem placa, sem release, sem imagem**.
Validacao em hardware/imagem permanece obrigatoria.

## Sintoma (validado na placa)

- `totem-update-agent.timer` (OnBootSec=10min, OnUnitActiveSec=6h, Persistent)
  roda `totem-updatectl apply-github-latest --repo dadoohai/kiosky-player` (C14.1.1).
- Logs confirmam: baixa manifest, valida SHA256, extrai release, troca `current`,
  reinicia `kiosky-player.service`, e reporta `apply_success`.
- **Porem** o launcher loga, em todo boot/restart:
  `data app dir present but kiosk.py missing; falling back` /
  `kiosk_source=fallback kiosk_dir=/opt/totem/kiosky-player`.
- Resultado: a placa roda `/opt` (imagem), nunca a release baixada em
  `/data/apps/kiosky-player/current`.

## Causa raiz (validada com namei + teste como usuario totem)

```
namei -l /data/apps/kiosky-player/current/kiosk.py
  drwxr-xr-x root root  releases
  drwx------ root root  homolog-20260511-202109-c71318a   <-- 0700 root:root
  -rw-rw-r-- root root  kiosk.py
runuser -u totem -- test -f .../current/kiosk.py  => TOTEM_SEES_MISSING
```

O servico roda como usuario **`totem`** (`User=totem`, `Group=totem`,
`ReadWritePaths=/data /tmp`, `ReadOnlyPaths=/opt/totem`). O updater extrai o
diretorio da release com modo **0700 root:root** (criacao sob umask restritivo no
processo do agente). `totem` **nao consegue atravessar** o diretorio => o teste
`[ -f current/kiosk.py ]` do launcher falha => fallback para `/opt`. Nao e race,
nao e namespace/sandbox (`/data` e ReadWrite e o arquivo existe para root); e
**permissao de diretorio**.

## Correcao

`scripts/board/totem_updatectl.py`:
- Novo helper `_make_world_traversable(root)` = equivalente a `chmod -R a+rX`:
  diretorios e arquivos ja executaveis ganham `a+x`; todos ganham `a+r`. **Nao**
  concede `write`, **nao** adiciona execute em arquivos nao executaveis.
- Chamado ao fim de `_safe_extract_tar(...)`, normalizando toda release extraida
  (inclusive o proprio diretorio de versao). Assim qualquer usuario de servico
  (`totem`) consegue atravessar/ler a release => o launcher passa a escolher
  `/data/apps/current`.
- `import stat` adicionado.

Teste: `scripts/qa/c18_runtime_3_release_perms_test.py` reproduz a condicao
(umask 077 + membros de tar 0700/0600), extrai e afirma:
- diretorio da release e subdiretorio ficam `o+rx`;
- arquivos ficam `o+r`;
- **nao** ha `world-write`; arquivo nao executavel **nao** ganha execute.
Regressao C17.9 (`c17_9_update_channel_policy_test.py`): 13/13 OK.

## Alcance / honestidade (importante)

- O updater faz parte da **IMAGEM** (`/opt/totem/bin/totem-updatectl`), nao da app
  `kiosky-player`. O updater C14 atualiza a APP, **nao a si mesmo**. Logo, este fix
  so chega as placas existentes via **nova imagem** (ou, futuramente, via
  totem-core remote update C17.5+, ausente em C17.4.2). Placas C17.4.2 atuais
  precisam de re-imagem para corrigir permanentemente.
- **Remediacao interina (opcional, manual, fora desta rodada)** para uma placa ja
  no campo, sem re-imagem: tornar as releases existentes atravessaveis
  (`chmod -R a+rX /data/apps/kiosky-player/releases`) e reiniciar o player; porem
  releases futuras criadas pelo updater nao corrigido voltariam a 0700. Nao
  aplicado nesta rodada.
- Mesmo com este fix, publicar release exige confianca de homologacao: a placa
  C14.1.1 **nao tem channel gating** (pega a latest por component+device), entao
  qualquer release latest seria puxada. Channel governance so existe a partir de
  C17.9.

## Status

- `c18_runtime_3_status=fixed_in_repo_test_validated`
- `updater_code_changed=true`, `app_player_changed=false`
- `board_touched=false`, `release_published=false`, `image_built=false`
- `reaches_existing_boards_only_via_new_image=true`
- `hardware_validation_required=true`
- `no_channel_gating_on_c17_4_2=true` (governanca de canal so em C17.9+)

## Relacao com 179/180

- 179: diagnostico (duracao OK; repeticao = media_load_failed -> restart).
- 180: fix da repeticao (soft-retry) no `kiosky-player`.
- 181 (este): fix do updater para que QUALQUER release (inclusive a do 180)
  realmente passe a rodar nas placas. Sem 181, publicar o 180 nao mudaria as
  placas.
