# C18 prod13 - RCA da janela inicial do player-runtime

Estado: causa reproduzida e correcao estreita validada na placa. A `prod13`
permanece saudavel no player embutido, mas nao deve virar referencia de
distribuicao. A sucessora deve ser a `prod14`.

## O que aconteceu

O timer real baixou o alvo C25B exato, verificou os artefatos e iniciou o health
do candidato. A tentativa terminou em `rc=11` e colocou o alvo em quarantine:
depois da espera de cinco segundos ainda houve sete amostras iniciais sem
classificacao, uma alem do limite estrito de seis.

O unico check vermelho foi `unclassified_media_bounded_to_startup`. Os demais
checks mostraram reproducao real: 30 amostras IPC e HW decode validas, frames
avancando, zero falha de midia, zero restart e zero fault novo de GPU/storage.
Nas primeiras sete amostras o status ainda nao classificava a midia; depois a
reproducao foi reconhecida normalmente.

## Isolamento da causa

Uma primeira repeticao com oito segundos usou o mesmo `kiosk.py` C25B embutido
na imagem, mas nao a arvore exata do release. Ela passou e confirmou que a
espera maior resolvia a classificacao inicial; por isso, so sustenta a causa
relacionada ao warm-up.

O ensaio seguinte usou a arvore exata C25B
`a7baf69dc249c39b2f6f8653873171fa8d799c814acbe8bc95c3eeed2c7136fc`.
Com a exposicao padrao de dez segundos, os quadros avancaram continuamente, mas
a coleta terminou logo apos o terceiro reinicio intencional do mesmo canario.
O segmento final tinha uma unica amostra e foi corretamente recusado como nao
comprovado. Isso revelou uma segunda causa no harness: uma janela de health de
30 segundos nao deve usar um canario que reinicia a cada dez segundos.

Na prova final, a duracao de exposicao do canario foi limitada ao maior valor
entre o default e toda a janela de observacao, incluindo warm-up e margem de
duas coletas. Para `8 + 30` segundos, o valor resultou em 40 segundos. A arvore
C25B exata passou com os mesmos limites estritos:

- 26 amostras classificadas como reproducao real e quatro amostras iniciais
  nao classificadas, dentro do limite estrito existente de seis;
- 30/30 IPC e HW decode esperados;
- frames avancando;
- zero falha de midia, restart, erro de filesystem ou fault novo de GPU;
- teardown limpo e servico principal restaurado.

Portanto as mudancas aprovadas sao adicionar `--startup-wait-sec 8` a unit
production e impedir que o canario reinicie dentro da propria janela de
avaliacao. Nao se altera o limite global de seis amostras/seis segundos, a
exigencia de progresso de quadros nem qualquer outro criterio de health.

## Consequencia

Essa unit e fixa na imagem e fica fora do payload `totem-core`. A correcao nao
pode ser entregue honestamente por OTA sobre a `prod13`; exige a sucessora
estreita `prod14`, preservando C20.14, C25B, kernel, boot e pilha de video.

O alvo C25B ficou em quarantine nesta gravacao apos a rejeicao fail-closed. Nao
se limpa essa quarantine para forcar uma nova tentativa. O flash da `prod14`
reinicia a topologia e permite provar timer, apply, noop, rollback para o player
embutido e reapply do alvo exato.

## Arquivos

- `pre.json`: snapshot anterior a tentativa;
- `timer-attempt-journal.txt`: execucao real do timer e rejeicao `rc=11`;
- `rejection/`: resultado e amostras da espera de cinco segundos;
- `startup-wait-8/`: repeticao aprovada com o `kiosk.py` exato, mas arvore
  embutida diferente do release;
- `exact-startup-wait-8-loop-boundary/`: arvore C25B exata, com progresso real
  e recusa no segmento final de uma amostra;
- `exact-startup-wait-8-windowbound/`: arvore C25B exata, canario cobrindo toda
  a janela e todos os checks aprovados.

Os dois ensaios exatos incluem `probe-tools.json` com a identidade do alvo e os
hashes das ferramentas, alem de `SHA256SUMS` para o conjunto curado.

Non-claims:

- esta evidencia nao aprova a `prod13` para distribuicao;
- os ensaios isolados nao aplicaram nem promoveram um release em `/data`;
- o roundtrip production completo continua pendente na `prod14`;
- nenhum criterio de deep-health foi afrouxado.
