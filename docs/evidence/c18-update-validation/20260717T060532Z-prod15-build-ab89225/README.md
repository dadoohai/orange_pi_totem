# C18 prod15 - build e auditoria pre-flash

Estado: aprovada somente para uma gravacao controlada na placa de homologacao.
Ainda nao e referencia de distribuicao. Essa promocao depende do boot, da
jornada do wizard, do player, do OTA e do reboot passarem na placa real.

Artefato:

- tag: `c18-hwdecode-prod-15`;
- versao: `c18.image-prod.15`;
- SHA256: `cff33f16e3a0f62327b0b75fb2378c08da9e51e14f9a9550ded72730e2218d09`;
- bytes: `1971322880`;
- source: `ab892251e434aa1bcd4fa4ab773fc5f0025ee468`;
- tree: `2067083bcb79885b23b22e2ba370687ddd5be285`;
- predecessor: `c18-hwdecode-prod-14`;
- predecessor SHA256: `3d93f05f896c8e7c17866129a901a02803e65d7968ed69eac3987b03a4b02682`.

Resultado:

- release gate completo verde;
- validacao offline e filesystem limpos;
- tres auditorias independentes aprovaram exatamente uma gravacao controlada;
- boot, kernel, U-Boot, DTB, pilha de video e player-runtime C25B foram
  preservados em relacao a prod14;
- o totem-core C21.24 stable foi embutido com conteudo exato;
- a correcao image-bound do avaliador de playback foi incorporada;
- machine-id vazio, host keys ausentes e nenhuma configuracao real ou
  credencial plaintext foram incorporados;
- a credencial compartilhada de suporte foi rotacionada e somente seu hash
  aparece na imagem, conforme o contrato atual.

Esclarecimento: o texto `C21.24 stable product baseline` no manifest refere-se
ao totem-core incorporado. Nao promove a imagem prod15. A imagem permanece
candidata ate a validacao fisica.

Proximo passo: gravar exatamente este SHA uma unica vez, com HDMI conectado
antes do boot, e validar wizard, playback/deep-health, C21.24, C25B congelado,
timer, no-op, rollback, restauracao e reboot. Somente depois atualizar a fonte
da verdade e declarar a prod15 como baseline de distribuicao.

Non-claims: nao prova a prod15 na placa, nao autoriza rollout amplo, nao libera
outro player-runtime e nao substitui a validacao pos-flash.
