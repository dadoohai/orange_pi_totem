## Findings

1. **BLOQUEADOR — credencial aceita antes da remoção torna a revogação impossível depois.**

   O contrato, o QR real e o writer aceitam `api_key = "é" * 1500`. O writer de reset limita caracteres, não o tamanho serializado ([writer](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_config_writer_real.py:1486)). O pending produzido mede **9.255 bytes**, mas o revogador impõe limite de **8.192 bytes** ([limite](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_qr_pairing_client.py:63), [recusa](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_qr_pairing_client.py:228)).

   Antes dessa leitura, o fluxo já gravou intent/pending e passou para remoção do seed e moves de configuração, mídia, estado, spool e logs ([ordem destrutiva](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_config_writer_real.py:2233)). A revogação retorna rc inesperado; a sessão converte em `57`, enquanto a recuperação visual só abre para `55/56` e permite corrigir apenas Wi‑Fi ([sessão](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_open_settings_session.sh:782), [recovery](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:6644)).

   Outro vetor independente: `"😀" * 16` passa contrato/QR/writer, mas a serialização de `x-api-key` levanta `UnicodeEncodeError`, não capturado pelo transporte ([transporte](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_qr_pairing_client.py:316)).

   Impacto 24/7: configuração local antiga já bloqueada, ativação remota não revogada e nenhuma saída self-service.

2. **BLOQUEADOR — a helper canônica ainda aceita URLs sintaticamente inválidas antes da fronteira destrutiva.**

   A validação verifica HTTPS, porta, userinfo e fragmento, mas não a gramática do hostname ([helper](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_api_url_contract.py:18)). Probes próprios mostraram `contract_real_valid=true`, writer aceitando e endpoint derivado literalmente para:

   ```text
   https://%/search
   https://a..example.com/search
   https://<label-de-64-caracteres>.example.com/search
   https://api.example.com\bad/search
   ```

   Trace instrumentado sem I/O observou:

   ```text
   capture_and_validate_credential
   write_intent
   write_pending
   prepare_graveyard
   remove_seed
   move_domain x5
   move_last_settings
   ```

   Portanto, a afirmação “qualquer URL inválida é recusada antes de remover configuração/identidade” é falsa.

3. **MÉDIA — o verde atual é não composicional e contém divergências observáveis.**

   - Para `https://[2001:db8::1`, helper/writer/QR recusam, mas o contrato `real-dry-run` lança `ValueError`: depois de capturar o erro canônico, chama novamente `urlparse()` sem proteção ([função](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_config_contract_validate.py:329), [chamada](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_config_contract_validate.py:542)).
   - O QR real do wizard não usa a helper; aceita userinfo, porta zero, fragmento e URLs acima de 2.048 bytes, além de remover silenciosamente query aceita pelo contrato ([QR visual](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:6034), [normalização](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:6132)).
   - O próprio self-test QR marca como válido `REAL_DEVICE_KEY_FOR_SELF_TEST...` e `api_token_id="token-self-test"`, mas o handoff real rejeita ambos por placeholder e UUID inválido ([fixture](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_setup_visual_wizard.py:9682), [contrato](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_config_contract_validate.py:524)).

   Assim, o release gate verde não prova QR → handoff → writer → reset.

## Verificações positivas

- Valores atualmente reconhecidos como inválidos — HTTP, userinfo, fragmento, porta inválida, whitespace, chave curta/placeholder/control e UUID inválido — param antes de intent/pending/moves, inclusive na reentrada anterior à captura. Apenas o diretório privado do journal pode ser preparado antes; não há remoção.
- Não encontrei fail-open adicional no journal: intent, pending, tombstone, receipt e `gc-pending` têm ordem sincronizada. Nos bloqueadores acima, porém, a reentrada fica **fail-closed sem liveness**.
- **C26.5 passa como `previous` estático.** O tar contém 13 Python compiláveis e 5 shells com `bash -n` verde; nenhum arquivo importa ou declara a nova helper. O updater a trata como opcional ([updatectl](/home/builder/totem-os/orange_pi_totem/scripts/board/totem_updatectl.py:253)) e o builder a exclui deliberadamente do slot anterior ([embed](/home/builder/totem-os/orange_pi_totem/scripts/build/totem_core_image_embed.py:128)).
- Leitura direta e mountless do ext4 da prod18 confirmou:

  ```text
  current  -> releases/c26.7-local-recovery-20260718-01464f8-actions
  previous -> releases/c26.5-local-recovery-20260718-f1d0da9-actions
  current helper: presente, SHA 15c9e084...
  previous helper: ausente
  ambos: product-reset-v1 + totem-actions-v1
  ```

- O tar C26.7 bate o manifesto: `1369a5c7...`; seus 19 binários são byte a byte iguais ao commit `01464f8`. Não há diff nos arquivos relevantes até o HEAD `50f808e`.
- A imagem real mede 1.971.322.880 bytes e confere com SHA-256 `fbaf93d...`. A própria evidência mantém `ready_for_manual_card_flash: false` ([artifact-ready.json](/home/builder/totem-os/orange_pi_totem/docs/evidence/c26-local-recovery/20260718T230211Z-prod18-c26-build/artifact-ready.json:14)).

## Comandos/probes principais

```bash
git diff --quiet 01464f8..HEAD -- scripts/board
sha256sum releases/core-updates/c26.7-local-recovery-20260718-01464f8-actions/*.tar.gz
sha256sum /home/builder/totem-os/armbian-build-v25.11/output/images/*prod-18-c26*.img
tar -tzf releases/core-updates/c26.5-local-recovery-20260718-f1d0da9-actions/*.tar.gz
```

Probe em memória decisivo:

```python
key = "é" * 1500
candidate = writer.build_synthetic_candidate()
candidate["api_key"] = key
# contract valid=True; writer reset aceita
# pending JSON=9255 bytes; QR máximo=8192 bytes
```

O status Git inicial e final permaneceu idêntico; nenhum arquivo, rede, systemd ou placa foi alterado.

## Veredito limitado

**NO-GO: há blocker antes de gravar a prod18 na placa de laboratório.**

Identidade do artefato e C26.5 como `previous` passam. A fronteira destrutiva e a consistência contrato–writer–QR reprovam; interrupção permanece fechada, mas pode deixar o usuário sem recuperação local utilizável.