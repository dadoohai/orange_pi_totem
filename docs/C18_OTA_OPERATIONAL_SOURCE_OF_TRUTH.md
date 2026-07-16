# C18 OTA - fonte da verdade operacional

Estado em 2026-07-16. Este documento e o radar curto para decidir os proximos
passos de OTA. O contrato detalhado continua em `docs/UPDATE_CONTRACT.md`; este
arquivo existe para nao perder as decisoes praticas enquanto fechamos a etapa
operacional.

Direcao macro da fase atual: `docs/C18_MACRO_STEERING.md`.

Spec de execucao da fase de producao com auto-pull:
`docs/C18_PRODUCTION_AUTOPULL_SPEC.md`.

Fluxo curto de QA visual do wizard/settings na placa:
`docs/C19_VISUAL_QA_FLOW.md`.

Plano de acumulo UX/produto para a proxima imagem:
`docs/C20_UX_ACCUMULATION_PLAN.md`.

Campanha adversarial rapida de midia/OTA:
`docs/product/196_C22_RAPID_ADVERSARIAL_RELIABILITY.md`.

Decisao para fonte do player e futuros alvos sem regravacao:
`docs/product/198_C24_PLAYER_SOURCE_AND_SCALE_DECISION.md`.

Runbook do marco fisico encerrado de `totem-core`:
`docs/c18-totem-core-production-timer-runbook.md`.

## Definicao pratica

Para produto, "OTA em producao" significa: uma placa consegue receber uma
atualizacao remota, validar o pacote, aplicar, continuar funcional e voltar por
rollback se necessario.

Hoje a C18 tem dois caminhos reais:

- `totem-core`: auto-pull stable C21.12 provado na `prod14` por timer real,
  no-op, rollback, restauracao e reboot;
- `player-runtime`: auto-pull de producao fechado somente para o alvo exato
  C25B `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`, com timer
  real, no-op, rollback, reaplicacao e 600 segundos continuos limpos. Qualquer
  alvo futuro continua bloqueado ate nova autorizacao presa por hashes.

Estado de distribuicao vigente: `prod14` + C25B + C21.12 e a referencia aceita.
A candidata completou na placa o E2E fisico dos dois componentes, reboot final,
reproducao estrita, gate global e tres auditorias independentes sem blocker.
`prod8` + C23 passa a ser a referencia anterior. `prod9`, `prod10`, `prod11` e
`prod13` continuam bloqueadas pelos achados registrados no historico abaixo;
`prod12` permanece bancada intermediaria, nao imagem final.

O M5 anterior nao deve ser reaberto. A arquitetura C24 para reconciliar
a fonte e autorizar alvos futuros sem regravacao esta aprovada, mas foi movida
para roadmap. A prioridade volta ao produto visivel e a jornada de ativacao,
incluindo o caso recuperavel que uma vez exigiu `F5`. M4 continua em paralelo;
grupos, dashboard e telemetria seguem no roadmap.

## Repositorio de entrega

O repo de entrega C18 e `dadoohai/orange_pi_totem`.

Ele contem imagem/SO, wizard, scripts de boot, OTA, gates, documentacao,
empacotamento e o snapshot governado do player em
`player-runtime/kiosky-player/kiosk.py`.

O repo `kiosky-player`, branch `appliance-v0.1`, sera a fonte editavel do
comportamento depois da convergencia C24. Ele nao publica direto para placas.
Toda entrega para cliente continua passando por um snapshot de commit exato na
frente `player-runtime` do fluxo C18. Ate a convergencia fechar, o snapshot
C25B e a verdade funcional da candidata `prod14`.

Nota de nome: em runtime o servico ainda pode se chamar `kiosky-player.service`.
Isso nao torna `kiosky-player` uma rota de release C18. O launcher C18 deve
adotar `/data/player-runtime/current` quando houver marker valido e cair para a
imagem/fallback quando nao houver.

## Frentes de update

| Frente | O que entra | Caminho permitido agora |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, helpers, validadores, settings e UX operacional da placa | auto-pull de producao fechado; dry-run, apply, timer e rollback provados |
| `player-runtime` | `kiosk.py`, comportamento do player, timing, sync, duracao, playlist, flags de MPV no player | auto-pull production fechado para C25B exato; futuros alvos exigem nova autorizacao hash-bound |
| `kiosky-player` legado | rota historica do player | nao usar como caminho de release C18 |
| `media-system` | MPV, ffmpeg, hwdecode, kernel, DTB, U-Boot, BSP, imagem base | nova imagem + homologacao, nao OTA comum |
| `field-data` | midia, config real, cache, playlist, estado local | fluxo operacional de dados, nao release de software |
| `server-side/publish` | GitHub Release, assinatura, allowlist, rollout, auditoria | publicar/validar artefatos; nao aplica por si so na placa |

## Regras que nao devem ser esquecidas

1. Nao existem dois deploys concorrentes do player: `kiosky-player` legado nao
   publica para C18; `player-runtime` e a rota de entrega.
2. `totem-core` nao pode carregar launcher do player, MPV, midia, config,
   cache, systemd, kernel ou updater novo.
3. `player-runtime` nao pode carregar MPV/ffmpeg/kernel/midia/config/cache; o
   pacote atual e deliberadamente estreito.
4. Auto-pull de `totem-core` C21.12 e de `player-runtime` C25B estao provados; isso nao
   autoriza `latest` amplo nem futuros pacotes de player por inferencia.
5. Regravar imagem em laboratorio e permitido como reset/prova, mas nao conta
   como OTA de producao.
6. Toda atualizacao real precisa ter dry-run, apply, validacao e rollback.

## Modo De Acumulo Para Proxima Imagem

Decisao em 2026-07-07: as proximas rodadas de produto devem ser acumuladas como
marcos validados, em vez de publicadas individualmente por padrao.

Regra pratica:

- cada rodada pequena deve ter escopo claro, evidencia e non-claims;
- quando passar em placa/gates, entra no radar como `validada para acumulo`;
- o pendente macro passa a ser gerar o pacote/update consolidado e, depois, a
  nova imagem de referencia;
- nao publicar/promover cada rodada isolada salvo decisao explicita;
- se uma rodada tocar outra frente (`player-runtime`, display, Wi-Fi real,
  media-system), ela deve continuar separada e nao contaminar o pacote de
  `totem-core`.

Fila atual para consolidacao:

- C19/C20, QR C21 e os estados C25A foram acumulados no `totem-core` ate o
  pacote C20.14
  `c20.14-settings-stop-hardening-20260714T034217Z-22bd473`. O pacote passou
  gate `84/84`, apply governado, parada forcada limitada, cancelamento normal,
  rollback, reaplicacao e reboot com health final verde na placa prod12. Ele e
  agora a entrada exata da prod13; ainda nao e uma release `stable` remota.
- A jornada real de wizard, QR, ambiente, escrita e retorno ao player passou na
  prod12. C20.13 e C20.14 fecharam os residuos de ownership/cleanup descobertos
  ao interromper a sessao por systemd, sem mascarar a causa.
- Estados visiveis C25A (`totem-core`) e C25B (`player-runtime`) estao
  validados e reversiveis. O alvo C25B final
  `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4` foi incorporado
  na prod12 e executa como baseline da imagem; sua publicacao/auto-pull futuro
  continua exigindo o alvo exato e autorizacao presa por hashes. Contrato e
  evidencias estao em `docs/product/199_C25_VISIBLE_PRODUCT_STATES.md` e
  `docs/evidence/c25-visible-states/20260713T082118Z-c25b-still-final-board/`.
- Continuar novas melhorias de wizard/status por `totem-core`, uma vertical de
  uso por rodada, preservando o QA C19/C20.
- Retomar a matriz de compatibilidade de display quando as telas alvo estiverem
  disponiveis; ate la, manter apenas diagnostico read-only.
- `prod9` foi gerada no commit `c06fd9b`, SHA256
  `4a413bc84d76de045a4e0884a1b1f60db962823e2bdca042e31e17feaee0c050`,
  com core consolidado C25.3 e autorizacao C25B exact-target. Passou gate
  `82/82` e validacao offline `54/54`, mas a varredura inicial cobria somente
  arquivos alocados. A auditoria independente recuperou dados apagados em
  blocos livres e bloqueou a imagem antes do flash. Evidencia negativa em
  `docs/evidence/c18-update-validation/20260713T155142Z-prod9-build-c06fd9b/`.
- `prod10`, commit `94ee655`, SHA256
  `fb1ba57e0ac2cffdd74169c96b57cde03cccd8b576c9628642a6f51621cc8026`,
  eliminou os residuos e zerou 58530/58530 blocos livres, mas a auditoria
  quebrou a senha root curta herdada em cerca de 17 segundos. Tambem foi
  bloqueada antes do flash. Evidencia negativa em
  `docs/evidence/c18-update-validation/20260713T162710Z-prod10-build-94ee655/`.
- `prod11`, commit `777e1fd`, SHA256
  `675b9c9f8c3eb1bcbd90b5fa8fe398841d05d3d55a24d7df36b4ac571ec58922`,
  fechou a credencial forte e toda a higiene anterior. A auditoria encontrou,
  porem, o inicializador Dadooh criando host keys antes do SSH e o
  `armbian-firstrun` apagando-as e recriando-as depois. Nenhuma placa recebeu a
  imagem. Evidencia negativa em
  `docs/evidence/c18-update-validation/20260713T191534Z-prod11-build-777e1fd/`.
- `prod12`, commit `cb89485`, SHA256
  `4bef1f398635f66202c280b33206c4f7e84503c9d0f8734888a5821bae9d8262`,
  passou gate `82/82`, validacao offline `66/66`, quatro auditorias e foi
  gravada. A placa confirmou o marker `c18.image-prod.12`, rootfs ext4
  expandido e o E2E de produto usado para fechar C20.14. Evidencias:
  `docs/evidence/c18-update-validation/20260713T200707Z-prod12-build-cb89485/`
  e
  `docs/evidence/c20-totem-core-ota/20260714T042600Z-c20-14-settings-stop-hardening-board-e2e/`.
- `prod13`, commit `61e3abd`, SHA256
  `4918796e08a1a0147c797ac64fa0629a6d2d340fa21902c78a629f62db89ac3e`,
  foi construida e auditada como sucessora estreita: identidade nova, core
  C20.14 e guard transacional image-bound. Boot region, kernel, initrd, DTB,
  U-Boot, player-runtime e pilha de midia ficaram identicos a prod12; nenhum
  delta inesperado foi encontrado. O flash controlado passou boot, expansao,
  SSH, wizard/QR/writer, playback, timers, bloqueio de downgrade e guard de
  settings. O alvo C25B exato foi publicado sem mover `latest`. Evidencia de
  build:
  `docs/evidence/c18-update-validation/20260714T045929Z-prod13-build-61e3abd/`.
- O timer real da prod13 baixou e verificou C25B, mas rejeitou o candidato
  porque o health comecou antes da primeira publicacao de status. O candidato
  tinha HW decode, frames avancando e zero restart/fault. A repeticao exata com
  espera de oito segundos e canario cobrindo toda a janela passou todos os
  checks sem mudar limites. A prod13 nao sera promovida. Evidencia:
  `docs/evidence/c18-update-validation/20260714T145543Z-prod13-player-startup-window-rca/`.
- A candidata `prod14`, SHA256
  `3d93f05f896c8e7c17866129a901a02803e65d7968ed69eac3987b03a4b02682`,
  foi construida no commit `59a1b7c` e auditada como sucessora estreita,
  limitada a identidade nova,
  `--startup-wait-sec 8` na unit production e ao canario isolado cobrindo toda
  a janela de health. Duas comparacoes independentes do rootfs real confirmaram
  boot region, kernel, initrd, DTB, U-Boot, C20.14, C25B e pilha de midia
  preservados, sem delta inesperado. O marcador interno foi extraido da imagem
  e tem SHA256
  `ef56eec47a977bb4f0d8d3f50a7934ae0ac5b1219fa52eaccb76f8483c4fb8f2`.
  Seu E2E provou timer, apply, no-op, rollback para o fallback da imagem,
  reapply, `rc=44`, reboot e playback estrito final. O timer real do core
  aplicou a stable C21.12, tambem passou no-op, rollback e restauracao. As
  evidencias estao em
  `docs/evidence/c18-update-validation/20260714T200704Z-prod14-player-runtime-production-autopull-c25b/`
  e
  `docs/evidence/c18-update-validation/20260714T212827Z-prod14-core-stable-and-final-reboot/`.
  O construtor de producao recusa arvore suja, identidade de candidata
  divergente, ferramentas ext4 diferentes das fixadas, espaco insuficiente e
  erro de `debugfs`. Imagem, hash e evidencias so formam um conjunto completo
  quando o marcador `.ready.json` e publicado por ultimo, sem autorizar flash:
  a auditoria forense externa continua obrigatoria.
- Antes do build da prod14, o coletor e o gate de evidencia foram endurecidos
  contra reutilizacao de health antigo, invocacao de player reaproveitada,
  quarantine no alias legado, marker/freeze sem vinculo exato e residuos `{}`.
  Os testes passaram `12/12` e `54/54`; a reauditoria adversarial nao encontrou
  brecha restante nesse escopo. A rota exact-target ganhou
  `--verify-existing` para baixar e conferir o release C25B ja publicado sem
  republicar nem mover `latest`; a execucao real passou e esta em
  `docs/evidence/c18-update-validation/20260714T171607Z-c25b-existing-release-verification/`.
  Isso e governanca pre-build, nao evidencia E2E da prod14. Evidencia de build
  e auditoria pre-flash:
  `docs/evidence/c18-update-validation/20260714T173015Z-prod14-build-59a1b7c/`.
- A convergencia C24 e o controle assinado de novos players ficam no roadmap
  conforme a decisao 198.

## O que fechamos

- Power-loss fisico do `player-runtime`: 17/17.
- H2 final do alvo `9bebaf1`: verde por excecao formal de negocio.
- Stable promotion e thaw decision: registrados para o alvo.
- GitHub Release de `player-runtime`: publicada com 18 assets em
  `player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`.
- Target `player-runtime`: source commit
  `9bebaf1d37d4574ff2fec69ae8db2a9ffdf7b522`; payload SHA256
  `d363fe3af9e3ca267123d3d4c324faefb2392cf04d4884d36e153074e6b758a0`.
- Gate global C18: verde em `5890218`.
- Marco 1 `totem-core` remoto: fechado em 2026-07-05. A placa lab selecionou
  a GitHub Release
  `totem-core-c18.ota-core-m1-20260705T001743Z-140e706`, aplicou com
  `rc=0`, manteve `kiosky-player.service` ativo e rollbackou com `rc=0`.
  Evidencia em
  `docs/evidence/c18-update-validation/20260705T002405Z-totem-core-remote-m1-140e706/`.
- Marco 2 `player-runtime` remoto: fechado em 2026-07-05. A placa lab consumiu
  a GitHub Release exata
  `player-runtime-c18.player-runtime-homolog-20260617-mpv-stuck-fix-9bebaf1`,
  validou 18 assets, payload SHA e release gate, aplicou com `rc=0`, manteve o
  CLI publico congelado com `rc=44`, reiniciou o servico, passou deep-health
  real, executou rollback com `rc=0`, e terminou restaurada no alvo
  `9bebaf1` com health estabilizada verde. Evidencia em
  `docs/evidence/c18-update-validation/20260705T150628Z-player-runtime-github-m2-hdmi-9bebaf1/`.
- RCA C21 de tela preta por PNG: fechado em 2026-07-09. A placa lab aplicou o
  release `c18.player-runtime-homolog-20260709-image-transcode-50919f5`, saiu
  de `waiting_for_media/all_media_temporarily_blocked` para `playing` com
  `current_item.path=*.png.h264.mp4` e `source_path` no PNG original.
  Evidencia em
  `docs/evidence/c21-player-runtime-image-transcode/20260709T045504Z-board-lab-apply/`.
- C22 confiabilidade adversarial rapida: prova de placa fechada em 2026-07-10.
  O player passou a rejeitar midia que nao decodifica primeiro frame, reconstruir
  sidecar invalido e preservar last-known-good com estado stale explicito. A
  campanha real cobriu playlist mista, API 500/vazia, download truncado,
  sidecar corrompido e recuperacao; observou 8 transicoes, nenhum preto
  persistente e restaurou o player real saudavel. O updater ganhou limites de
  pacote compactado/expandido, reserva de disco, staging local verificado,
  permissoes de extracao normalizadas, staging sem symlink e lock de reconcile.
  Evidencia:
  `docs/evidence/c22-rapid-adversarial/20260710T045119Z-board-governed-final/`.
  O pacote governado alvo e
  `c18.player-runtime-homolog-20260710-c22-c023eae`, payload SHA256
  `4b5ee5435be0fb3d21d0cf3661c5eac94a9348aa77e1cd8f5613d5ee66740e16`.
  O roundtrip apply/rollback/reapply passou na placa, com dois deep-health
  verdes, playback real em cada etapa e C22 final em `current`; evidencia em
  `docs/evidence/c22-rapid-adversarial/20260710T050658Z-package-roundtrip-c023eae/`.
  Non-claim: zero frame preto requer captura HDMI; publicacao e reancoragem do
  auto-pull pertencem ao M5.
- C23 backpressure IPC: causa e correcao fechadas na placa em 2026-07-10. O
  pacote `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`, payload SHA256
  `88471756039a492a6857c2b8c37fbac4a4ff56602f0934729960fc77d6d94f80`,
  remove a conexao persistente sem leitura e serializa comandos/consultas em
  conexoes fresh. Apply, rollback para C22 e reapply passaram. A observacao
  decisiva de 10 minutos percorreu nove midias sem erro/restart/watchdog; 120
  amostras paralelas mantiveram o mesmo PID e fila de saida zero. A evidencia
  esta em
  `docs/evidence/c23-player-runtime-ipc-backpressure/20260710T195427Z-board-roundtrip/`.
  O target exato C23 foi publicado com tres assets e hashes remotos conferidos;
  evidencia em
  `docs/evidence/c18-update-validation/20260710T211259Z-c23-exact-publication/`.
  A prova local nao substituiu a prova production: ela foi completada na prod8
  em 2026-07-11, conforme o marco abaixo.
- Drift operacional: o alvo antigo `9bebaf1` do timer foi substituido por C22
  na prod7. Depois do apply lab C23, a placa executa C23 como `current`, mas o
  timer production continua autorizado somente para C22 ate a prod8. A
  protecao de downgrade permanece ativa; o ajuste deve trocar autorizacao e
  imagem de forma atomica, sem desabilitar o guard.
- Preparacao M5 off-board em 2026-07-10: o alvo canonico passou a ser o C23
  `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`. A autorizacao esta em
  `scripts/board/player_runtime_production_autopull.json`; ela bloqueia
  `latest`, prerelease e downgrade e esta presa aos hashes do pacote. A rota
  `publish_player_runtime_exact_target_release.sh` publica somente os tres
  assets exatos sem mover GitHub `latest`. A prova historica C22 cobre
  auto-apply, no-op, rollback autorizado e restauracao. A nova prova production
  C23 deve repetir esse round-trip a partir de uma imagem prod8 que carregue a
  autorizacao C23.
- Preparacao prod8 off-board em 2026-07-10: o novo core canonico e
  `c21.9-prod8-pairing-restore-20260710T225825Z-665fc01`, source commit
  `665fc01ac5b1df19c44ae5bb911d6ae67e3816cd`, payload SHA256
  `2c4123aed190c243e2e65bd1a477237717e93db14e69716dfb14f8c280fdd01b`.
  O QR deixa de depender da hora da placa e espera o estado terminal do
  servidor sob watchdog monotonic bounded; a restauracao do player usa start
  no-block limitado e registra o resultado. A identidade prevista passa a ser
  `c18-hwdecode-prod-8` / `c18.image-prod.8`. A imagem final foi construida no
  commit `314ddd1`, SHA256
  `6c3801d970d7bc5248f4c8fc5838b4233ea2e9e1f2120de4bffd7bea07f063ee`,
  e recebeu dois GO independentes para flash de bancada; evidencia em
  `docs/evidence/c18-update-validation/20260710T232544Z-prod8-build-314ddd1/`.
  Validacao em placa em 2026-07-11: primeiro boot, wizard/QR, writer privado e
  playback passaram. O timer production original aplicou o C23 remoto exato;
  no-op, rollback para o bridge e restauracao C23 passaram. A janela final de
  600 segundos ficou limpa e o gate M5 v2 passou com mecanica e limpeza para
  distribuicao verdes, sem blockers. Evidencia em
  `docs/evidence/c18-update-validation/20260711T175205Z-prod8-m5-production-autopull-c23/`.
  O freeze generico continua em `rc=44`; o resultado autoriza somente o alvo
  C23 preso por hashes, nao `latest` amplo nem pacotes futuros.

  Observacao paralela: o timer de `totem-core` tentou a stable remota antiga e
  recebeu `rc=45` por downgrade sobre o C21.9 embutido, sem mutar o core. O
  alinhamento da publicacao/promotion do core atual e pendencia operacional
  separada e nao invalida o round-trip C23.
- Correcao de imagem M5: `prod-5` limpou o seed do player, mas a auditoria do
  artefato encontrou firstboot privado com Wi-Fi/senhas, servico lab habilitado,
  marcadores contraditorios e chaves SSH clonadas herdados da base. `prod-5`
  esta bloqueada. `prod-6` removeu esses artefatos e passou a gerar chaves SSH
  unicas no primeiro boot, mas foi bloqueada porque o servico do wizard ainda
  chamava a politica lab/homologacao. `prod-7` substitui esse caminho por
  politica de producao fail-closed e remove o helper lab. Prod-1 a prod-6 nao
  sao distribuicao M5.
- Proveniencia do core em `prod-7`: o current embarcado e
  `c21.8-production-settings-policy-20260710T161120Z-d79e4bd`, gerado do commit
  `d79e4bdb0d77b11441d5abe9473bfce1cd4426f2` e preso ao payload SHA256
  `4a1f58ba5caecb3f124d02c834a5d3f71b6c2701a8f2f596f22dad0d594cd105`.
  O builder compara cada arquivo de `bin/` com esse pacote antes de criar a
  imagem.
- Marco 3 imagem producao offline: fechado em 2026-07-05. O repo tem um
  builder explicito para imagem C18 producao e o build gerou
  `c18-hwdecode-prod-1` com `artifact_private=false`, `final_image=true`,
  policy `stable`, `allowed_components=["totem-core"]` e timer habilitado.
  SHA da imagem:
  `9b10788031b9bf4884cd49169799b56d995fa56f8cb185c846bb7b485e1dc89e`.
  Evidencia em
  `docs/evidence/c18-update-validation/20260705T175747Z-prod-image-build-44bfbd0/`.
- Separacao de `totem-core stable`: o caminho de stable do core passa a ter gate
  proprio, evidencia propria, assets de imagem de producao e non-claims
  explicitos. Isso autoriza somente auto-pull do core; nao abre thaw nem stable
  de `player-runtime`.
- Marco 4 `totem-core stable`: fechado em 2026-07-05. A GitHub Release
  `totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1` foi publicada como
  `stable`/nao-prerelease, com 6 assets validados, payload SHA256
  `613d9d6d1099636d7ca956c72e3927d502f1281068f8b0830b2d5f3ba2af0355` e tag
  apontando para o `source_commit`
  `ccaf5a11775d122dd08512c9f5cf1e3027e5a29b`.
- Prova lab `totem-core stable`: a placa lab, com policy temporariamente
  alterada para `stable`, selecionou a release publicada, aplicou com sucesso,
  passou self-test, manteve `kiosky-player.service` ativo com `NRestarts=0`,
  rollbackou para `c17.6-environment-input-20260514T211247Z` e teve a policy
  original restaurada. Evidencia em
  `docs/evidence/c18-update-validation/20260705T185806Z-totem-core-stable-lab-apply-rollback-ccaf5a1/`.
- Marco anterior `totem-core` auto-pull em imagem de producao: fechado em
  2026-07-05.
  A placa foi gravada com a imagem `c18-hwdecode-prod-1`, bootou com policy
  `stable`, timer habilitado, aplicou automaticamente a release stable
  `totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1`, manteve
  `kiosky-player.service` ativo com `NRestarts=0`, preservou o freeze publico
  de `player-runtime` com `rc=44`, e rollbackou para
  `c17.6-environment-input-20260514T211247Z`. Depois da prova de rollback, foi
  restaurada para a release stable pretendida via servico governado. Evidencia em
  `docs/evidence/c18-update-validation/20260705T202923Z-totem-core-production-timer-91f6ae7/`.
  Coletor/gate desse marco:
  `scripts/board/c18_totem_core_production_timer_collect.py` e
  `scripts/qa/c18_totem_core_production_timer_evidence_gate.py`.

## Estado operacional atual

### Marco 1 - `totem-core` remoto na placa

Objetivo: provar que conseguimos atualizar wizard/produto remotamente.

Status: fechado em 2026-07-05 como prova mecanica de OTA remoto `totem-core`.
O pacote foi fresco a partir do HEAD e nao introduziu mudanca funcional de UX.

Checklist minimo:

- gerar pacote `totem-core` pequeno e rastreavel;
- nao reutilizar pacotes historicos em `releases/core-updates` que nao passem
  no gate C18 atual;
- publicar no canal correto;
- na placa, fazer dry-run e confirmar que seleciona exatamente a release;
- aplicar;
- validar wizard/core/status e player ainda saudavel;
- executar rollback;
- registrar evidencia curta.

Depois desse marco, melhorias de wizard e produto podem seguir pelo OTA
`totem-core` com seguranca pragmatica.

### Marco 2 - `player-runtime` remoto na placa

Objetivo: provar que a release publicada do player pode ser consumida pela placa.

Status: fechado em 2026-07-05 como prova de consumo remoto assistido de
`player-runtime`. A release publicada foi baixada pela placa a partir do GitHub,
validada, aplicada, revertida por rollback, e restaurada ao alvo final com
playback real verde.

Checklist executado:

- partir de imagem base conhecida, regravada se necessario;
- confirmar estado inicial da placa;
- fazer a placa localizar e consumir a GitHub Release publicada do
  `player-runtime`, nao um tarball local copiado manualmente;
- validar manifest, hashes e assets;
- aplicar/thaw pelo caminho C18, sem usar publisher ou scripts legados de
  `kiosky-player`;
- validar playback real;
- testar rollback;
- registrar evidencia curta.

Depois desse marco, mudancas futuras de player devem seguir como
`player-runtime`.

Claim permitido apos esse marco: "a placa consumiu remotamente a release
publicada, adotou o alvo e validou playback sob janela controlada". Nao dizer:
"auto-pull ligado", "rollout automatico", "media-system validado", "novo soak
limpo" ou "manifest stable de player-runtime".

Negativos de pacote/hash/canal continuam cobertos por gates offline e pelo
release gate; nao foram repetidos como mutacao de placa nesta corrida HDMI.

## Estado da referencia e pendencias

- `prod14` + C25B + C21.12 e a referencia de producao comprovada. `prod8` + C23
  permanece somente como referencia anterior;
- `prod9` esta **bloqueada e nao deve ser gravada**. Seu SHA256 e
  `4a413bc84d76de045a4e0884a1b1f60db962823e2bdca042e31e17feaee0c050`.
- `prod10` tambem esta **bloqueada e nao deve ser gravada**. Ela resolveu os
  residuos forenses do prod9, mas manteve uma senha root herdada de quatro
  digitos; seu SHA256 e
  `fb1ba57e0ac2cffdd74169c96b57cde03cccd8b576c9628642a6f51621cc8026`;
- `prod11` tambem esta **bloqueada e nao deve ser gravada**. Ela fechou
  credencial e higiene, mas recriaria a identidade SSH duas vezes no primeiro
  boot; seu SHA256 e
  `675b9c9f8c3eb1bcbd90b5fa8fe398841d05d3d55a24d7df36b4ac571ec58922`;
- `prod12` foi construida, auditada e gravada preservando a credencial forte e
  toda a higiene. A placa confirmou a expansao do rootfs e o produto real; os
  refinamentos C20.13/C20.14 surgidos nessa corrida foram validados por OTA;
- `prod13` foi construida, auditada e gravada. Boot, identidade SSH, wizard/QR,
  configuracao, retorno a midia e playback passaram. O timer baixou e verificou
  C25B, mas o health iniciou antes do status ficar pronto; a rejeicao foi segura
  e `prod13` nao deve ser promovida;
- os tres assets exatos de C25B foram publicados sem mover `latest`. A arvore
  exata passou na placa com oito segundos de espera e um canario que cobre toda
  a observacao, sem afrouxar os limites do health;
- a `prod14` foi gravada do zero e concluiu timer, apply exato, no-op, rollback
  para o player embutido, reapply, freeze `rc=44`, reboot e playback estrito;
- o core consolidado foi promovido como stable C21.12 e concluiu timer real,
  no-op, rollback e restauracao sem downgrade;
- gate global e tres auditorias independentes terminaram sem blocker; a
  `prod14` substitui a `prod8` como imagem de referencia;
- manter como frente separada o RCA da ativacao que uma vez ficou em espera ate
  `F5`; o onboarding concluiu, mas a experiencia ainda nao e considerada
  encerrada por esse caso;
- manter futuras evolucoes separadas: `totem-core` para wizard/core e
  `player-runtime` para comportamento do player. Grupos, dashboard e kill
  switch continuam roadmap M6 e nao bloqueiam a primeira escala aceita.

Risco aceito para esta primeira escala: SSH root por uma senha compartilhada de
alta entropia permanece para suporte; credencial por device e M6. A excecao nao
permite senha curta, plaintext, Wi-Fi/identidade de lab ou host keys reutilizadas
na imagem.

Hardenings nao bloqueantes apontados pela auditoria do marco anterior de
`totem-core` auto-pull:

- pinning mais forte do resumo `c18-ota-release-gate.json` anexado a releases
  `totem-core stable`, para evitar aceitar um summary verde porem antigo;
- pinning explicito do SHA da imagem e do SHA do marker no production timer
  gate, alem dos campos do marker ja validados;
- revalidacao completa de timer/policy no resumo de rollback, nao apenas no
  resumo pos-timer e no estado final.

## Direcao de producao por decisao de negocio

Decisao operacional em 2026-07-05: o cliente quer escala rapidamente e aceita o
risco de negocio. A direcao passa a ser producao em escala com auto-pull como
padrao, preservando a governanca tecnica minima para nao quebrar placa e manter
rollback.

Leitura pratica:

- novas placas devem sair com a `prod14`, C25B como
  fallback/target exato do player e C21.12 como stable atual do core;
- `totem-core` e o auto-pull padrao para wizard e produto; apply remoto, no-op,
  rollback, restauracao e reboot estao provados na placa;
- `player-runtime` esta fechado para C25B por caminho pinado/hash-bound, health
  real e rollback. Futuros alvos continuam exigindo autorizacao exata;
- como ainda nao ha infraestrutura real de grupos, dashboard ou monitoramento
  de frota, a primeira producao deve assumir rollout simples/global e registrar
  isso como risco aceito, com inventario manual e procedimento de emergencia;
- staged rollout, allowlist por grupos, assinatura consumida no device,
  kill-switch e telemetria ficam no roadmap de robustez, nao como bloqueio para
  a primeira entrega se a decisao de negocio for avancar.

Resultado dessa decisao: a linha de producao pragmatica foi materializada:

1. imagem `prod14`, sem marcador `not_for_production`;
2. policy de producao e timer habilitado para auto-pull de `totem-core`;
3. timer real aplicando update remoto, no-op, rollback e restauracao;
4. especificacao curta para devs e fabrica;
5. ponte publica exact-target para C25B, com rollback e health real;
6. auditoria final concluida; `prod14` e a referencia aceita.

## Historico V3/M5 - C22/prod7

Esta secao preserva a rodada que abriu a mecanica production exact-target em
C22/prod7. O estado vigente esta no topo deste documento; este historico nao e
a rodada atual.

Decisao: avancar com auto-pull de `player-runtime` em producao pragmatica,
assumindo risco de negocio e preservando as barreiras tecnicas que evitam
regressao silenciosa.

Claim permitido ao final da rodada: uma placa C18 em imagem de producao aplicou
automaticamente o `player-runtime` exato autorizado, validou hashes/manifest,
gerou marker valido no device, passou health real, manteve rollback e recusou
alvos nao autorizados.

Atualizacao de alvo em 2026-07-10: o sucessor escolhido e
`c18.player-runtime-homolog-20260710-c22-c023eae`, que inclui o tratamento de
imagens do C21 e os endurecimentos rapidos C22. `9bebaf1` e C21 permanecem
historicos/baseline de ensaio, nao alvo de producao atual.

Nao-claims:

- nao e `latest` amplo para qualquer `player-runtime` futuro;
- nao publica direto pelo repo/caminho legado `kiosky-player`;
- nao altera MPV, ffmpeg, kernel, imagem base, midia original ou config;
- sidecar/cache local de playback faz parte do `player-runtime` corrigido;
- nao entrega dashboard, grupos/canary, telemetria ou kill switch completo;
- nao reclassifica evidencia antiga como prova de novo alvo.

Passos minimos:

1. construir e inspecionar a imagem production nova com updater e autorizacao
   C22 exatos;
2. publicar tag/assets C22 pelo publisher exact-target, sem alterar `latest`;
3. preparar o bridge rollback-safe
   `c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63` como current de
   bancada e coletar o preflight M5; C21 foi rejeitado pelo health nesta
   preparacao e permanece corretamente em quarantine;
4. deixar o timer real aplicar C22 e coletar deep-health/marker/state;
5. executar no-op, rollback autorizado e segunda troca autorizada para
   restaurar C22;
6. rodar o gate de cinco fases e auditoria final de regressao: `totem-core`
   continua funcionando, `kiosky-player` legado continua fora e `media-system`
   continua fora do OTA.

Runbook curto: `docs/c18-player-runtime-production-autopull-runbook.md`.

Resultado em 2026-07-10: M5 fechado. Na imagem `c18-hwdecode-prod-7`, o timer
real aplicou o C22 remoto exato, o no-op preservou state/links/marker, o
rollback autorizado voltou ao bridge e a segunda troca restaurou C22. Todas as
cinco fases passaram deep-health, mantiveram o freeze publico `rc=44` e deixaram
C22 ativo com o bridge como `previous`. C21 rejeitado permaneceu em quarantine.

Evidencia decisiva:
`docs/evidence/c18-update-validation/20260710T190539Z-prod7-m5-production-autopull-c22/`.

O marco fecha auto-pull de `player-runtime` para o alvo C22 explicitamente
autorizado. Nao abre `latest` amplo nem autoriza releases futuros por inferencia.

## Rodada C19 - pacote `totem-core` de wizard/settings

Decisao em 2026-07-07: C19.2 + C19.3 formam um pacote pequeno e coerente de
`totem-core`, validado como homologacao controlada na placa.

Pacote:

- versao: `c19.visual-settings-20260707T205630Z-5df93c1`;
- canal: `homologation`;
- source commit: `5df93c1`;
- pacote/gate commitado em `df7865e`;
- gate especifico C18: verde;
- apply/rollback local em placa: verde.

Claim permitido do pacote:

- melhoria visual e operacional do wizard/settings;
- lista Wi-Fi em paisagem sem invadir rodape;
- PageDown/PageUp coerentes com a pagina visivel;
- `Esc` na tela inicial encerrando settings sem deixar service `failed`;
- indicador de sinal Wi-Fi legivel em ASCII;
- sem escrita real de Wi-Fi/config.

Nao-claims:

- nao valida Wi-Fi real/persistente em campo;
- nao valida escrita real de `/data/config/config.json`;
- nao corrige EDID/resolucao/display fallback;
- nao muda player, MPV, media-system, field-data, updater ou kernel;
- nao substitui M5 `player-runtime` auto-pull.

Sequencia executada:

1. Commit limpo contendo codigo, docs e evidencias C19 intencionais.
2. Pacote `totem-core` gerado sem `--allow-dirty`.
3. Release gate especifico do pacote e gate global C18 verdes.
4. Validacao na placa com policy temporaria de homologacao:
   apply-local, self-test, playback deep-health curto, rollback e restauracao.
5. Estado final da placa restaurado: `stable`, `allow_prerelease=false`,
   timer ativo/habilitado, `current` C18 e `previous` C17.6.

Evidencia:

- `releases/core-updates/c19.visual-settings-20260707T205630Z-5df93c1/`;
- `docs/evidence/c19-totem-core-ota/20260707T211121Z-apply-rollback/`.

Intencao macro:

- acumular C19 com as proximas rodadas pequenas de `totem-core`;
- depois gerar pacote/update consolidado;
- depois compilar a nova imagem de referencia com esse conjunto validado.
  Ate essa consolidacao, C19 esta validado em homologacao, mas nao publicado
  isoladamente como stable.

Decisoes de escopo:

- Display/EDID segue na frente M7/display-profile. Forcar resolucao pertence a
  `media-system`/imagem, nao a `totem-core` comum.
- Wi-Fi real/config real segue como frente de bancada separada. Nao bloqueia o
  pacote C19 se o claim continuar visual/operacional.

## Rodada C20 - acumulacao UX de wizard/settings

Decisao em 2026-07-07: C20 continua a linha de acumular melhorias pequenas de
`totem-core` antes de gerar um pacote consolidado e uma nova imagem de
referencia.

Estado atual:

- C20 V0 validada: primeira tela de orientacao sem sobreposicao entre preview e
  painel lateral.
- C20 V1 validada: wizard recalibrado para o framebuffer atual `1024x768`,
  lista Wi-Fi em paisagem com 4 itens sem invadir rodape e revisao com resumo
  publico no corpo principal.
- C20 V2 validada: cards mais solidos, marcador renderizavel no framebuffer,
  rodape como barra de acoes, `Esc` preservado em rodapes longos, campo de
  entrada integrado ao tema escuro e revisao reposicionada como decisao
  `Pronto para concluir`.

Evidencias principais:

- `docs/evidence/c20-visual-qa/20260707T192000-c20-v0-final-preview-board/`;
- `docs/evidence/c20-visual-qa/20260707T224916Z-c20-v1-layout-preview-board/`;
- `docs/evidence/c20-visual-qa/20260707T225600Z-c20-v1-wifi-landscape-board-clean/`;
- `docs/evidence/c20-visual-qa/20260707T225800Z-c20-v1-review-landscape-board/`;
- `docs/evidence/c20-visual-qa/20260707T235900Z-c20-v2-pdca1-board-preview/`;
- `docs/evidence/c20-visual-qa/20260708T000400Z-c20-v2-pdca2-board-preview/`;
- `docs/evidence/c20-visual-qa/20260708T000700Z-c20-v2-review-decision-board/`;
- `docs/evidence/c20-visual-qa/20260708T001336Z-c20-v2-final-local-verification/`.

Non-claims:

- C20 ainda nao foi empacotado nem publicado por OTA;
- nao mexe em player-runtime, Wi-Fi real, display/EDID, updater, imagem ou
  media-system;
- captura de preview nao substitui fluxo completo por teclado quando a rodada
  depender de interacao real.

Proximo marco recomendado: continuar V3/V8 ou fechar um pacote consolidado de
`totem-core` quando o conjunto de UX estiver suficiente para uma imagem de
referencia.

Rodada de inspeção em placa em 2026-07-08:

- pacote `totem-core` de homologacao
  `c20.visual-settings-20260708T003000Z-4e3a13d` gerado e aplicado localmente;
- a placa ficou com C20 como `current` e wizard aberto para inspeção humana;
- evidencia em
  `docs/evidence/c20-totem-core-ota/20260708T004241Z-visible-apply/`;
- pendente: rollback/restauracao apos inspeção ou decisão explicita de manter
  C20 aplicado; depois consolidar no pacote/update final e na proxima imagem de
  referencia.

## Rodada C21 - ativacao real por QR/codigo

Objetivo macro: uma placa nova deve conseguir nascer sem operador digitando
segredo. O fluxo alvo e: placa mostra QR/codigo, usuario logado no
`home.dadooh.ai` escolhe o ambiente, backend autoriza, placa recebe credencial
propria, grava config real e volta ao player.

Estado em 2026-07-09:

- backend C21 esta em producao em `api-00476-rix`, com rollback pronto em
  `api-00469-gus`;
- `POST /totem-auth/activations` no endpoint principal retorna `201`;
- `homeHabitat` branch `feat/pills-media-doc` esta publicado na EC2 e
  `https://home.dadooh.ai/totem/activate?...` responde com a pagina de
  autorizacao;
- `totem-core` C21.7 de homologacao foi aplicado na placa:
  `c21.7-qr-auth-credential-handoff-20260709T040439Z-208274b`;
- o E2E real `placa -> backend -> home -> placa -> config -> player` foi
  exercitado em laboratorio e registrado em
  `docs/evidence/c21-qr-auth/20260709T041826Z-board-e2e-real/`;
- a rodada passou com `policy_private_source=tmp-file`,
  `homologation_seed_mode=false`, `writer_rc=0`, `real_config_written=true`,
  config final presente em `0640` e player ativo.

Decisoes e riscos ainda vivos:

- na ativacao da `prod14` em 2026-07-14, o portal chegou a `Codigo recebido`
  e `Conta verificada`, mas permaneceu em `Carregando autorizacao` antes da
  escolha de ambiente; recarregar a pagina com `F5` retomou o fluxo. O caso e
  recuperavel e nao bloqueou o onboarding, mas permanece pendente de RCA no
  front para evitar que o usuario precise descobrir esse contorno;
- para o primeiro slice, ativacao por ambiente e aceitavel se a UI disser isso
  claramente; vinculacao forte por `station_id` fica como decisao/endurcimento
  seguinte ou deve ser feita agora se o produto exigir identidade por totem;
- a placa nao deve expor `api_key`, `device_secret` ou token humano em tela,
  log, evidencia publica ou repositorio;
- a troca de credencial e sensivel: se o primeiro `poll` autorizado falhar
  antes da persistencia local, precisa haver procedimento de gerar novo codigo
  e revogar o token antigo;
- rollback de `totem-core` nao revoga token nem restaura sozinho
  `/data/config/config.json`; rollback operacional precisa cobrir config e
  revogacao.

Proximo marco de maior valor:

1. manter C21.7 como pacote acumulado para a proxima imagem de referencia;
2. decidir se o primeiro produto aceita ativacao por ambiente ou se exige
   amarracao forte por estacao antes de escalar;
3. criar o procedimento operacional de revogacao/novo codigo quando um poll
   autorizado for consumido mas a placa nao persistir a credencial;
4. endurecer casos negativos de campo: expirado, negado, `already_used`,
   usuario sem permissao e sem internet;
5. levar C21.7 para o pacote/update consolidado de `totem-core`.

Non-claims:

- C21 prova o slice E2E real em laboratorio, mas nao prova todos os cenarios
  negativos de campo;
- o slice inicial de QR/auth nao altera `player-runtime`, MPV, kernel,
  media-system ou field-data; a RCA posterior de tela preta abriu uma subrodada
  separada de `player-runtime`;
- nao resolve por si so monitoramento, rollout por grupos ou revogacao
  automatica de tokens antigos.

## Subrodada C21 - RCA tela preta apos ativacao

Problema observado: apos QR/auth real e selecao de ambiente, a API entregou uma
playlist valida com 1 PNG. O player antigo tentou carregar o PNG direto no MPV
C18, falhou, bloqueou a unica midia e ficou em `waiting_for_media`.

RCA fechado:

- a placa tinha `playlist_size=1` e arquivo PNG local baixado;
- o MPV custom C18 nao decodificou PNG nesse caminho;
- converter a imagem para H.264 MP4 fez o mesmo MPV carregar a midia;
- a midia tambem e visualmente escura, mas isso e qualidade de conteudo, nao a
  causa tecnica do bloqueio.

Correcao aplicada no candidato `50919f5`:

- imagens estaticas sao preparadas como sidecar local `.h264.mp4` antes de
  entrar na playlist;
- `source_path` preserva o arquivo original;
- cache/saved playlist/offline path respeitam o sidecar e nao apagam a fonte;
- testes estaticos C18 passaram `31/31`;
- apply lab em placa passou, com marker verificado e rollback anterior mantido
  como `previous`; rollback nao foi executado nesta subrodada.

Pendente desta subrodada:

- publicar/consumir este novo alvo pelo fluxo remoto/publico de player-runtime,
  se ele virar alvo de escala;
- gerar nova autorizacao/policy hash-bound para este alvo ou sucessor; a
  autorizacao antiga de `player-runtime` continua amarrada ao `9bebaf1`;
- definir validacao de qualidade visual de midias muito escuras/pequenas no
  backend ou no produto;
- decidir se imagens devem ser convertidas no player, no backend, ou nos dois
  em camadas.

## Imagem para novas placas

Com o marco remoto de `totem-core` fechado, o marco remoto de `player-runtime`
fechado para `9bebaf1`, e a RCA C21 incorporada como candidato lab corrigido,
podemos escolher entre:

- imagem base enxuta + atualizacao OTA no provisionamento;
- imagem com o `player-runtime` corrigido como baseline inicial a validar e
  aprovar;
- rollout remoto por grupos para placas ja instaladas.

## Regra para os devs

- Mudou wizard/produto/core: `totem-core`.
- Mudou player/comportamento de playback: `player-runtime`.
- Mudou MPV/ffmpeg/kernel/hwdecode/imagem: nova imagem.
- Mudou midia/config/cache/playlist: fluxo de dados, nao release de software.
- Nunca publicar player direto pelo caminho legado `kiosky-player` para C18.

## PDCA imediato

1. Registrar este operating model curto.
2. Auditar se ele contradiz `UPDATE_CONTRACT.md`, doc 191 ou doc 192.
3. Corrigir textos historicos que confundam publicacao com consumo em placa.
4. Marco 1 (`totem-core` remoto) fechado.
5. Marco 2 (`player-runtime` remoto) fechado.
6. Marco 3 fechado: imagem `prod14` gerada, auditada offline e gravada.
7. Marco 4 fechado: `totem-core` C21.12 stable publicado, aplicado pelo timer,
   rollbackado, restaurado e persistido no reboot.
8. M5 fechado para o alvo exato C25B: timer, no-op, rollback, reaplicacao e
   playback estrito passaram sem autorizar futuros alvos por inferencia.
9. Auditoria independente final fechada com tres pareceres GO e zero blocker.
10. Rodada atual: `prod14` + C25B + C21.12 e a referencia; a prioridade volta a
    ativacao/estados visiveis, mantendo M4 minimo em paralelo.
11. C21.19 fecha em homologacao o Wi-Fi persistente transacional: pacote exato,
    bloqueio stable, apply/rollback/reapply, conexao real, restauracao em falha,
    fluxo visual sem escrita, reboot e playback passaram. A referencia publica
    continua `prod14` + C25B + C21.12. O summary `c075a55` fica marcado como
    entrada obrigatoria da proxima imagem, nao como parte do pacote C21.19.
12. A proxima frente e M9, Wi-Fi de produto. A ordem canonica de execucao esta
    em `docs/C20_UX_ACCUMULATION_PLAN.md`: verdade das opcoes/mensagens,
    simplificacao, redes abertas, estados, diagnostico, portal cativo,
    navegador restrito e fechamento por placa/OTA. Se o navegador exigir
    runtime novo, a dependencia entra na proxima imagem. Nao criar fila
    paralela.
13. Em 2026-07-16, M9 itens 1 e 2 fecharam na placa como C21.20: opcoes
    dinamicas, cancelamento limitado a sessao atual, rede protegida sem
    confirmacoes repetidas, retry direto e lista retrato sem item oculto. Os
    gates passaram `84/84`; stable bloqueou o prerelease; apply, rollback para
    C21.19, reaplicacao e captura visual real passaram. A placa terminou com
    player sem restart, policy/timer stable e estado persistente inalterado
    pela sessao visual. Rede aberta permanece o item 3. Evidencia:
    `docs/evidence/c20-totem-core-ota/20260716T160720Z-c21-20-wifi-product-flow-board-e2e/`.
14. M9 item 3 fechou tecnicamente na candidata C21.21: rede aberta sem senha,
    IPv4 obrigatorio, rollback transacional e regressao WPA coberta. Gates,
    bloqueio stable e roundtrip OTA passaram. A associacao em AP aberto fisico
    continua como non-claim explicito. Evidencia:
    `docs/evidence/c20-totem-core-ota/20260716T183703Z-c21-21-open-wifi-board-e2e/`.
15. M9 itens 4, 5 e 6 fecharam na candidata C21.22: estados visuais,
    transporte/acesso Dadooh verdadeiro e diagnostico/retry sanitizado. Gates
    `84/84`, replay, galeria, testes instalados, bloqueio stable,
    apply/rollback/reapply e estado final passaram. A placa terminou em C21.22
    com C21.21 como previous, player sem restart, rede preservada e
    policy/timer stable restaurados. Portal cativo e o proximo recorte.
    Evidencia:
    `docs/evidence/c20-totem-core-ota/20260716T202728Z-c21-22-wifi-state-recovery-board-e2e/`.
16. M9 item 7 fechou tecnicamente na candidata C21.23: deteccao positiva de
    portal, ambiguidade fail-closed, bloqueio de ambiente/revisao/gravacao e
    caminhos de retry/troca/saida. Gates `84/84`, auditorias, bloqueio stable,
    apply/rollback/reapply e testes instalados passaram. A placa terminou em
    C21.23 com C21.22 como previous, player sem restart, rede preservada e
    policy/timer stable restaurados. Portal fisico/emulado e navegador M9.8
    continuam pendentes, sem contaminar este claim. Evidencia:
    `docs/evidence/c20-totem-core-ota/20260716T214911Z-c21-23-captive-portal-board-e2e/`.
