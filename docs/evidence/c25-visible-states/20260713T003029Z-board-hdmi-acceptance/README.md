# C25A - Aceite Visual Na Placa

Data UTC: `2026-07-13T00:30:29Z`.

## Alvo

- placa: `orangepizero3`, bancada de homologacao;
- pacote aplicado: `c25.1-visible-states-20260713T001600Z-7f204d7`;
- source commit: `7f204d725d4d10d4add85909a1a6d0fc99b23fd8`;
- payload SHA-256:
  `4407e407bae3badf041e109215cb16e15af6b70563f71c238c4d580ee95f1178`;
- canal do pacote: `homologation`;
- rollback preservado para:
  `c21.11-qr-pairing-20260712T021729Z-4068839`.

## Resultado Fisico

- apply local governado concluiu com sucesso;
- a policy original `stable` foi restaurada byte a byte apos o apply;
- timer de update e servico do player ficaram ativos;
- o player voltou com MPV ativo, primeiro frame aceito e midia avancando;
- o wizard real abriu, navegou ate Revisao e bloqueou conclusao incompleta;
- `Enter` manteve o fluxo no estado corrigivel, sem salvar parcialmente;
- cancelamento encerrou o wizard e devolveu a tela ao player;
- capturas reais nao apresentaram corte, overflow ou sobreposicao.

As telas `Pronto para salvar`, `Salvando configuracao`, `Configuracao salva`
e `Configuracao nao salva` foram renderizadas pelo codigo C25 no framebuffer
real da placa. Para preservar a configuracao valida da bancada, essa verificacao
visual nao executou uma nova escrita real de Wi-Fi/ambiente.

## Artefatos

- `01-opened.jpg`: wizard real na etapa Tela;
- `02-review-attempt.jpg`: Revisao incompleta;
- `03-enter-after-review.jpg`: correcao apos tentativa de concluir;
- `wizard-flow-contact-sheet.jpg`: jornada real resumida;
- `ready-to-save.jpg`: confirmacao final renderizada na placa;
- `saving.jpg`, `complete.jpg`, `save-failed.jpg`: estados do writer no
  framebuffer real;
- `save-states-board-contact-sheet.jpg`: estados do writer resumidos.

## Limites E Non-Claims

- nao houve promocao `stable` nem publicacao externa;
- nao houve nova escrita real de Wi-Fi/ambiente nesta sessao;
- imagens estaticas nao provam ausencia absoluta de flicker;
- o hook de recuperacao entre reinicios do player pertence a imagem e ainda
  requer a proxima imagem de referencia;
- estados dinamicos enquanto o player possui DRM pertencem a C25B
  (`player-runtime`) e continuam fora deste aceite;
- este aceite valida a fatia C25A `totem-core` em homologacao, nao uma imagem
  final de producao.
