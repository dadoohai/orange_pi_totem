# C18 prod15 - validacao pos-gravacao na placa

Estado: validacao fisica e revisao independente verdes. Esta evidencia sustenta
a promocao da `prod15` como baseline de distribuicao atual, dentro dos limites
registrados abaixo.

## Artefato validado

- imagem: `c18-hwdecode-prod-15` / `c18.image-prod.15`;
- SHA256:
  `cff33f16e3a0f62327b0b75fb2378c08da9e51e14f9a9550ded72730e2218d09`;
- totem-core embutido e adotado:
  `c21.24-product-stable-20260717T025907Z-076e18b`;
- player-runtime embutido e alvo remoto exato:
  `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`;
- payload C25B:
  `b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d`.

## Resultado na placa

- primeiro boot criou identidade propria, expandiu o rootfs e manteve a pilha
  de video esperada;
- a jornada real do wizard foi percorrida: tela, conexao Ethernet, autorizacao
  por QR, selecao de ambiente pelo celular, revisao, bloqueio de pendencia e
  confirmacao. As capturas provam as telas e o ambiente validado; servico,
  status e deep-health provam o retorno automatico a midia;
- a configuracao foi gravada com `0640 root:totem`, permaneceu presente e foi
  consumida normalmente depois do reboot final;
- antes do OTA, o deep-health passou com seis midias distintas, HW decode
  `v4l2request-copy`, zero falha de carga e zero restart;
- C21.24 executou no-op real: `current`, `state.json` e a invocacao do player
  permaneceram inalterados;
- o alvo C25B exato foi baixado e adotado em `/data/player-runtime/current`;
- a segunda execucao foi no-op sem alterar estado nem reiniciar o player;
- o rollback publico de `player-runtime` permaneceu congelado em `rc=44` e
  nao alterou estado;
- o rollback autorizado removeu os links em `/data`, adotou
  `/opt/totem/kiosky-player` e voltou a `playing` com health verde;
- a restauracao remota readotou C25B em `/data`, seguida de deep-health verde;
- apos reboot, o sistema voltou `running`, sem unidades falhas, com C21.24,
  C25B, configuracao e os dois timers persistidos;
- os dois timers dispararam sozinhos depois do reboot; core e player-runtime
  terminaram em no-op com `Result=success`, preservando current, state e a
  mesma invocacao do player;
- o deep-health pos-reboot passou em 30/30 amostras, com multiplas transicoes,
  HW decode em 30/30, zero restart, zero falha de midia e zero erro novo de
  GPU, MMC ou ext4.

O `console-setup.service` falhou uma vez no primeiro boot enquanto o relogio
da imagem ainda estava defasado. Um restart controlado passou. No reboot final,
o servico iniciou sozinho com `Result=success`; portanto o evento foi
transitorio e nao recorrente nesta campanha.

## Rate limit do canal GitHub

O primeiro disparo real dos dois timers encontrou `HTTP 403 rate limit
exceeded` no IP publico compartilhado do laboratorio. Ambos falharam antes de
qualquer promocao, limparam o staging e mantiveram player e versoes atuais.
Depois do reset da janela do GitHub, core no-op, apply C25B, no-op, rollback e
restauracao passaram normalmente.

Isso nao invalida a imagem nem sua seguranca de rollback. E um risco de
latencia de distribuicao: consultas sem token compartilham a cota publica por
IP, logo varias placas atras do mesmo NAT podem receber uma stable somente em
uma tentativa posterior. A placa tenta novamente pela cadencia de seis horas.
Nenhum token compartilhado foi embutido na imagem. O caminho recomendado para
escala maior e substituir a descoberta por um indice stable sem polling da API
ou provisionar credencial de leitura por dispositivo/coorte; isso fica
registrado como endurecimento de distribuicao, nao como mudanca improvisada na
baseline validada.

## Limites honestos

- a tecla F10 fisica nao foi reexecutada nesta gravacao; o servico real do
  wizard e toda a jornada foram exercitados, e o mesmo trigger ja era coberto
  pela baseline anterior;
- AP aberto fisico, portal cativo fisico/emulado e displays adicionais
  continuam nos limites ja registrados no plano macro;
- esta validacao nao autoriza nenhum player-runtime alem do C25B exato;
- os erros de boot historicos `Error applying setting, reverse things back` e
  avisos opcionais de Bluetooth/Wi-Fi reapareceram sem unidade falha, sem erro
  MMC/ext4 e sem impacto de playback, como ja documentado desde as campanhas
  iniciais.

## Evidencia

- `visual/`: capturas reais do framebuffer durante a jornada; telas contendo
  QR ou codigo efemero foram deliberadamente excluidas da evidencia publica;
- `board/pre-reboot/`: apply, no-op, freeze, rollback, restauracao e health;
- `board/post-reboot/`: adocao persistida, timers, systemd e health final;
- `board/rate-limit-after-validation.txt`: estado sanitizado da cota ao final.
- `artifact-byte-verification.txt`: recomputacao do SHA e tamanho da copia de
  distribuicao ainda presente no disco de imagens.
