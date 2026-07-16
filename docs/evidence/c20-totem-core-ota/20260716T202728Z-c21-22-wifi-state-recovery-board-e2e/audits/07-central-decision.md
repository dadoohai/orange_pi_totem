# Decisao Central

## Veredito

GO para fechar a candidata OTA de homologacao C21.22 para M9 itens 4, 5 e 6,
sem blockers remanescentes.

## Base

- Gates de fonte e pacote exato: `84/84`.
- Suite estatica pos-documentacao: `81/81`.
- Replay: 12 cenarios, 53 assertions e 58 telas.
- Galeria completa: 119 PNG + 119 SVG; previews do pacote instalado: 20 SVG.
- Policy stable recusou o pacote homologation com rc `41`.
- Apply, rollback e reapply governados: rc `0/0/0`.
- Placa final em C21.22, com C21.21 como previous.
- Hashes dos arquivos instalados batem com o pacote.
- Player ativo, zero restart, Ethernet e Wi-Fi preservados.
- Policy stable e timer de producao restaurados.
- Auditorias finais de codigo/claim e evidencia emitiram GO.

## Analise Dos Achados

A primeira auditoria de evidencia encontrou somente uma lacuna de arquivo: a
pasta guardava amostras, nao a galeria e os previews completos. O conjunto foi
ampliado para 119/119 telas e 20/20 previews; a reauditoria confirmou
integridade e removeu o finding.

A observacao de checksum da auditoria de codigo foi produzida antes da
regeneracao final. No estado decidido, `SHA256SUMS` cobre todos os arquivos
anteriores a esta decisao e valida sem divergencia. Ele sera regenerado depois
da inclusao dos pareceres e desta decisao.

## Limites Mantidos

O fechamento nao prova portal cativo, navegador temporario, associacao fisica
em AP aberto, falhas Wi-Fi reais, aceite por framebuffer interativo, stable,
release publico ou nova imagem. O campo legado `state.updated_at` nao foi usado
como prova; a decisao usa manifest, payload, `last_operation`, symlinks,
arquivos instalados e snapshots runtime.
