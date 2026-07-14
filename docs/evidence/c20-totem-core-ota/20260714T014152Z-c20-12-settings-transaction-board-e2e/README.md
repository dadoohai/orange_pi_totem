# C20.12 Settings Transaction Board E2E

C20.12 foi exercitado na placa real com QR de producao, gravacao governada,
rollback e reaplicacao do pacote exato. Esta rodada revelou tres refinamentos
necessarios antes da proxima referencia: prefill transitorio, limpeza completa
na troca de fonte privada e posse do framebuffer durante toda tela visivel.

- Versao: `c20.12-settings-transaction-20260713T235714Z-bfb0d04`
- Payload SHA256: `75d757e41a8d8fb0031e99a2ee95f9895381ca37678962f76d3280a1786e2c02`
- Release gate: verde, `82/82`
- Placa: `orangepizero3`, imagem prod12
- Canal do pacote: `homologation`
- Policy final da placa: `stable`, `allow_prerelease=false`, restaurada byte a byte

## Resultado

1. O wizard abriu pela unit de producao e segurou os locks esperados.
2. O QR real foi exibido, autorizado e converteu a sessao em candidata valida.
3. A configuracao foi escrita com validacao antes/depois, rename atomico e fsync.
4. Os valores privados nao apareceram nos status publicos. O temporario do QR
   foi removido; a coleta nao mediu o temporario anterior derivado da
   configuracao ativa, que uma auditoria posterior mostrou poder permanecer
   ate a proxima sessao ou reinicio.
5. O player voltou com um unico MPV, `v4l2request-copy` e zero reinicios.
6. O rollback para C20.10 trocou o componente com sucesso e manteve byte a byte
   o contexto auxiliar medido; a configuracao ativa nao foi medida nessa etapa.
7. A reaplicacao do mesmo C20.12 passou e restaurou a policy original.
8. Uma sessao posterior cancelada nao chamou writer e preservou hash e mtime de
   `/data/config/config.json` byte a byte. Ela reescreveu o contexto auxiliar
   durante o prefill, comportamento corrigido somente na sucessora.

## Saude De Playback

As tres janelas canonicas de 45 segundos ficaram verdes:

| Momento | Amostras | Midias com progresso | Reinicios | GPU/disco |
| --- | ---: | ---: | ---: | ---: |
| depois do save | 40 | 5 | 0 | 0 |
| depois do rollback | 36 | 4 | 0 | 0 |
| depois da reaplicacao | 37 | 3 | 0 | 0 |

Uma coleta exploratoria de 30 segundos cortou uma transicao na borda e ficou
vermelha; a invocacao canonica de 45 segundos classificou a borda corretamente
e observou progresso continuo. Ela nao foi usada como evidencia positiva.

## Evidencias

- `board/session-status.json`, `handoff-status.json` e `writer-status.json`:
  fechamento da sessao real e escrita atomica.
- `board/cancel-session-status.json` e `cancel-active-*`: cancelamento sem
  mutacao da configuracao ativa.
- `board/context-before-rollback.sha256`, `context-after-rollback.sha256`,
  `rollback.log`, `status-after-rollback.json`, `reapply.log` e
  `status-final.json`: troca reversivel do componente, contexto auxiliar
  preservado e reaplicacao exata. Nao provam preservacao da configuracao ativa.
- `health/`: resumos publicos das tres janelas verdes.
- `visual/`: telas reais do framebuffer, SVG gerado e renderizacao independente.
- `gates/c18-ota-release-gate.json`: gate integral reproduzido.

## Achado Visual Aberto

O SVG final gerado e valido e renderiza completo fora da placa, mas duas
capturas estaveis de `/dev/fb0` mostraram regioes pretas e texto cortado depois
de navegacoes. Um experimento controlado posterior confirmou que o console de
texto repintava o framebuffer durante as teclas: a mesma tela ficou limpa com
o tty em modo grafico. O achado nao alterou a transacao nem a reproducao, mas
C20.12 nao deve ser tratado como referencia visual final.

## Non-Claims

- Nao e promocao `stable` deste pacote de homologacao.
- Nao valida Wi-Fi real; a placa usou Ethernet e o modo de bancada explicito.
- Nao substitui soak de 24 horas nem campanhas de producao anteriores.
- Nao declara prod13 pronta.
- Nao prova que `/data/config/config.json` ficou byte-identico durante o
  rollback/reapply, pois esse arquivo nao foi medido nessa parte da rodada.
- O codigo e o QR registrados pertencem a uma sessao de laboratorio expirada
  em `2026-07-14T01:33:04.053Z`; sua preservacao foi aceita nesta bancada e nao
  estabelece precedente para versionar sessoes futuras ainda validas.
