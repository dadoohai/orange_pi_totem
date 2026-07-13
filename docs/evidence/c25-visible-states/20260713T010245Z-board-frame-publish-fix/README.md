# C25.2 - Publicacao De Quadro Na Placa

Data UTC: `2026-07-13T01:02:45Z`.

## Motivo Da Rodada

A primeira auditoria do aceite C25A encontrou uma captura feita durante o
desenho progressivo do framebuffer. O layout final estava correto, mas a tela
viva podia expor partes do quadro enquanto retangulos e glifos ainda eram
gravados.

C25.2 passou a compor o quadro inteiro em memoria e publicar no framebuffer
somente depois da composicao terminar. Se a composicao falhar, o quadro visivel
anterior permanece intacto.

## Alvo Aplicado

- versao: `c25.2-frame-publish-20260713T004706Z-3267ecf`;
- source commit: `3267ecf8e68e557d93ca3a60bd995c0af6c18796`;
- payload SHA-256:
  `9841eb8b25883c9e91fd12dbb6f4aafb55bc14b3ea39eb91f41a982628116067`;
- canal: `homologation`;
- previous preservado:
  `c25.1-visible-states-20260713T001600Z-7f204d7`.

## Resultado

- self-test no host e na placa: passou;
- policy static: `68/68`;
- gate global limpo: `82/82`;
- sandbox apply/rollback/fallback/lock: passou;
- apply governado na placa: `rc=0`;
- policy original `stable`: restaurada com o mesmo SHA-256;
- timer e player: ativos; unidades falhas: zero;
- wizard real: abriu, chegou a Revisao, bloqueou conclusao incompleta,
  cancelou e voltou ao player;
- quadro estavel: dez capturas sucessivas ficaram byte-identicas;
- composicao de telas reais na placa: `0,153 s` a `0,183 s` na amostra.

O probe de estresse alternou vinte vezes dois quadros completos enquanto outro
processo lia `/dev/fb0`. Das 44 leituras, 34 coincidiram com um dos quadros
completos e 10 atravessaram a copia final. Isso confirma que o desenho
progressivo foi removido, mas tambem preserva o limite real: sem segundo buffer
fisico/page flip, a copia final nao e atomicamente sincronizada ao scanout.

## Artefatos

- `package-manifest.json`: identidade do pacote;
- `gates/`: gate global e sandbox;
- `apply/`: status antes/depois, log do apply e hashes da policy;
- `wizard/`: capturas do fluxo real e serie estavel;
- `frame-sampling/`: tempos e hashes das leituras concorrentes.

## Veredito E Limites

C25.2 esta aceita para continuar a homologacao do `totem-core`: o fluxo, o
guardrail e o retorno ao player passaram na placa, e o defeito de desenho
progressivo foi corrigido.

Non-claims:

- nao prova por camera ausencia absoluta de tearing/flicker de um frame;
- nao repete escrita real de Wi-Fi/ambiente;
- nao valida o hook do launcher, que entra na proxima imagem;
- nao valida C25B enquanto o player possui DRM;
- nao promove `stable` nem publica release externo.
