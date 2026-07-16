# Decisão Central

## Veredito

GO para fechar o candidato OTA de homologação C21.21, sem blockers
remanescentes.

## Base

- Gates de fonte e pacote exato: `84/84`.
- Política stable recusou o pacote homologation com rc `41`.
- Apply, rollback e reapply governados: rc `0/0/0`.
- Placa final em C21.21, com C21.20 como previous.
- Player ativo, zero restart, Ethernet e Wi-Fi existente preservados.
- Política stable e timer de produção restaurados.
- Duas auditorias finais independentes emitiram GO para candidato/OTA.

## Limite Mantido

Não há aceite físico de AP aberto real porque nenhuma rede desse tipo estava
disponível. Esse teste continua pendente e não bloqueia o avanço das próximas
frentes M9, mas bloqueia qualquer claim de validação física completa de rede
aberta.

O campo legado `state.updated_at` não foi usado como prova temporal; a decisão
usa `last_operation`, `applied_at_utc`, symlinks e o snapshot runtime final.
