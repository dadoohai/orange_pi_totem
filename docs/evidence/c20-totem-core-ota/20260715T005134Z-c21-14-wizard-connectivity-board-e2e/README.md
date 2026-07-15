# C20.16 / C21.14 - Indicador de conectividade

## Alvo

- versao: `c21.14-wizard-connectivity-20260715T003032Z-4835ca8`;
- componente: `totem-core`;
- canal: `homologation`;
- source commit: `4835ca8520370582f273cd0afd53b032dcc48fb3`;
- payload SHA-256:
  `f324098458e0c50e472af0902f9216ef82d4c99dc1c1975976f3af07f186a8f6`.

## Resultado

`passed=true`. O wizard mostra um indicador discreto ao lado da hora:

- Ethernet ou Wi-Fi e a intensidade do Wi-Fi;
- `OK` para internet disponivel, `!` para limitado/portal, `X` para offline e
  `?` para estado incerto;
- cor e simbolo, sem texto tecnico na tela.

O estado `online` exige coerencia entre a interface da rota, o device conectado,
a conexao ativa e o estado `full` cacheado pelo NetworkManager. Ambiguidade,
timeout ou leitura malformada falham fechados para `?`.

O release gate passou `84/84`; o sandbox passou apply, lock e rollback. Na
placa, a politica stable bloqueou corretamente o pacote homologation com
`rc=41`. O harness de bancada parou o timer, usou politica homologation apenas
durante cada apply e restaurou os bytes stable antes de continuar. Apply,
rollback e reaplicacao passaram com `rc=0`; configuracao, contexto e policy
terminaram com os mesmos hashes, timer ativo e zero restart do player.

A captura real confirmou `Ethernet + OK`, data/hora de Sao Paulo, navegacao ate
Revisao, cancelamento e retorno ao player. O deep-health final passou com um
MPV, hardware decode esperado, frames avancando e zero restart.

## Contrato 24/7

- um unico snapshot em memoria, substituido a cada leitura;
- callback e deadline unicos, sem fila ou thread;
- framebuffer sem arquivo por refresh;
- fallback MPV limitado a dois arquivos temporarios;
- telas temporarias do wizard limitadas a um anel de 64 SVGs;
- sem SSID, credencial, probe externo, speedtest, rescan ou historico.

## Incidente Contido

Antes do apply, uma chamada incorreta do helper SCP com dois arquivos
sobrescreveu somente a copia de trabalho local do payload pelo manifest. O blob
correto permaneceu intacto no Git. Ele foi restaurado de `HEAD`, conferido pelo
SHA-256 esperado e transferido novamente. Nenhum apply ocorreu antes dessa
verificacao; o roundtrip usou o payload correto.

## Limite Honesto

O estado de internet vem do cache do NetworkManager; nao e speedtest nem probe
externo em tempo real. O caminho Wi-Fi positivo foi coberto por testes e galeria,
mas a placa desta rodada estava em Ethernet. C21.14 e candidata de homologacao:
nao promove stable, nao publica release e nao altera player-runtime, imagem,
kernel, midia ou configuracao do cliente.

## Conteudo

- `package/`: identidade exata do pacote;
- `gates/`: release gate e sandbox;
- `board/transaction/`: bloqueio de canal, apply, rollback, reapply e invariantes;
- `board/visual/`: capturas reais e fluxo de cancelamento;
- `board/health/`: deep-health final;
- `board/indicator-live.json`: leitura read-only atual;
- `offline-visual/`: galeria de estados e orientacoes;
- `audits/`: auditorias independentes.
