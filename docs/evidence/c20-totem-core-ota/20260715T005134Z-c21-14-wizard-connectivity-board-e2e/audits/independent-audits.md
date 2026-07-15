# Auditorias independentes

## Semantica de rede

Veredito: aprovado, zero blocker.

O auditor exigiu e revalidou identidade exata da interface entre rota, device e
conexao ativa. Mismatch de interface, rotas concorrentes, locale inesperado,
campos extras, sinal invalido e leitura expirada falham fechados. Estados
antigos do wizard nao alimentam o badge.

## UX e evidencia visual

Veredito: aprovado, zero blocker.

O auditor encontrou inicialmente PNGs truncados e indicador sem refresh durante
inatividade. A rodada regenerou renders completos e adicionou repaint sincrono
a cada cinco segundos. A reauditoria aprovou paisagem, retrato, rodape,
hierarquia, simbolos e ausencia de overflow.

## Operacao 24/7

Veredito: aprovado, zero blocker.

Um snapshot e substituido em memoria; nao existem fila, thread ou historico. O
fallback usa dois slots e as telas temporarias usam anel de 64 arquivos.

Nenhum auditor editou o repositorio ou a placa.

## Auditoria final do estado commitado

Veredito: reprovado, dois blockers.

1. Sem rota default, uma unica conexao ativa ainda podia herdar o estado
   `full` cacheado e mostrar internet `online`.
2. O contador de request IPC do fallback MPV crescia sem teto enquanto o
   processo permanecesse aberto.

Riscos nao bloqueantes: a leitura sequencial podia consumir ate quatro timeouts
e a captura fisica cobriu somente paisagem com Ethernet. O auditor confirmou
self-tests, policy static `81/81`, pacote byte-identico ao commit, hashes,
roundtrip da placa, ausencia de segredo e ausencia de overclaim stable.

Decisao central: os dois blockers foram aceitos. C21.14 ficou imutavel e
supersedida; a correcao exige nova candidata. O primeiro passa a exigir rota
default verificada para qualquer estado positivo. O segundo usa contador
circular fixo. O mesmo ajuste limita toda a coleta a um unico orcamento de
tempo, eliminando a composicao de quatro timeouts.
