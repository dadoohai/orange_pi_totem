# C22 - campanha adversarial rapida de confiabilidade

Estado: implementacao, prova adversarial de placa e pacote de homologacao
concluidos em 2026-07-10. O roundtrip apply/rollback/reapply do pacote na placa
e o ultimo passo deste marco; nenhuma publicacao externa ou promocao `stable`
faz parte dele.

## Objetivo

Forcar, em minutos, falhas praticas de midia e OTA que antes poderiam ficar
silenciosas, sem repetir soak ou a matriz fisica 17/17 ja encerrada. A regra e:
midia defeituosa nao entra, playlist incompleta nao substitui conteudo bom,
falha fica observavel e a placa sempre volta funcional.

## Verticais exercitadas

- playlist mista de video, imagem e novas transicoes;
- API 500, API vazia, download truncado e corpo HTTP invalido;
- cache e sidecar de imagem corrompidos;
- recuperacao para nova playlist valida;
- alinhamento entre status e caminho real do MPV;
- captura KMS para excluir preto persistente;
- concorrencia de reconcile, pacote OTA inflado e falta de espaco;
- encerramento do candidato e restauracao do player/timers reais.

## Mudancas fechadas

### Player

- `ffprobe` valida estrutura, stream de video e dimensoes;
- `ffmpeg` precisa decodificar o primeiro frame, fechando falso-verde de MP4
  truncado que o `ffprobe` isolado aceitava;
- sidecar H.264 invalido e reconstruido antes de uso;
- API vazia ou playlist incompleta preserva a ultima playlist boa;
- adocao parcial legada continua possivel, mas nunca aparece como verde;
- status e telemetria passam a expor adocao, pendencias, falhas e conteudo
  desatualizado.

### OTA

- limite de membros, tamanho compactado e tamanho expandido do tar;
- reserva minima de espaco antes da extracao;
- download e copia local abortam pacote compactado acima do limite;
- copia local valida tamanho e SHA sobre os bytes ja no staging;
- extracao remove ownership, setuid/setgid e escrita global do tar;
- manifests e release gates baixados tambem possuem limite de tamanho;
- staging e arquivos `.part` recusam escapes por symlink;
- caminho de release inesperadamente simbolico falha sem tocar o alvo externo;
- reconcile de `player-runtime` usa o lock global e retorna `rc=49` sem mutar
  estado quando ocupado.

## Prova real de placa

Evidencia final:
`docs/evidence/c22-rapid-adversarial/20260710T045119Z-board-governed-final/`.

Resultado:

- todos os cenarios de falha preservaram a ultima midia boa em reproducao,
  observada por status, MPV e KMS;
- sidecar corrompido foi reconstruido e decodificado;
- recuperacao adotou playlist valida;
- trecho misto observou 3 midias e 8 transicoes do MPV;
- 20 capturas KMS validas, sem preto persistente;
- desalinhamento status/MPV recuperou em no maximo 2 amostras;
- servico, timer, symlinks, configuracao e midia de producao foram restaurados;
- player final voltou `playing`, com IPC, KMS e `v4l2request-copy` saudaveis.

## Limite honesto

O `kmsgrab` continuo desta imagem nao atravessa a mudanca do plano DRM entre
`NV12` e `AR24`; o FFmpeg encerra ao reconfigurar `hwdownload`. Amostras
isoladas nao mostraram preto persistente na corrida final, mas este marco nao
prova "zero frame preto em toda transicao". Essa afirmacao exige captura HDMI
ou optica sincronizada. Tambem nao prova rollout publico, auto-pull do novo
runtime, soak novo ou comportamento de todas as midias reais de cliente.

Achado operacional ao vivo: o timer de `player-runtime` foi encontrado ativo,
mas ainda autorizado para `9bebaf1`, enquanto a placa roda candidato mais novo.
A protecao de downgrade rejeita a tentativa com `rc=45`, entao nao ha regressao
do runtime; o servico do timer, contudo, fica `failed` ate a proxima janela.
Reancorar autorizacao/timer pertence ao M5 e so deve ocorrer depois de aprovar o
novo pacote exato.

## Proximo marco

Pacote alvo:
`c18.player-runtime-homolog-20260710-c22-c023eae`, payload SHA256
`4b5ee5435be0fb3d21d0cf3661c5eac94a9348aa77e1cd8f5613d5ee66740e16`.

1. aplicar, validar, rollbackar e reaplicar pela rota governada na placa;
2. manter publicacao externa e auto-pull separados no marco M5;
3. carregar a verificacao optica/HDMI de transicao como hardening posterior,
   sem bloquear as protecoes de integridade e disponibilidade fechadas aqui.
