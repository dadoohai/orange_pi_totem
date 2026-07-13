# 199 - C25 - Estados Visiveis Do Produto

## Missao

Um totem simples nao pode parecer parado sem explicar o que esta acontecendo.
C25 torna os estados publicos verdadeiros, claros e visualmente consistentes,
sem desktop, Chromium, rede extra ou diagnostico tecnico na tela.

## Estado Da Rodada

```text
status=off_board_ready_for_hdmi_homologation
scope=totem-core_plus_image_bound_launcher_hook
totem_core_subset_packagable=true
launcher_retry_hook_requires_next_image=true
offline_tests=passed
generated_visual_review=passed
hdmi_final_acceptance=pending
package_not_yet_promoted=true
next_reference_image_pending=true
```

## Contrato Publico V1

Schema: `totem-status.v1`.

| Estado | Significado publico | Condicao minima |
| --- | --- | --- |
| `booting` | sistema preparando a exibicao | launcher ainda iniciando |
| `display_missing` | tela nao detectada | conector sem sink |
| `config_missing` | configuracao necessaria | config ausente ou invalida |
| `starting_player` | player iniciando | processo iniciou, sem prova de conteudo |
| `loading_content` | conteudo em preparo | espera valida, sem primeiro frame |
| `content_unavailable` | retry de conteudo | falha repetida ou nenhuma midia utilizavel |
| `player_running` | player em operacao | status fresco, MPV ativo, sinal local de inicio e arquivo atual existente |
| `player_error` | recuperacao do processo | app saiu ou status do player venceu |
| `maintenance_placeholder` | manutencao autorizada | launcher parado com sinal explicito de manutencao |

Precedencia: display, config e ownership visual; depois falha do processo;
depois frescor e primeiro frame; por fim carregamento ou operacao normal.
Erro de API nunca deve ser rotulado automaticamente como falta de internet.

## Mudancas Da Fatia

- status antigo, grande, invalido ou vindo de symlink deixa de sustentar
  `player_running`;
- `player_running` exige primeiro frame confirmado, MPV ativo e item atual;
- falha repetida sem conteudo ganha estado recuperavel proprio;
- saida do player passa a manter uma tela de recuperacao durante o retry;
- tela publica remove enums, timestamp, painel de suporte e copy tecnica;
- F10 passa a instruir corretamente: segurar por 5 segundos;
- wizard deixa de dizer `Concluido` antes do writer;
- `Configuracao salva` aparece somente depois do writer verde;
- falha do writer ganha tela publica antes de restaurar o player;
- galeria passa a incluir SVG/PNG gerados pelo renderizador real C25.

## Fronteiras

- As telas, o agregador e a verdade do writer pertencem ao pacote OTA
  `totem-core`.
- O snapshot sanitizado foi tornado compativel com o schema V1, mas permanece
  diagnostico `field-data` fora do payload OTA comum, como exige o contrato C18.
- A manutencao da tela de recuperacao entre duas execucoes do player altera
  `kiosky_service_launcher.sh`. Esse arquivo e fixo na imagem e entra somente
  na proxima imagem de referencia; ele nao sera atribuido ao pacote OTA comum.
- O renderer de `totem-core` aparece somente quando o player nao possui DRM.
- Enquanto o processo do player esta vivo, seu placeholder continua sendo a
  superficie visivel. A atualizacao dinamica desse placeholder e uma fatia
  separada de `player-runtime`, nao uma claim desta rodada.
- `first_frame_ready` confirma hoje a aceitacao do caminho pelo MPV, nao um
  pixel fisico no HDMI. Por isso C25A nao usa esse sinal para afirmar na tela
  que um frame foi comprovadamente apresentado; essa prova pertence a C25B.
- Tela preta causada pelo proprio display/sink exige diagnostico externo; uma
  tela sem sinal nao consegue mostrar sua propria falha.
- Rede, backend e conteudo continuam causas separadas. C25 nao inventa uma
  causa que os sinais locais nao provem.

## Validacao

Antes de empacotar:

1. self-tests de aggregate, renderer, splash, wizard e snapshot;
2. smoke launcher comprovando renderer no intervalo de retry e exclusao mutua;
3. galeria real sem overflow, corte ou texto tecnico;
4. gate global C18 sem regressao;
5. auditoria independente de estado, UX e fail-closed.

Quando HDMI estiver disponivel:

1. config pendente com instrucao F10 correta;
2. writer verde e writer rejeitado;
3. app exit seguido de recuperacao e novo start;
4. fluxo F10, cancelar, salvar e retornar a midia;
5. confirmar ausencia de preto longo, flicker e splash em loop.

Sem essa ultima sessao, C25 pode ser `off-board ready`, mas nao `visually
accepted on hardware`.

## Checkpoint De Pausa - 2026-07-12

Estado: implementacao local em PDCA, sem commit, pacote promovido ou apply na
placa. O subset `totem-core` foi montado e seus health checks passaram; a placa
confirmou em probe temporario que `display_missing` vence um snapshot antigo de
reproducao.

Correcoes incorporadas apos auditoria independente:

- rollback para pacotes antigos nao exige o novo self-test do agregador;
- falha do agregador invalida SVG antigo antes do retry;
- smoke de handoff entrou no gate global;
- galeria reprova raster incompleto e nunca autoriza imagem sozinha;
- schema, caminho e enums do player falham fechados no JSON publico;
- guard de responsabilidade inclui installer e snapshot `field-data`.

Blockers honestos ainda abertos:

1. `first_frame_ready` do player prova path aceito, nao frame fisico apresentado;
2. estados com o processo do player vivo ainda dependem do placeholder legado;
3. rotacao do renderer de status, verdade final do writer e semantica de cores
   precisam da rodada de fechamento;
4. galeria final, gates completos e aceite HDMI devem ser repetidos apos os
   ajustes.

Ordem de retomada: fechar os itens localizados de core, regenerar e reinspecionar
a galeria, executar gates completos, abrir auditoria final independente e so
entao decidir a fatia governada de `player-runtime` e o aceite HDMI. Nenhuma
promocao OTA ou claim de imagem esta autorizada neste checkpoint.

## Checkpoint De Fechamento Off-Board - 2026-07-12

Estado atual:

```text
c25a_totem_core=off_board_ready
c25b_player_owned_live_states=separate_pending_slice
image_bound_launcher_hook=implemented_pending_reference_image
gallery=76_png_complete_zero_p0
package=local_homologation_candidate_health_green
release_gate=79_of_82_expected_precommit
independent_final_audit=passed_for_hdmi_homologation
hdmi_acceptance=pending
stable_promotion=not_authorized
```

A bateria inicial do gate passou 79 de 82 checks; as tres reprovacoes foram os
guards esperados antes do commit: arvore suja no inicio/fim e mais de uma frente
de responsabilidade no diff. A auditoria adversarial posterior encontrou gaps
fora dessa cobertura, incorporados antes do aceite HDMI. O payload local inclui
apenas `totem-core`; o launcher, o installer da imagem e o snapshot diagnostico
continuam fora dele. O gate deve ser repetido em arvore limpa antes de qualquer
promocao.

O rollback agora valida o destino antes de trocar qualquer link. C21.9, C21.10
e C21.11 foram confirmados como destinos compativeis; arquivos historicos mais
antigos podem ser recusados pelo health atual, sempre preservando `current`,
`previous` e state. C25 nao promete rollback arbitrario para todo tarball
arquivado; recuperacao anterior a esse horizonte usa o fallback da imagem ou
regravacao governada.

A galeria final rasterizou todas as 76 telas sem falha, overflow ou P0. Ela
inclui a confirmacao final real em paisagem e retrato, alem de saving, sucesso e
falha do writer. A revisao central dos pixels foi concluida, mas a galeria nao
substitui o aceite HDMI das transicoes entre player, renderer e wizard.

Evidencia reproduzivel:
`docs/evidence/c25-visible-states/20260713T000044Z-offboard-final/`.

Proxima ordem objetiva:

1. incorporar apenas findings validos da auditoria final;
2. separar e commitar as frentes sem alterar seus contratos;
3. repetir gate em arvore limpa e reconstruir o pacote image-bound;
4. aplicar a candidata `totem-core` em homologacao e validar na tela real;
5. registrar C25A como aceita ou fazer rollback;
6. manter C25B (`player-runtime` com processo vivo) como proxima fatia governada.
