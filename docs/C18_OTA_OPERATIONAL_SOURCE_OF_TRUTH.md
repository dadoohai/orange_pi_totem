# C18 OTA - fonte da verdade operacional

Estado em 2026-07-07. Este documento e o radar curto para decidir os proximos
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

Runbook do marco fisico encerrado de `totem-core`:
`docs/c18-totem-core-production-timer-runbook.md`.

## Definicao pratica

Para produto, "OTA em producao" significa: uma placa consegue receber uma
atualizacao remota, validar o pacote, aplicar, continuar funcional e voltar por
rollback se necessario.

Hoje a C18 tem duas coisas diferentes:

- `totem-core`: auto-pull de producao fechado em imagem C18 gravada do zero.
- `player-runtime`: pacote aprovado, publicado no GitHub e consumido pela placa
  em janela assistida. Public thaw/ativacao estao autorizados por evidencia, mas
  o caminho publico de auto-pull ainda precisa ser materializado no updater,
  timer/policy e prova de placa.

Portanto, o proximo marco ativo e V3/M5: transformar o apply assistido de
`player-runtime` em auto-pull publico por alvo exato, preservando rollback,
health real e bloqueio para qualquer alvo nao autorizado.

## Repositorio de entrega

O repo de entrega C18 e `dadoohai/orange_pi_totem`.

Ele contem imagem/SO, wizard, scripts de boot, OTA, gates, documentacao,
empacotamento e o snapshot governado do player em
`player-runtime/kiosky-player/kiosk.py`.

O repo antigo `kiosky-player` pode continuar existindo como origem de
desenvolvimento do player, mas nao deve publicar direto para placas C18. Toda
entrega de player para cliente deve passar pela frente `player-runtime` dentro
do fluxo C18.

Nota de nome: em runtime o servico ainda pode se chamar `kiosky-player.service`.
Isso nao torna `kiosky-player` uma rota de release C18. O launcher C18 deve
adotar `/data/player-runtime/current` quando houver marker valido e cair para a
imagem/fallback quando nao houver.

## Frentes de update

| Frente | O que entra | Caminho permitido agora |
| --- | --- | --- |
| `totem-core` | wizard, splash, status, writer, helpers, validadores, settings e UX operacional da placa | auto-pull de producao fechado; dry-run, apply, timer e rollback provados |
| `player-runtime` | `kiosk.py`, comportamento do player, timing, sync, duracao, playlist, flags de MPV no player | release C18-aware `player-runtime`; consumo remoto assistido provado; proximo marco e auto-pull publico por alvo exato |
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
4. Auto-pull de `totem-core` ja esta fechado; auto-pull de `player-runtime`
   agora e o marco ativo, mas somente por rotina publica propria e alvo exato.
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

- C19 wizard/settings visual: validada para acumulo em `totem-core`; pendente
  entrar no pacote/update consolidado e na proxima imagem de referencia.
- C20 V0 orientation preview: validada para acumulo em `totem-core`; corrige a
  sobreposicao do preview de orientacao em paisagem e preserva retrato sem
  sobreposicao no preview auto-exit. Evidencia em
  `docs/evidence/c20-visual-qa/20260707T192000-c20-v0-final-preview-board/`.
- C20 UX geral: plano aberto para novas rodadas acumulaveis de `totem-core`;
  proximos focos seguem hierarquia/densidade do wizard e navegacao previsivel.

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

- Decidir se novas placas saem com `player-runtime 9bebaf1` como baseline
  inicial aprovado da imagem ou se recebem `player-runtime` via OTA assistido no
  provisionamento.
- Transformar o caminho assistido em rotina operacional de release, sem
  reabrir o caminho legado `kiosky-player`.
- Materializar a politica de public thaw/auto-pull de `player-runtime` no
  updater, timer/policy e prova de placa. Rollout por grupos continua roadmap.
- Separar futuras evolucoes de produto: `totem-core` para wizard/core e
  `player-runtime` para comportamento do player.

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

- novas placas devem sair preferencialmente com imagem de producao contendo o
  `player-runtime 9bebaf1` como baseline inicial aprovado por excecao de
  negocio;
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

## Rodada atual - V3/M5 `player-runtime` auto-pull

Decisao: avancar com auto-pull de `player-runtime` em producao pragmatica,
assumindo risco de negocio e preservando as barreiras tecnicas que evitam
regressao silenciosa.

Claim permitido ao final da rodada: uma placa C18 em imagem de producao aplicou
automaticamente o `player-runtime` exato `9bebaf1`, validou hashes/manifest,
gerou marker valido no device, passou health real, manteve rollback e recusou
alvos nao autorizados.

Nao-claims:

- nao e `latest` amplo para qualquer `player-runtime` futuro;
- nao publica direto pelo repo/caminho legado `kiosky-player`;
- nao altera MPV, ffmpeg, kernel, imagem, midia, config ou cache;
- nao entrega dashboard, grupos/canary, telemetria ou kill switch completo;
- nao reclassifica evidencia antiga como prova de novo alvo.

Passos minimos:

1. autorizacao production hash-bound para o alvo `9bebaf1`;
2. caminho publico no updater sem env lab, permitido somente para alvo
   autorizado;
3. health real, marker, quarentena, state e rollback reaproveitando o
   verify-then-promote existente;
4. timer/service explicito para `player-runtime`, sem concorrer com
   `totem-core`;
5. evidencia de placa: dry-run, apply automatico, deep-health, rollback, no-op e
   negativos de alvo errado/hash errado/canal errado/sem autorizacao;
6. auditoria final focada em regressao: `totem-core` continua funcionando,
   `kiosky-player` legado continua fora e `media-system` continua fora do OTA.

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

Evidencias principais:

- `docs/evidence/c20-visual-qa/20260707T192000-c20-v0-final-preview-board/`;
- `docs/evidence/c20-visual-qa/20260707T224916Z-c20-v1-layout-preview-board/`;
- `docs/evidence/c20-visual-qa/20260707T225600Z-c20-v1-wifi-landscape-board-clean/`;
- `docs/evidence/c20-visual-qa/20260707T225800Z-c20-v1-review-landscape-board/`.

Non-claims:

- C20 ainda nao foi empacotado nem publicado por OTA;
- nao mexe em player-runtime, Wi-Fi real, display/EDID, updater, imagem ou
  media-system;
- captura de preview nao substitui fluxo completo por teclado quando a rodada
  depender de interacao real.

Proximo marco recomendado: continuar V2/V3 ou fechar um pacote consolidado de
`totem-core` quando o conjunto de UX estiver suficiente para uma imagem de
referencia.

## Imagem para novas placas

Com os marcos `totem-core` e `player-runtime` remotos fechados em laboratorio,
podemos escolher entre:

- imagem base enxuta + atualizacao OTA no provisionamento;
- imagem com `player-runtime 9bebaf1` como baseline inicial aprovado;
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
9. Rodada atual: executar V3/M5 `player-runtime` auto-pull publico por alvo
   exato, mantendo M4 minimo em paralelo.
