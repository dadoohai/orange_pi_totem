# Consolidacao Da Baseline De Produto

Estado atual aceito: `prod14` + player-runtime C25B exato + totem-core C21.12
stable. A placa de homologacao ja validou C21.23 por OTA, com rollback e
reaplicacao, mas C21.23 ainda nao e a stable publica.

## Alvo

Gerar a sucessora `prod15` com:

- o mesmo kernel, U-Boot, DTB, pilha de video e player-runtime C25B da prod14;
- o totem-core correspondente ao conteudo C21.23, promovido antes como uma nova
  stable de identidade monotona;
- a correcao image-bound `c075a55` no avaliador de playback;
- policy e timers de producao, credencial nova e nenhuma configuracao real.

## Ordem Obrigatoria

1. Empacotar o conteudo C21.23 como nova stable, sem mudar seus arquivos.
2. Provar o pacote exato localmente na prod14: apply, rollback e reaplicacao.
3. Publicar a stable e provar timer real, no-op, rollback, restauracao e reboot.
4. Construir e auditar a prod15 ja com essa stable embutida.
5. Gravar a imagem em cartao limpo e validar jornada, player, OTA e reboot.
6. Somente entao declarar a prod15 como nova baseline de distribuicao.

## Limites

- C25B permanece o unico alvo autorizado de player-runtime; nenhum futuro alvo
  e liberado por inferencia.
- Portal cativo fisico/emulado e navegador restrito continuam pendentes.
- Associacao em AP aberto fisico continua pendente.
- Nenhuma imagem ou release vira referencia apenas por passar em validacao
  offline.

