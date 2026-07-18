# Imagem candidata prod16 C26

Escopo: candidata para uma unica placa de bancada, sem claim de baseline final
ou producao.

## Artefato

- tag: `c18-hwdecode-prod-16-c26-candidate`
- versao: `c18.image-prod.16-c26-candidate`
- repo: `cdab0fedefdc8776a9d1fbb0e0974fab9980181f`
- tamanho: `1971322880` bytes
- SHA-256: `18c1b42c57809b704820f5dfa383fb05a3d254d50745cb217440f241c75e1168`
- totem-core embutido: `c26.3-local-recovery-20260718-d0363b7-actions`

O build de producao foi fail-closed. Uma primeira tentativa foi recusada
porque o link `current` ainda vinha do manifesto da imagem anterior e o health
gravava somente uma capacidade. O gerador foi corrigido no commit `cdab0fe`,
testado e reconstruido. Somente a segunda imagem, com validacao offline verde,
foi promovida para o nome final.

`artifact-ready.json`, `build_manifest.json`, `offline_validation.json` e
`build.log` estao ligados por hashes. O arquivo de imagem nao e commitado.

## Veredito independente

GPT-5.6 Sol `xhigh` recalculou o hash, abriu uma copia descartavel do ext4,
rodou `e2fsck -f -n`, comparou os 18 binarios, units, drop-in, symlink,
capabilities, pacote e commits. Veredito:

`SAFE-TO-FLASH-FOR-BOARD-VALIDATION: SIM`

Sem blocker para uma placa de bancada. Hardware, HDMI, boot real, rede,
playback e os fluxos C26 continuam pendentes e sao a finalidade da regravacao.
O `ready_for_manual_card_flash=false` do sidecar permanece como non-claim
conservador de producao; a autorizacao limitada vem da auditoria independente
registrada, nao do nome do arquivo.
