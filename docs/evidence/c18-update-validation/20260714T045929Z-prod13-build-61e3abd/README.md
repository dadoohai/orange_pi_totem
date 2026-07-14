# C18 prod13 - build e auditoria pre-flash

Estado: candidata aprovada somente para um flash controlado na placa de
homologacao. Nao e referencia de distribuicao nem autorizacao de rollout.

Artefato:

- tag: `c18-hwdecode-prod-13`
- versao: `c18.image-prod.13`
- SHA256: `4918796e08a1a0147c797ac64fa0629a6d2d340fa21902c78a629f62db89ac3e`
- source: `61e3abd9f78b229bb61125417494c669b0e60f57`
- predecessor: `c18-hwdecode-prod-12`
- predecessor SHA256: `4bef1f398635f66202c280b33206c4f7e84503c9d0f8734888a5821bae9d8262`

Escopo autorizado do sucessor:

1. identidade prod13;
2. `totem-core` C20.14 exato;
3. integracao image-bound do guard transacional entre settings e updater.

Resultados:

- release gate no source limpo: `84/84`;
- policy static: `81/81`;
- validacao offline da imagem: `66/66`;
- ext4 limpo, 58.513 blocos livres zerados e slack zerado;
- boot region, kernel, initrd, DTB, U-Boot, player-runtime e pilha de midia
  identicos a prod12;
- 52 deltas de conteudo, todos previstos; zero delta inesperado;
- host keys ausentes, machine-id vazio e credencial externa conferida sem
  exposicao contra `/etc/shadow` e `/etc/shadow-`;
- exemplos publicos de chave do pacote OpenVPN permanecem apenas em
  `/usr/share/doc`; nao ha chave ativa nem configuracao OpenVPN de produto.

Non-claims:

- nao prova boot da prod13 na placa;
- nao prova expansao fisica do cartao;
- nao prova persistencia da identidade SSH apos dois boots;
- nao prova wizard, QR, writer, playback ou timers na prod13;
- nao promove C20.14 para release remota `stable`;
- nao substitui prod8 + C23 como referencia de distribuicao.

O proximo passo e gravar somente este SHA na unica placa de homologacao e
executar o E2E fisico registrado no relatorio de decisao.
