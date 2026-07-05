# C18 OTA - fonte da verdade operacional

Estado em 2026-07-04. Este documento e o radar curto para decidir os proximos
passos de OTA. O contrato detalhado continua em `docs/UPDATE_CONTRACT.md`; este
arquivo existe para nao perder as decisoes praticas enquanto fechamos a etapa
operacional.

## Definicao pratica

Para produto, "OTA em producao" significa: uma placa consegue receber uma
atualizacao remota, validar o pacote, aplicar, continuar funcional e voltar por
rollback se necessario.

Hoje a C18 tem duas coisas diferentes:

- `totem-core`: caminho OTA manual/operator-triggered ja e a frente mais pronta.
- `player-runtime`: pacote aprovado e publicado no GitHub, mas consumo/thaw em
  placa ainda nao foi executado como rotina operacional.

Portanto, a release de `player-runtime` esta liberada como artefato; o OTA
remoto operacional dessa frente ainda precisa ser fechado na placa.

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
| `player-runtime` | `kiosk.py`, comportamento do player, timing, sync, duracao, playlist, flags de MPV no player | release C18-aware `player-runtime`; hoje publicada, ainda falta consumo/thaw operacional em placa |
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
4. Auto-pull geral continua desligado ate a rotina remota ser provada na placa.
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

## O que falta para chamar OTA remoto de operacional

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

Checklist minimo:

- partir de imagem base conhecida, regravada se necessario;
- confirmar estado inicial da placa;
- fazer a placa localizar e consumir a GitHub Release publicada do
  `player-runtime`, nao um tarball local copiado manualmente;
- validar manifest, hashes e assets;
- aplicar/thaw pelo caminho C18, sem usar publisher ou scripts legados de
  `kiosky-player`;
- validar playback real;
- testar rollback;
- testar pelo menos um negativo: pacote errado, hash errado ou canal errado;
- registrar evidencia curta.

Depois desse marco, mudancas futuras de player devem seguir como
`player-runtime`.

Claim permitido apos esse marco: "a placa consumiu remotamente a release
publicada, adotou o alvo e validou playback sob janela controlada". Nao dizer:
"auto-pull ligado", "rollout automatico", "media-system validado", "novo soak
limpo" ou "manifest stable de player-runtime".

## Imagem para novas placas

Enquanto o consumo remoto de `player-runtime` nao estiver fechado, novas placas
devem sair com imagem base C18 conhecida e com o estado aprovado aplicado no
provisionamento.

Quando os marcos acima passarem, podemos escolher entre:

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
4. Fechar marco 1 (`totem-core` remoto) na placa lab.
5. Fechar marco 2 (`player-runtime` remoto) na placa lab.
6. So depois discutir auto-pull/rollout amplo.
