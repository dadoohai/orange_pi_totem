# C18 OTA - fonte da verdade operacional

Estado em 2026-07-13. Este documento e o radar curto para decidir os proximos
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

- `totem-core`: auto-pull de producao provado em imagem C18 gravada do zero;
- `player-runtime`: auto-pull de producao fechado somente para o alvo exato C23
  `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`. A prod8 foi gravada do
  zero e provou timer remoto, no-op, rollback, restauracao e 600 segundos
  continuos limpos. Qualquer alvo futuro continua bloqueado ate nova
  autorizacao presa por hashes.

O M5 nao deve ser reaberto: C23 esta provado. A arquitetura C24 para reconciliar
a fonte e autorizar alvos futuros sem regravacao esta aprovada, mas foi movida
para roadmap. A prioridade atual volta a ser produto visivel por `totem-core`,
fechamento E2E do conjunto acumulado e nova imagem de referencia. M4 continua
em paralelo; grupos, dashboard e telemetria seguem no roadmap.

## Repositorio de entrega

O repo de entrega C18 e `dadoohai/orange_pi_totem`.

Ele contem imagem/SO, wizard, scripts de boot, OTA, gates, documentacao,
empacotamento e o snapshot governado do player em
`player-runtime/kiosky-player/kiosk.py`.

O repo `kiosky-player`, branch `appliance-v0.1`, sera a fonte editavel do
comportamento depois da convergencia C24. Ele nao publica direto para placas.
Toda entrega para cliente continua passando por um snapshot de commit exato na
frente `player-runtime` do fluxo C18. Ate a convergencia fechar, o snapshot C23
continua sendo a verdade funcional em producao.

Nota de nome: em runtime o servico ainda pode se chamar `kiosky-player.service`.
Isso nao torna `kiosky-player` uma rota de release C18. O launcher C18 deve
adotar `/data/player-runtime/current` quando houver marker valido e cair para a
imagem/fallback quando nao houver.

## Frentes de update

| Frente | O que entra | Caminho permitido agora |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, helpers, validadores, settings e UX operacional da placa | auto-pull de producao fechado; dry-run, apply, timer e rollback provados |
| `player-runtime` | `kiosk.py`, comportamento do player, timing, sync, duracao, playlist, flags de MPV no player | auto-pull production fechado para C23 exato; futuros alvos exigem nova autorizacao hash-bound |
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
4. Auto-pull de `totem-core` e de `player-runtime` C23 estao provados; isso nao
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

- C19/C20 e o QR C21 ja foram consolidados e publicados no `totem-core`
  C21.11. Nao aguardam outro pacote para funcionar; aguardam apenas entrar como
  baseline da proxima imagem de referencia.
- Fechar na versao atual a jornada real completa: Wi-Fi, QR, ambiente, escrita,
  conclusao e retorno ao player, com captura visual quando o HDMI estiver
  disponivel.
- Estados visiveis C25A (`totem-core`) e C25B (`player-runtime`) estao
  validados e reversiveis na placa de homologacao. O alvo C25B final e
  `c18.player-runtime-homolog-20260713-c25b-still-fix-54308e4`, com playback,
  `content_unavailable`, recuperacao, rollback e reaplicacao comprovados. Ele
  permanece fora de `stable` e do auto-pull publico; o proximo marco e
  incorpora-lo, junto com o launcher/updater correspondentes, na nova imagem
  de referencia. Contrato e evidencias estao em
  `docs/product/199_C25_VISIBLE_PRODUCT_STATES.md` e
  `docs/evidence/c25-visible-states/20260713T082118Z-c25b-still-final-board/`.
- Continuar novas melhorias de wizard/status por `totem-core`, uma vertical de
  uso por rodada, preservando o QA C19/C20.
- Retomar a matriz de compatibilidade de display quando as telas alvo estiverem
  disponiveis; ate la, manter apenas diagnostico read-only.
- Depois desse conjunto, gerar a nova imagem de referencia com C21.11 e as
  melhorias acumuladas como baseline.
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

## O que falta para producao automatizada/ampla

- construir e auditar `prod-7` com updater/autorizacao C22, sem estado lab e
  com o wizard usando politica de producao: **fechado off-board** no SHA256
  `c82c69341b4e1306899ae149d25a0c8953b42ee081291928adee8614d5b5b0b7`;
- sincronizar branch/tag remotas e publicar os tres assets C22 sem mover
  `latest`: **fechado** em 2026-07-10, com re-download e hashes conferidos;
- gravar a imagem na placa e preparar C21 como estado anterior controlado;
- provar o timer adotando C22, no-op sem mutacao, rollback autorizado e
  restauracao C22 com playback real;
- manter futuras evolucoes separadas: `totem-core` para wizard/core e
  `player-runtime` para comportamento do player. Grupos, dashboard e kill
  switch continuam roadmap M6 e nao bloqueiam a primeira escala aceita.

Risco aceito para esta primeira escala: SSH root por senha compartilhada
permanece para suporte; credencial por device e M6. A excecao nao permite senha
plaintext, Wi-Fi/identidade de lab ou host keys reutilizadas na imagem.

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

- novas placas devem sair com a nova imagem de producao contendo o C22 como
  fallback e autorizacao exact-target C22; a prova de atualizacao usa C21 como
  estado anterior apenas na bancada;
- `totem-core` deve ser o primeiro auto-pull padrao, porque ja tem apply remoto,
  health, rollback e escopo estreito provados na placa;
- `player-runtime` entra agora no objetivo de auto-pull, mas nao por
  reaproveitamento cego do harness de laboratorio: precisa de caminho publico
  pinado/hash-bound, health real, rollback e criterio claro de thaw;
- como ainda nao ha infraestrutura real de grupos, dashboard ou monitoramento
  de frota, a primeira producao deve assumir rollout simples/global e registrar
  isso como risco aceito, com inventario manual e procedimento de emergencia;
- staged rollout, allowlist por grupos, assinatura consumida no device,
  kill-switch e telemetria ficam no roadmap de robustez, nao como bloqueio para
  a primeira entrega se a decisao de negocio for avancar.

Consequencia: o proximo trabalho nao e mais provar homologacao assistida. E
materializar uma linha de producao pragmatica:

1. imagem de producao C18, sem marcador `not_for_production`;
2. policy de producao e timer habilitado para auto-pull de `totem-core`;
3. teste real do timer aplicando update remoto e rollbackando;
4. especificacao curta para devs e fabrica;
5. ponte publica segura para auto-pull de `player-runtime`, agora exigida pelo
   cliente e assumida como proximo marco.

## Historico V3/M5 - C22/prod7

Esta secao preserva a rodada que abriu a mecanica production exact-target em
C22/prod7. O estado vigente e seu fechamento C23/prod8 estao no topo deste
documento e na evidencia de 2026-07-11; este historico nao e a rodada atual.

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
6. Marco 3: imagem producao C18 gerada offline e validada por manifesto.
7. Marco 4: `totem-core stable` publicado e validado por apply/rollback lab.
8. Marco anterior: imagem producao bootada e timer real de `totem-core` provado
   com rollback.
9. M5 fechado para o alvo exato C23; nao reabrir sua prova por causa de um
   pacote futuro.
10. C25A e o alvo exato C25B validados e reversiveis em homologacao.
11. Rodada atual: consolidar o conjunto C25 e os hooks image-bound na proxima
    imagem de referencia, mantendo M4 minimo em paralelo. C25B nao herda
    `stable` ou auto-pull de C23 por inferencia.
