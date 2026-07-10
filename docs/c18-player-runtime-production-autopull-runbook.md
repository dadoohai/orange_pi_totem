# C18 M5 player-runtime production auto-pull

Objetivo: provar que uma imagem production busca e adota automaticamente o
unico alvo C22 autorizado, sem abrir `latest`, e consegue voltar e restaurar o
player com health real.

## Alvo

- version: `c18.player-runtime-homolog-20260710-c22-c023eae`
- tag: `player-runtime-c18.player-runtime-homolog-20260710-c22-c023eae`
- autorizacao: `scripts/board/player_runtime_production_autopull.json`
- imagem prevista: `c18-hwdecode-prod-7` / `c18.image-prod.7`
- baseline de bancada: bridge rollback-safe
  `c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63`

C21 `c18.player-runtime-homolog-20260709-image-transcode-50919f5` foi rejeitado
corretamente pelo health de candidato durante a preparacao desta rodada. Ele
permanece em quarantine e nao deve ser perdoado nem usado como baseline M5.

## Ordem

1. Gate global verde, repo limpo e imagem production offline validada.
2. Branch e tag no remoto; publisher exact-target em `--prepare-only` verde.
3. Publicar somente manifest, payload e release gate com `--latest=false` e
   salvar o JSON final do publisher como evidencia de publicacao.
4. Gravar a imagem e, com o timer parado apenas durante o setup da bancada,
   deixar o bridge rollback-safe como `current` e C22 fora de
   `current/previous`.
5. Ligar o timer e coletar `pre` e `post_apply`.
6. Rodar novamente a unit para provar `noop` sem alterar state/symlinks.
7. Rodar `rollback-player-runtime-authorized` para o bridge e coletar
   `rollback`.
8. Rodar o mesmo rollback autorizado outra vez para restaurar C22 e coletar
   `restored`.
9. Copiar cada snapshot junto de seu diretorio `<fase>-deep-health`, sem
   separar os arquivos ou alterar nomes.
10. Rodar `c18_player_runtime_production_autopull_evidence_gate.py` sobre as
   cinco coletas, a evidencia de publicacao e os quatro artefatos exatos; depois
   commitar a evidencia com arvore limpa.

## Resultado exigido

- C22 veio da tag GitHub exata e tem hashes/marker corretos;
- o trigger do timer ocorreu depois do pre e a unit teve nova invocacao para o
  apply e para o no-op;
- os arquivos reais de amostras/deep-health acompanham cada fase e seus hashes
  batem com o snapshot;
- os cinco sidecars `deep-health-*.json` produzidos pelo coletor acompanham cada
  fase;
- player e HW decode passam deep-health apos apply, rollback e restauracao;
- no-op nao muda state, current ou previous;
- rollback reinicia e verifica o player antes de reportar sucesso;
- CLI generico de player-runtime continua bloqueado com `rc=44`;
- timer de `totem-core` continua independente;
- estado final: C22 `current`, bridge `previous`, alvo fora de quarantine;
- C21 rejeitado continua em quarantine, sem contaminar o round-trip aprovado.

Non-claims: nao e `latest` amplo, stable de qualquer pacote futuro, rollout por
grupos, assinatura consumida no device ou atualizacao de media-system. O gate
offline detecta evidencia ausente/inconsistente, mas nao torna artefatos
coerentemente fabricados resistentes a adulteracao sem attestation no device.

## Execucao decisiva

Fechada em 2026-07-10 na imagem prod7. O timer real aplicou C22 a partir do
bridge, o no-op nao alterou estado, o rollback voltou ao bridge e a segunda
troca restaurou C22. As cinco fases passaram deep-health e freeze `rc=44`.

Evidencia:
`docs/evidence/c18-update-validation/20260710T190539Z-prod7-m5-production-autopull-c22/`.
