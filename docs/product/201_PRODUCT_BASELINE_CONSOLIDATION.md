# Consolidacao Da Baseline De Produto

Estado atual aceito: imagem `prod19` + player-runtime C25B exato + totem-core
C26.16 atual/C26.15 anterior embutidos. A imagem foi construida, gravada e
passou na validacao fisica: wizard, playback, OTA, reinicio, restauracao com
corte real, revogacao, reativacao, desligamento e boot final. C26.17 e o
`totem-core stable` publico atual para a `prod19`; C21.24 permanece retida para
clientes antigos que recusam o contrato C26.

## Baseline anterior prod15

Gerar a sucessora `prod15` com:

- o mesmo kernel, U-Boot, DTB, pilha de video e player-runtime C25B da prod14;
- o totem-core C21.24 stable, cujo conteudo corresponde ao C21.23 validado;
- a correcao image-bound `c075a55` no avaliador de playback;
- policy e timers de producao, credencial nova e nenhuma configuracao real.

## Ordem Obrigatoria

1. [concluido] Empacotar o conteudo C21.23 como C21.24 stable, sem mudar seus arquivos.
2. [concluido] Provar o pacote exato localmente na prod14: apply, rollback e reaplicacao.
3. [concluido] Publicar a stable e provar timer real, no-op, rollback, restauracao e reboot.
4. [concluido] Construir e auditar a prod15 ja com essa stable embutida.
5. [concluido] Gravar a imagem em cartao limpo e validar jornada, player, OTA e reboot.
6. [concluido] Auditar a evidencia final e declarar a prod15 como nova baseline de distribuicao.

## Baseline atual prod19

Alvo exato:

- imagem `c18-hwdecode-prod-19-c26`, versao `c18.image-prod.19-c26`;
- SHA256
  `991ee90b8c042cbd1424c29f8c5062668c3125c999a24e32c01f14d9b4ec1ebc`;
- player-runtime C25B preservado;
- C26.16 atual e C26.15 anterior, com o mesmo contrato corrigido e identidades
  imutaveis distintas;
- policy/timers de producao, nenhuma configuracao real e nenhuma credencial de
  laboratorio embutida.

Fechamento:

1. [concluido] Reprovar C26.13/C26.14 e aceitar somente os dois slots corrigidos.
2. [concluido] Construir e auditar a imagem com `current` e `previous` compativeis.
3. [concluido] Gravar a imagem exata em cartao limpo e validar boot/onboarding.
4. [concluido] Provar reinicio e desligamento reais com estado preservado.
5. [concluido] Provar restauracao offline com corte, retomada e revogacao exata.
6. [concluido] Provar nova ativacao, token antigo recusado e playback saudavel.
7. [concluido] Provar C26.16 -> C26.15 -> C26.16 pelo updater governado.
8. [concluido] Publicar a mesma arvore executavel como C26.17 stable, presa a
   imagem e commit exatos.
9. [concluido] Provar na placa rollback para C26.16, download/aplicacao publica
   de C26.17, no-op manual e natural pelo timer, correlacao temporal do gate,
   playback e fallback C21.24 no cliente antigo.
10. [em fechamento] Congelar evidencias/documentos e concluir a auditoria
    independente post-publicacao.

Evidencia:
`docs/evidence/c26-local-recovery/20260719T162849Z-prod19-final-board-e2e/`.

## Limites

- C25B permanece o unico alvo autorizado de player-runtime; nenhum futuro alvo
  e liberado por inferencia.
- Portal cativo fisico/emulado e navegador restrito continuam pendentes.
- Associacao em AP aberto fisico continua pendente.
- A descoberta de releases pela API publica do GitHub falha de forma segura,
  mas divide uma cota por IP. Um indice stable sem polling da API ou credencial
  de leitura provisionada fica no roadmap antes de uma concentracao grande de
  placas sob o mesmo NAT.
- Nenhuma imagem ou release vira referencia apenas por passar em validacao
  offline.
- C26.15/C26.16 permanecem os slots embutidos da imagem. C26.17 e a unica
  promocao stable autorizada desta arvore; nenhuma versao futura e autorizada
  por inferencia.
- Restauracao local nao reinstala boot, kernel ou rootfs. Recuperacao integral
  continua no marco M11.
