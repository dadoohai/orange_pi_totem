# C18 prod14 - build e auditoria pre-flash

Estado: aprovada somente para um flash controlado na placa de homologacao,
depois deste conjunto estar commitado e a arvore ficar limpa. Nao e referencia
de distribuicao nem autorizacao de rollout amplo.

Artefato:

- tag: `c18-hwdecode-prod-14`;
- versao: `c18.image-prod.14`;
- SHA256: `3d93f05f896c8e7c17866129a901a02803e65d7968ed69eac3987b03a4b02682`;
- source: `59a1b7c4774ec0cd487405f4205a526abf18b899`;
- predecessor: `c18-hwdecode-prod-13`;
- predecessor SHA256: `4918796e08a1a0147c797ac64fa0629a6d2d340fa21902c78a629f62db89ac3e`;
- marker SHA256: `ef56eec47a977bb4f0d8d3f50a7934ae0ac5b1219fa52eaccb76f8483c4fb8f2`.

Resultado:

- release gate `84/84` e validacao offline `66/66`;
- ext4 limpo, `58513/58513` blocos livres zerados e zero inode apagado;
- duas auditorias independentes compararam as imagens reais;
- boot region, kernel, initrd, DTB, U-Boot, C20.14, C25B e pilha de midia
  permaneceram identicos;
- os dois deltas funcionais sao a espera production de oito segundos e o
  canario cobrindo toda a janela de health; ambos batem com o source;
- identidade/timestamp e rotacao controlada da credencial prod14 sao os demais
  deltas esperados; nao houve delta inesperado;
- host keys, machine-id, config real e credencial plaintext nao foram
  incorporados.

As auditorias encontraram um blocker operacional temporario: o build ainda nao
estava rastreado. Este diretorio, o marker binding, os relatorios e o runbook
canonico formam a resolucao; o flash continua proibido enquanto `git status`
nao estiver limpo.

Proximo passo: gravar exatamente este SHA uma unica vez e executar boot/config,
apply, no-op, rollback para a imagem, reapply, freeze `rc=44`, health continuo
de 600 segundos e reboot final conforme
`docs/c18-player-runtime-production-autopull-runbook.md`.

Non-claims: nao prova a prod14 na placa, nao promove distribuicao, nao abre
`latest` e nao autoriza outra versao de player-runtime.
