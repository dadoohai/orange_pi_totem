# 199 - C25 - Estados Visiveis Do Produto

## Missao

Um totem simples nao pode parecer parado sem explicar o que esta acontecendo.
C25 torna os estados publicos verdadeiros, claros e visualmente consistentes,
sem desktop, Chromium, rede extra ou diagnostico tecnico na tela.

## Estado Da Rodada

```text
status=c25_validated_on_prod12_c20_14_ready_for_prod13
scope=totem-core_with_image_bound_and_player_runtime_slices_tracked_separately
totem_core_subset_packagable=true
launcher_retry_hook_preserved_in_candidate_chain=true
c25b_player_runtime_package=c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4
c25b_apply_rollback_reapply=passed
c25b_live_mpv_recovery_surface=passed
c25b_live_content_unavailable_surface=passed
c25b_episode_health_fail_closed=passed
offline_tests=passed
generated_visual_review=passed
board_framebuffer_flow_validation=passed
hdmi_camera_flicker_acceptance=pending
writer_mutating_e2e=passed_on_prod12_c20_12
remote_targets_not_yet_promoted=true
next_reference_image=prod13_pending_build_audit_and_board_e2e
prod9_board_acceptance=blocked_do_not_flash
prod10_board_acceptance=blocked_do_not_flash
prod11_board_acceptance=blocked_do_not_flash
prod12_board_acceptance=physical_base_passed_not_distribution_reference
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
  superficie visivel. A atualizacao dinamica desse placeholder foi separada de
  C25A por pertencer a `player-runtime` e foi fechada na fatia C25B registrada
  abaixo; ela nao passa a pertencer ao payload `totem-core`.
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
package=c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4
package_source_commit=54308e4a09ef693dbfb3d6b31ce9626908ca0c16
package_payload_sha256=b6e1a58b6434107a5af43d27bc07f19b0255bcc58c86deac59be6acc2742b70d
release_gate=passed
candidate_health=47_checks_clean
controlled_mpv_recovery=passed
recovery_surface_status_and_mpv_path=passed
content_unavailable_surface_status_mpv_vo_frame=passed
rollback_to_c23=passed
linked_previous_reapply=passed
final_live_health=40_samples_45_checks_clean
inconclusive_episode_negative=correctly_rejected
public_player_runtime_freeze=rc44
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

A rodada seguinte encontrou um caso diferente de video: midia estatica pode
manter o mesmo numero de quadro e nao deve ser tratada como video travado. O
pacote final separa midia em movimento de quadro estatico sem relaxar a prova:
video exige progresso local e quadro estatico exige quadro, HW decode, saida e
dimensoes validos no mesmo instante. Evidencia incompleta ou desconhecida
continua reprovando.

O estado `content_unavailable` foi provocado de forma controlada no candidato
exato e observado no status e no caminho real do MPV, com quadro, VO e
`v4l2request-copy` presentes. O servico foi restaurado ativo sem restart. A
janela final do servico teve 40 amostras, dois episodios de video comprovados,
zero episodio tolerado, zero falha de midia, zero restart e zero novo evento
Panfrost. Uma janela encerrada no primeiro quadro de um episodio foi
corretamente recusada; a janela completa seguinte passou. Isso prova que o
avaliador nao transforma observacao inconclusiva em verde.

A auditoria adversarial final encontrou que erros IPC anteriores ao primeiro
sucesso nao tinham limite. O avaliador agora aceita somente `missing_socket`
de startup por no maximo seis amostras e seis segundos; timeout, outro erro,
tempo invalido ou espera maior reprovam. A evidencia real foi recalculada com
essa regra: candidato, C23 apos rollback e servico final tiveram sucesso desde
a primeira amostra.

Veredito: C25B esta aceita para homologacao funcional e reversivel. O pacote
continua fora de `stable` e do auto-pull publico. A proxima imagem de referencia
deve incorporar este snapshot, o updater e o launcher correspondentes antes de
qualquer claim de distribuicao ampla.

Evidencia:
`docs/evidence/c25-visible-states/20260713T062512Z-c25b-player-h264-governed/`.

Evidencia final que substitui a claim do pacote intermediario:
`docs/evidence/c25-visible-states/20260713T082118Z-c25b-still-final-board/`.

## Checkpoint Prod9 - Consolidacao Bloqueada - 2026-07-13

Estado atual:

```text
reference_image=c18-hwdecode-prod-9
reference_image_version=c18.image-prod.9
image_sha256=4a413bc84d76de045a4e0884a1b1f60db962823e2bdca042e31e17feaee0c050
image_repo_commit=c06fd9b510457f6721be6307aceba3bd1f83c492
embedded_core=c25.3-reference-image-20260713-562939e
embedded_player_fallback=c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4
source_release_gate=82_of_82_clean
offline_image_validation=54_of_54
direct_allocated_rootfs_audit=passed_but_incomplete
forensic_unallocated_block_audit=failed
board_flash=blocked_do_not_flash
remote_c25b_publication=pending
totem_core_stable_alignment=pending
distribution_reference=still_prod8_until_board_e2e
```

O prod9 fechou corretamente a composicao que antes estava pendente: C25A,
C25B, launcher, updater, dependencias de midia e autorizacao exact-target foram
presos a hashes na mesma imagem. Essa parte permanece aproveitavel.

Entretanto, a primeira inspecao verificou somente arquivos alocados. A auditoria
forense independente recuperou configuracao, credenciais de lab e antigas
chaves SSH em blocos ext4 livres. Tambem encontrou o caminho antigo
`overlayroot=tmpfs` ainda ambiguo, identidade SSH potencialmente volatil, marker
de proveniencia antigo e modo `0777` no arquivo de imagem.

Prod9 foi bloqueada antes do flash e removida do caminho normal `.img`. A
sucessora deve zerar e verificar todo o espaco livre, desativar explicitamente
o overlayroot nao shipado, preservar identidade SSH entre reboots, corrigir a
proveniencia e restringir os modos do artefato. Evidencia negativa:
`docs/evidence/c18-update-validation/20260713T155142Z-prod9-build-c06fd9b/`.

## Checkpoint Prod10 - Higiene Verde, Credencial Bloqueada - 2026-07-13

O prod10 corrigiu os bloqueios forenses do prod9: todos os blocos livres e
slacks inspecionados estavam zerados, os residuos exatos do prod9 desapareceram,
overlayroot ficou desativado, a identidade SSH passou a nascer na placa e a
composicao C25A/C25B permaneceu presa aos hashes corretos.

Uma auditoria independente encontrou outro blocker antes do flash: a conta root
continuava ativa com a senha curta herdada da imagem base, quebrada em cerca de
17 segundos por busca offline. Nenhuma placa recebeu o prod10.

```text
candidate_image=c18-hwdecode-prod-10
image_sha256=fb1ba57e0ac2cffdd74169c96b57cde03cccd8b576c9628642a6f51621cc8026
image_repo_commit=94ee655c0593d27d191db0203c81f216aa47c4ae
free_blocks_zeroed=58530_of_58530
forensic_old_lab_residues=absent
root_support_password_strength=blocked_inherited_short_password
board_flash=blocked_do_not_flash
distribution_reference=still_prod8
next_candidate=c18-hwdecode-prod-11
```

O prod11 deve substituir o hash root durante o build a partir de uma credencial
forte guardada fora do Git, recusar arquivo frouxo ou senha fraca, preservar as
permissoes e substituir o verificador tanto em `/etc/shadow` quanto no backup
`/etc/shadow-`, provar que nem o plaintext nem o hash antigo aparecem na imagem
e repetir a auditoria forense completa. O construtor tambem deve recusar fonte
suja, identidade divergente e falha silenciosa de ferramenta; seu marcador final
fecha imagem, hash e evidencias, mas nao substitui o aceite forense para flash.
Evidencia negativa:
`docs/evidence/c18-update-validation/20260713T162710Z-prod10-build-94ee655/`.

## Checkpoint Prod11 - Credencial Verde, Identidade SSH Bloqueada - 2026-07-13

O prod11 substituiu a senha root herdada por uma credencial externa forte,
preservou `/etc/shadow` e `/etc/shadow-`, zerou os blocos livres e removeu
plaintext, verificadores antigos, host keys e identidades de laboratorio. A
composicao offline passou integralmente.

A auditoria da imagem encontrou um blocker de primeiro boot: o inicializador
Dadooh criaria host keys antes do SSH, mas o `armbian-firstrun`, executado depois
do SSH, estava configurado para apaga-las, recria-las e reiniciar o servico. A
identidade final seria unica, mas poderia mudar durante o primeiro acesso. A
expansao automatica do rootfs foi confirmada separadamente e nao e blocker.

```text
candidate_image=c18-hwdecode-prod-11
image_sha256=675b9c9f8c3eb1bcbd90b5fa8fe398841d05d3d55a24d7df36b4ac571ec58922
image_repo_commit=777e1fd730d6c6f6915310a18b6af5ec7a2d8294
credential_hygiene=passed
free_blocks_zeroed=58530_of_58530
rootfs_auto_expand=enabled
ssh_host_identity=blocked_double_regeneration_on_first_boot
board_flash=blocked_do_not_flash
distribution_reference=still_prod8
next_candidate=c18-hwdecode-prod-12
```

O prod12 foi definido para usar o controle oficial
`OPENSSHD_REGENERATE_HOST_KEYS=false`, mantendo as demais tarefas do primeiro
boot do Armbian e deixando somente o inicializador Dadooh como dono da identidade
SSH. Este checkpoint registra o blocker do prod11; o resultado da sucessora esta
no checkpoint seguinte. Evidencia:
`docs/evidence/c18-update-validation/20260713T191534Z-prod11-build-777e1fd/`.

## Checkpoint Prod12 - Auditoria Verde, Placa Pendente - 2026-07-13

O prod12 foi construido no commit `cb89485` e corrige somente o conflito de
identidade SSH do prod11. Quatro revisoes independentes do artefato real nao
encontraram blocker: o inicializador Dadooh e o unico dono efetivo das host
keys, o SSH espera por ele, o restante do firstrun foi preservado e a expansao
automatica do rootfs continua habilitada.

```text
candidate_image=c18-hwdecode-prod-12
image_sha256=4bef1f398635f66202c280b33206c4f7e84503c9d0f8734888a5821bae9d8262
image_repo_commit=cb894852c81d82ecad9320bb24accac81f1827b6
release_gate=82_of_82
offline_validation=66_of_66
independent_reviews=4_go_0_blockers
board_flash=approved_for_one_controlled_validation
distribution_reference=still_prod8
```

O aceite fisico exige boot limpo, rootfs expandido, fingerprint SSH estavel
apos segundo reboot, wizard/QR/configuracao, playback/C25 e
auto-pull/no-op/rollback. Evidencia:
`docs/evidence/c18-update-validation/20260713T200707Z-prod12-build-cb89485/`.

## Checkpoint Prod12 Em Placa E Sucessor C20.14 - 2026-07-14

A prod12 foi gravada e confirmou na placa o marker `c18.image-prod.12`, rootfs
ext4 expandido, wizard/QR/configuracao real, retorno ao player e playback. A
corrida real revelou residuos de ownership e parada da sessao de settings que
nao eram visiveis na auditoria offline.

C20.13 fechou a posse transacional; C20.14 corrigiu a parada pelo systemd sem
mascarar o problema. O pacote C20.14 passou stop abaixo de 15 segundos,
cancelamento normal, rollback, reaplicacao e reboot com health final verde. A
configuracao e o contexto foram preservados e nenhum fault GPU novo apareceu.

```text
board_image=c18-hwdecode-prod-12
board_image_version=c18.image-prod.12
totem_core_current=c20.14-settings-stop-hardening-20260714T034217Z-22bd473
totem_core_previous=c20.13-settings-session-hardening-20260714T023435Z-868e328
release_gate=84_of_84
service_stop=passed_8467ms_result_success
rollback_reapply=passed
post_reboot_health=passed
next_candidate=c18-hwdecode-prod-13
distribution_reference=still_prod8_until_prod13_e2e
```

Como C20.14 foi aplicado depois da gravacao, prod12 nao e promovida como imagem
final. A prod13 deve ser uma derivacao estreita da prod12, mudando apenas a
identidade e o core embutido, seguida de auditoria e um E2E fisico final.
Evidencia:
`docs/evidence/c20-totem-core-ota/20260714T042600Z-c20-14-settings-stop-hardening-board-e2e/`.
