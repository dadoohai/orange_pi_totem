# C18 OTA - fonte da verdade operacional

Estado em 2026-07-05. Este documento e o radar curto para decidir os proximos
passos de OTA. O contrato detalhado continua em `docs/UPDATE_CONTRACT.md`; este
arquivo existe para nao perder as decisoes praticas enquanto fechamos a etapa
operacional.

Direcao macro da fase atual: `docs/C18_MACRO_STEERING.md`.

Spec de execucao da fase de producao com auto-pull:
`docs/C18_PRODUCTION_AUTOPULL_SPEC.md`.

Runbook do proximo marco fisico:
`docs/c18-totem-core-production-timer-runbook.md`.

## Definicao pratica

Para produto, "OTA em producao" significa: uma placa consegue receber uma
atualizacao remota, validar o pacote, aplicar, continuar funcional e voltar por
rollback se necessario.

Hoje a C18 tem duas coisas diferentes:

- `totem-core`: caminho OTA manual/operator-triggered ja e a frente mais pronta.
- `player-runtime`: pacote aprovado, publicado no GitHub e consumido pela placa
  em janela assistida. Public thaw, auto-pull e rollout amplo continuam
  separados.

Portanto, os dois caminhos praticos de software C18 ja possuem prova remota de
laboratorio: `totem-core` como OTA manual comum e `player-runtime` como apply
assistido por operador, com rollback e health real. Isso ainda nao significa
auto-pull amplo nem producao automatica.

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
| `totem-core` | wizard, splash, status, writer, helpers, validadores, settings e UX operacional da placa | OTA C18 manual/remoto, com dry-run, apply e rollback |
| `player-runtime` | `kiosk.py`, comportamento do player, timing, sync, duracao, playlist, flags de MPV no player | release C18-aware `player-runtime`; consumo remoto assistido provado na placa; public thaw/auto-pull continuam separados |
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
4. Auto-pull de `totem-core` e o alvo de producao pragmatica; auto-pull geral
   de `player-runtime`/frota continua separado ate ter rotina publica propria.
5. Regravar imagem em laboratorio e permitido como reset/prova, mas nao conta
   como OTA de producao.
6. Toda atualizacao real precisa ter dry-run, apply, validacao e rollback.

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
- Marco 5 `totem-core` auto-pull em imagem de producao: fechado em 2026-07-05.
  A placa foi gravada com a imagem `c18-hwdecode-prod-1`, bootou com policy
  `stable`, timer habilitado, aplicou automaticamente a release stable
  `totem-core-c18.ota-core-prod-20260705T184013Z-ccaf5a1`, manteve
  `kiosky-player.service` ativo com `NRestarts=0`, preservou o freeze publico
  de `player-runtime` com `rc=44`, e rollbackou para
  `c17.6-environment-input-20260514T211247Z`. Evidencia em
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

- Decidir se a placa de bancada deve permanecer rollbackada para a versao
  embutida da imagem ou deixar o timer reaplicar a release stable novamente
  como estado final operacional.
- Decidir se novas placas saem com `player-runtime 9bebaf1` consolidado na
  imagem ou se recebem `player-runtime` via OTA assistido no provisionamento.
- Transformar o caminho assistido em rotina operacional de release, sem
  reabrir o caminho legado `kiosky-player`.
- Decidir formalmente a politica de public thaw/auto-pull/rollout por grupos
  para `player-runtime`, se esse update automatico for requerido agora.
- Separar futuras evolucoes de produto: `totem-core` para wizard/core e
  `player-runtime` para comportamento do player.

## Direcao de producao por decisao de negocio

Decisao operacional em 2026-07-05: o cliente quer escala rapidamente e aceita o
risco de negocio. A direcao passa a ser producao em escala com auto-pull como
padrao, preservando a governanca tecnica minima para nao quebrar placa e manter
rollback.

Leitura pratica:

- novas placas devem sair preferencialmente com imagem de producao consolidada,
  ja contendo o `player-runtime 9bebaf1` aprovado por excecao de negocio;
- `totem-core` deve ser o primeiro auto-pull padrao, porque ja tem apply remoto,
  health, rollback e escopo estreito provados na placa;
- `player-runtime` tambem deve entrar no objetivo de auto-pull, mas nao por
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
5. ponte publica segura para auto-pull de `player-runtime`, se o cliente exigir
   update automatico do player alem do core.

## Imagem para novas placas

Com os marcos `totem-core` e `player-runtime` remotos fechados em laboratorio,
podemos escolher entre:

- imagem base enxuta + atualizacao OTA no provisionamento;
- imagem ja consolidada com `player-runtime 9bebaf1`;
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
8. Marco 5: imagem producao bootada e timer real de `totem-core` provado com
   rollback.
9. Proxima rodada: definir estado final da placa de bancada, fechar runbook de
   fabrica/devs e decidir se V3 `player-runtime` publico entra agora ou fica
   como roadmap controlado.
