# Consolidacao Da Baseline De Produto

Estado atual aceito: imagem `prod14` + player-runtime C25B exato. A stable
publica atual do totem-core e C21.24; a placa `prod14` adotou essa release pelo
timer real, passou por no-op, rollback, restauracao e reboot. A `prod15` foi
construida e auditada, mas ainda nao e baseline de distribuicao enquanto nao
for gravada e validada na placa.

## Alvo

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
5. [em andamento] Gravar a imagem em cartao limpo e validar jornada, player, OTA e reboot.
6. [pendente] Somente entao declarar a prod15 como nova baseline de distribuicao.

## Limites

- C25B permanece o unico alvo autorizado de player-runtime; nenhum futuro alvo
  e liberado por inferencia.
- Portal cativo fisico/emulado e navegador restrito continuam pendentes.
- Associacao em AP aberto fisico continua pendente.
- Nenhuma imagem ou release vira referencia apenas por passar em validacao
  offline.
