# C18 C25B - verificacao do release existente

Estado: aprovado, sem mutacao remota.

Em arvore limpa no commit
`aee07f76f660f9234d8fd872778658f0dc5c1af9`, a rota exact-target foi executada
com `--verify-existing` sobre o release C25B ja publicado. A verificacao:

- confirmou tag e source commit exatos;
- recusaria draft, prerelease ou conjunto de assets diferente;
- baixou os tres assets e comparou seus SHA256 com os arquivos locais;
- confirmou `latest` identico antes e depois;
- nao criou, editou, substituiu ou republicou release.

O resultado estruturado esta em `publication-verification.json` e seu hash em
`SHA256SUMS`.

Non-claims: esta prova nao e E2E da prod14, nao promove `stable`, nao move
`latest` e nao autoriza outro alvo de player-runtime.
