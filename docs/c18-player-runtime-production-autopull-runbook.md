# C18 M5 player-runtime production auto-pull

Objetivo: provar separadamente que uma imagem production busca e adota o alvo
exato autorizado, consegue voltar/restaurar e permanece limpa em playback por
uma janela continua que cubra falhas tardias, sem abrir `latest`.

## Alvo

- version: `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`
- tag: `player-runtime-c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`
- autorizacao: `scripts/board/player_runtime_production_autopull.json`
- imagem prevista: `c18-hwdecode-prod-8` / `c18.image-prod.8`
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
   deixar o bridge rollback-safe como `current` e C23 fora de
   `current/previous`.
5. Ligar o timer e coletar `pre` e `post_apply`.
6. Rodar novamente a unit para provar `noop` sem alterar state/symlinks.
7. Rodar `rollback-player-runtime-authorized` para o bridge e coletar
   `rollback`.
8. Rodar o mesmo rollback autorizado outra vez para restaurar C23 e coletar
   `restored` com `--deep-health-duration-sec 600`. Depois do restore terminar,
   aguardar o status declarar `playback_state=playing`, `mpv_running=true` e um
   `current_item` presente; somente entao iniciar a janela continua.
9. Copiar cada snapshot junto de seu diretorio `<fase>-deep-health`, sem
   separar os arquivos ou alterar nomes.
10. Rodar `c18_player_runtime_production_autopull_evidence_gate.py` sobre as
   cinco coletas, a evidencia de publicacao e os quatro artefatos exatos; depois
   commitar a evidencia com arvore limpa.

## Resultado exigido

- C23 veio da tag GitHub exata e tem hashes/marker corretos;
- o trigger do timer ocorreu depois do pre e a unit teve nova invocacao para o
  apply e para o no-op;
- os arquivos reais de amostras/deep-health acompanham cada fase e seus hashes
  batem com o snapshot;
- os cinco sidecars `deep-health-*.json` produzidos pelo coletor acompanham cada
  fase;
- player e HW decode passam deep-health apos apply, rollback e restauracao;
- o `restored` final cobre ao menos 10 minutos continuos, com amostras reais,
  zero `media_load_failed`, restart interno, restart de servico, acao de
  watchdog ou falha de IPC;
- no-op nao muda state, current ou previous;
- rollback reinicia e verifica o player antes de reportar sucesso;
- CLI generico de player-runtime continua bloqueado com `rc=44`;
- timer de `totem-core` continua independente;
- estado final: C23 `current`, bridge `previous`, alvo fora de quarantine;
- C21 rejeitado continua em quarantine, sem contaminar o round-trip aprovado.

Non-claims: nao e `latest` amplo, stable de qualquer pacote futuro, rollout por
grupos, assinatura consumida no device ou atualizacao de media-system. O gate
offline detecta evidencia ausente/inconsistente, mas nao torna artefatos
coerentemente fabricados resistentes a adulteracao sem attestation no device.

## Historico e execucao atual

Mecanica C22 fechada em 2026-07-10 na imagem prod7. O timer real aplicou C22 a
partir do bridge, o no-op nao alterou estado, o rollback voltou ao bridge e a
segunda troca restaurou C22. As cinco janelas curtas passaram deep-health e
freeze `rc=44`.

Uma auditoria posterior encontrou restart interno do MPV entre/depois dessas
janelas. A reavaliacao atual preserva `mechanics_passed=true`, mas bloqueia
`product_distribution_cleanliness_passed` porque o `restored` original durou
somente 30 segundos. Essa separacao e o requisito continuo formam o schema v2
do gate. C23 e a recaptura continua de 10 minutos fecham essa claim.

C23 ja passou apply/rollback local e duas observacoes continuas de 10 minutos,
mas isso nao substitui o auto-pull remoto a partir da prod8. A execucao atual
deve repetir o round-trip acima usando a autorizacao C23 embutida na imagem.

Evidencia:
`docs/evidence/c18-update-validation/20260710T190539Z-prod7-m5-production-autopull-c22/`.
