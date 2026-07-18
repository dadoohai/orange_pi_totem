## Findings

1. **BLOCKER — o `previous` C26.5 é real, porém não é um rollback semanticamente seguro.**

   Reexecutei o código exato de `f1d0da9`, sem rede. A URL `https://api.example.com:`:

   - é aceita pelo contrato C26.5 em `real-dry-run`;
   - é aceita pelo writer antes da operação destrutiva;
   - é rejeitada pelo cliente de revogação do mesmo C26.5.

   A reprodução ponta a ponta chegou a:

   ```text
   local_complete=true
   active_config_exists_after_local_reset=false
   graveyard_config_exists=true
   pending_credential=true
   qr_revocation_precheck=rejected:PairingError:api_url_invalid
   ```

   Ou seja: a configuração aceita pela própria C26.5 permite mover a configuração ativa para o graveyard e concluir o reset local, mas depois impede a revogação. A C26.7 rejeita a mesma entrada antes de qualquer movimentação:

   ```text
   accepted=false
   error=product_reset_api_url_invalid
   active_config_exists_after_attempt=true
   graveyard_config_exists=false
   pending_credential_exists=false
   ```

   Isso é relevante após rollback: o updater troca C26.5 para `current` e C26.7 para `previous` ([totem_updatectl.py](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:4163)). Ambos continuam declarando `product-reset-v1`, permitindo novamente a ação.

   O falso-verde existe porque a validação offline comprova apenas presença, hash e rótulo das capabilities ([totem_core_image_embed.py](/home/builder/totem-os/orange_pi_totem/scripts/build/totem_core_image_embed.py:932)); ela não cruza a semântica writer/revogação do `previous`. O fluxo executa o writer antes do cliente de revogação ([totem_open_settings_session.sh](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_open_settings_session.sh:733)).

2. **PASS — identidade e integridade da imagem.**

   ```text
   tamanho   = 1971322880 bytes
   SHA-256   = fbaf93d0438567f5312363415c9e6778c74ca1e8e9642c6e46f79f02b5ad0a4d
   MBR       = partição Linux única, início 8192, 3842048 setores
   offset    = 4194304
   extensão  = 1967128576
   ```

   `offset + extensão` cobre exatamente a imagem. O marcador interno root:root `0644` confirma:

   ```text
   image_tag=c18-hwdecode-prod-18-c26
   image_version=c18.image-prod.18-c26
   BOARD=orangepizero3
   VERSION=25.11.1
   ```

   A partição foi copiada para `memfd` anônimo, sem mount. `e2fsck -f -n` passou nos cinco passes:

   ```text
   armbi_root: 35567/120240 files, 422389/480256 blocks
   exit=0
   filesystem state=clean
   ```

3. **PASS — commit/árvore e cadeia current/previous byte-real.**

   ```text
   HEAD = 50f808e412b3f70d8313ee731b63073a47458907
   tree = 04c8ea43811ae80bdab2a2dc38b04024ca100a07
   git fsck --full --strict --no-dangling = 0
   ```

   ```text
   current  -> C26.7 / 01464f8...
   payload  = 1369a5c7d04486f2d37fb11a6205ace25ae1efe2baf6bae3bd7d348ec82e5e5f

   previous -> C26.5 / f1d0da9...
   payload  = b8864cc913f6e7ca4562a0e3edfe9eb0ba55a6aef5019a47a0535397ba26f4df
   ```

   C26.7 tem 19 executáveis; C26.5 tem 18. Todos coincidem byte a byte com seus tarballs e com `git show <source_commit>:scripts/board/...`. Há diferenças reais: três scripts, health e o `totem_api_url_contract.py` exclusivo da C26.7. Os tarballs não têm duplicatas, links, dispositivos ou path traversal.

4. **PASS — adulteração é recusada e o enforcement funciona offline.**

   Em namespace sem rede, o verificador da imagem passou limpo em 219/219 checks. Em cópias anônimas:

   ```text
   byte alterado no previous          -> ok=false
   capability do previous alterada    -> ok=false
   source_commit do state alterado    -> ok=false
   payload comprimido alterado        -> passed=false
   SHA do manifesto alterado          -> passed=false
   source_commit não alcançável       -> passed=false
   ```

   Reexecuções adicionais offline:

   ```text
   C26 local recovery:          17/17
   updatectl/freeze/rollback:   92/92
   release-gate self-tests:     18/18
   ```

   Não usei o JSON declarando `85/85` como prova.

5. **Não-blockers no escopo restrito, mas contradições registradas.**

   - A policy interna é `stable`/`allow_prerelease=false`, enquanto ambos os slots são `homologation`. Isso bloquearia reaplicação desses manifestos e é blocker para promoção/distribuição, mas não é o blocker decisivo para o flash laboratorial do layout já embutido.
   - Commits e pacotes não têm assinatura, tag confiável ou `stable_promotion_evidence_sha256`; a proveniência é local e byte-exata, não autenticidade criptográfica. Fora do escopo de distribuição solicitado.
   - O `.ready.json` mantém `ready_for_manual_card_flash=false`; o builder grava esse valor incondicionalmente para production enquanto aguarda auditoria externa ([derive_c18_image_lab_1_hwdecode.py](/home/builder/totem-os/orange_pi_totem/scripts/build/derive_c18_image_lab_1_hwdecode.py:2155)).
   - Durante a auditoria apareceu um diretório documental não rastreado. Nenhum arquivo rastreado mudou; imagem e evidência são anteriores e conservaram seus hashes.

## Comandos principais

```bash
sha256sum "$IMG"
sha256sum -c "$IMG.sha256"
fdisk -l "$IMG"
sfdisk --json "$IMG"

git rev-parse HEAD HEAD^{tree}
git fsck --full --strict --no-dangling
git merge-base --is-ancestor 01464f8... 50f808e...
git merge-base --is-ancestor f1d0da9... 50f808e...

e2fsck -f -n /proc/self/fd/4
dumpe2fs -h /proc/self/fd/4
debugfs -R 'stat /data/core/totem/current' /proc/self/fd/4
debugfs -R 'stat /data/core/totem/previous' /proc/self/fd/4

git archive f1d0da9... scripts/board | tar -x -C /dev/shm/c26-audit/
unshare --user --map-root-user --net python3 <counterexample-harness>
```

## Veredito

**NÃO APTA para gravação na placa de laboratório.**

O filesystem, a identidade, os payloads e a distinção C26.7/C26.5 passam. O blocker é o `previous` C26.5: ele declara `product-reset-v1`, passa os gates, mas possui um contraexemplo reproduzível que conclui a etapa destrutiva local e depois recusa a revogação. Isso invalida justamente a segurança de rollback exigida. Nenhuma placa foi tocada e nenhum artefato foi editado.