# 199 - C25 - Estados Visiveis Do Produto

## Missao

Um totem simples nao pode parecer parado sem explicar o que esta acontecendo.
C25 torna os estados publicos verdadeiros, claros e visualmente consistentes,
sem desktop, Chromium, rede extra ou diagnostico tecnico na tela.

## Estado Da Rodada

```text
status=c25a_totem_core_and_c25b_player_runtime_validated_on_homologation_board
scope=totem-core_with_image_bound_and_player_runtime_slices_tracked_separately
totem_core_subset_packagable=true
launcher_retry_hook_requires_next_image=true
c25b_player_runtime_package=c18.player-runtime-homolog-20260713-c25b-recovery-8ce9bb8
c25b_apply_rollback_reapply=passed
c25b_live_mpv_recovery_surface=passed
offline_tests=passed
generated_visual_review=passed
board_framebuffer_flow_validation=passed
hdmi_camera_flicker_acceptance=pending
writer_mutating_e2e=not_repeated_in_this_round
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

## Checkpoint De Aceite C25A Na Placa - 2026-07-13

Estado atual:

```text
c25a_totem_core=applied_on_homologation_board
package=c25.1-visible-states-20260713T001600Z-7f204d7
package_source_commit=7f204d725d4d10d4add85909a1a6d0fc99b23fd8
package_payload_sha256=4407e407bae3badf041e109215cb16e15af6b70563f71c238c4d580ee95f1178
release_gate=82_of_82_clean
board_apply=passed
wizard_navigation_and_cancel=passed_on_real_board
incomplete_review_block=passed_on_real_board
writer_state_layout=passed_on_real_framebuffer
framebuffer_transition_atomicity=not_proven
player_return=passed
policy_restore=byte_identical
rollback_target=c21.11-qr-pairing-20260712T021729Z-4068839
stable_promotion=not_authorized
image_bound_launcher_hook=pending_reference_image
c25b_player_owned_live_states=pending_separate_slice
```

O pacote `totem-core` foi aplicado pelo updater governado. A placa abriu o
wizard real, navegou ate a Revisao, recusou conclusao incompleta, cancelou sem
salvar e voltou a reproduzir midia. As telas estaveis de confirmacao, gravacao,
sucesso e falha ficaram legiveis e sem overflow. Uma captura feita durante a
transicao, porem, mostrou o quadro sendo desenhado progressivamente; esse
achado reabriu o aceite e originou C25.2.

Para nao alterar novamente uma configuracao funcional, esta sessao nao repetiu
uma escrita real de Wi-Fi/ambiente. Portanto, o resultado confirma a navegacao,
os guardrails, o retorno ao player e o layout fisico dos estados do writer; nao
cria uma nova claim de writer E2E mutante.

A policy temporariamente aberta para `homologation` foi restaurada byte a byte
para `stable`, o timer ficou ativo, o servico voltou ativo e o rollback para
C21.11 permaneceu disponivel. Este checkpoint prova o apply e o fluxo inicial,
mas sua claim visual final foi substituida pelo checkpoint C25.2 abaixo.

Evidencia:
`docs/evidence/c25-visible-states/20260713T003029Z-board-hdmi-acceptance/`.

Proxima ordem objetiva:

1. consolidar o hook image-bound na proxima imagem de referencia;
2. tratar C25B como fatia separada de `player-runtime` para estados visiveis
   enquanto o player possui a tela;
3. promover C25A somente dentro do fluxo OTA governado, sem inferir que o
   aceite desta placa valida automaticamente uma nova imagem.

## Checkpoint C25.2 - Quadro Composto Antes Da Publicacao - 2026-07-13

Estado atual:

```text
c25a_totem_core=validated_on_homologation_board
package=c25.2-frame-publish-20260713T004706Z-3267ecf
package_source_commit=3267ecf8e68e557d93ca3a60bd995c0af6c18796
package_payload_sha256=9841eb8b25883c9e91fd12dbb6f4aafb55bc14b3ea39eb91f41a982628116067
release_gate=82_of_82_clean_package_bound
sandbox_apply_rollback=passed
board_apply=passed
policy_restore=byte_identical
wizard_navigation_guard_cancel_return=passed
progressive_frame_composition=closed
stable_frame_series=10_of_10_byte_identical
scanout_atomicity=not_claimed
hdmi_camera_flicker_acceptance=pending
stable_promotion=not_authorized
image_bound_launcher_hook=pending_reference_image
c25b_player_owned_live_states=pending_separate_slice
```

A auditoria independente rejeitou corretamente a claim ampla do primeiro
aceite: captura de framebuffer nao equivale a camera HDMI, o writer real nao
foi repetido e o hook de app-exit depende da proxima imagem. Alem disso, uma
captura transitoria revelou desenho progressivo.

A causa localizada foi corrigida: o renderer agora compoe o quadro em memoria
e somente depois o publica. Um erro no meio da composicao preserva o quadro
anterior, coberto por self-test. Na placa, vinte transicoes levaram entre
`0,153 s` e `0,183 s`; a serie estavel ficou identica em dez capturas.

O framebuffer desta placa nao oferece um segundo quadro virtual. Leitura
concorrente de alta frequencia ainda pode atravessar a copia final, portanto
C25.2 nao promete page flip atomico nem ausencia absoluta de tearing por
camera. Isso fica como limite conhecido, distinto do desenho progressivo ja
fechado.

Veredito: C25.2 esta aceita para homologacao funcional do `totem-core`, sem
promocao `stable`. A proxima imagem deve incorporar o hook image-bound; C25B e
o aceite perceptivo por camera continuam fatias separadas e rastreadas.

Evidencia:
`docs/evidence/c25-visible-states/20260713T010245Z-board-frame-publish-fix/`.

## Checkpoint C25B - Estados Dinamicos No Player - 2026-07-13

Estado atual:

```text
c25b_player_owned_live_states=validated_on_homologation_board
package=c18.player-runtime-homolog-20260713-c25b-recovery-8ce9bb8
package_source_commit=8ce9bb8f4a3bcb2873c229ef6791008eca1b57c2
package_payload_sha256=962346c2fd9df78a555ae767ab4562161c307ce9a4497c63ee38c4c5608f5cff
release_gate=passed
candidate_health=45_of_45_clean
controlled_mpv_recovery=passed
recovery_surface_status_and_mpv_path=passed
rollback_to_c23=passed
linked_previous_reapply=passed
final_live_health=30_of_30_clean
stable_promotion=not_authorized
public_player_autopull=not_enabled_for_this_target
next_reference_image=pending
```

O MPV de producao rejeitou o primeiro formato SVG; a fatia foi corrigida para
H.264 de um quadro, gerado atomicamente e validado antes do uso. A primeira
tentativa H.264 tambem revelou uma contradicao real: a superficie estava
visivel, mas o status ainda carregava o risco antigo de tela preta. A correcao
passou a limpar esse risco somente depois da prova local de quadro.

Um teste controlado de saida do MPV encontrou a ultima lacuna: a tela de
recuperacao era criada apenas depois da falha e sua prova podia desaparecer no
intervalo do writer de status. O player agora preaquece essa superficie atras
da tela de carregamento, registra `recovering` imediatamente e persiste a prova
assim que o MPV apresenta o quadro.

Na placa, a superficie `player_error` foi observada no status e diretamente no
caminho ativo do MPV; a midia voltou sem restart do servico e sem novo evento
Panfrost. O pacote final foi rollbackado para C23, teve saude verde, e voltou
pelo caminho explicito de reaplicacao do `previous` verificado. Uma tentativa
comum de reaplicar foi corretamente negada com rc=45.

Veredito: C25B esta aceita para homologacao funcional e reversivel. O pacote
continua fora de `stable` e do auto-pull publico. A proxima imagem de referencia
deve incorporar este snapshot, o updater e o launcher correspondentes antes de
qualquer claim de distribuicao ampla.

Evidencia:
`docs/evidence/c25-visible-states/20260713T062512Z-c25b-player-h264-governed/`.
