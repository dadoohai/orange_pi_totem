# C19 Visual QA Flow

Estado: 2026-07-07.

Objetivo: ter um fluxo simples para validar visualmente wizard/settings na placa
real, com captura de tela e retorno seguro para midia.

## Premissas

- SVG gerado pelo wizard nao conta como screenshot real.
- Screenshot real do wizard e captura feita durante a sessao aberta na placa.
- PNG bruto vindo do framebuffer pode ter alfa zerado; para revisao humana no
  Windows, gerar tambem `*-visible.jpg`.
- Para player/midia em DRM/GPU, framebuffer pode nao provar exatamente o que a
  TV mostra. Se a duvida for sobre a midia final na TV, usar HDMI capture ou
  camera.

## Pre-requisitos

- Placa acessivel por SSH, preferencialmente por Ethernet.
- HDMI conectado.
- Teclado USB conectado quando o teste for reproduzir fluxo de usuario.
- Confirmar que `/dev/input/event*` existe e que o trigger ve dispositivos.
- Nao aplicar Wi-Fi/config real salvo se esse for o objetivo explicito do teste.

## Fluxo De Usuario Real

1. Usuario segura `F10` por cerca de 5s.
2. `totem-settings-trigger.service` grava request em `/run/dadooh-settings/request.json`.
3. `totem-open-settings.service` abre a sessao no `tty2`.
4. `kiosky-player.service` para e a midia deixa de aparecer.
5. Wizard roda em `/tmp/dadooh-c10-6-2-visual-wizard`.
6. Capturar framebuffer enquanto a tela esta aberta.
7. Usuario sai com `Esc`.
8. Cleanup remove lock/request e o player volta.

Marcadores esperados:

- `request.json` com `trigger_type=keyboard_f10_hold`;
- `/run/totem/settings-session.lock` presente durante wizard;
- `kiosky-player.service=inactive` durante wizard;
- `kiosky-player.service=active` e `PLAYER_STATUS=playing` depois do `Esc`;
- `real_config_written=false`, `wifi_changed=false` quando o teste for apenas
  navegacao/captura.

## Operacao Remota Controlada

Quando a sessao ja esta aberta no `tty2`, e possivel operar a tela remotamente
injetando teclas no TTY. Isso foi provado movendo a selecao de `Paisagem` para
`Retrato para direita` e voltando para `Paisagem`.

Uso recomendado:

- enviar apenas teclas pequenas e previsiveis;
- capturar depois de cada passo;
- nao confirmar escrita real sem objetivo explicito;
- sempre restaurar para midia ao final.

## Captura

Captura tecnica na placa:

```sh
ffmpeg -hide_banner -loglevel error -f fbdev -i /dev/fb0 -frames:v 1 -update 1 /tmp/capture.png
```

Conversao para imagem visivel no Windows:

```sh
convert /tmp/capture.png -channel RGB -separate -combine /tmp/capture-visible.jpg
```

Guardar os dois quando possivel:

- `capture.png`: evidencia tecnica bruta;
- `capture-visible.jpg`: revisao humana.

## Evidencia Lab Atual

Rodada real em 2026-07-07:

- teclado USB detectado como `SIGMACHIP USB Keyboard`;
- F10 abriu wizard real;
- request capturado com `trigger_type=keyboard_f10_hold`;
- screenshot corrigido mostrou `Orientacao da tela`;
- injecao remota de seta alterou a selecao na tela;
- `Esc` fechou wizard e a midia voltou.

Artefatos locais de bancada:

- `/home/builder/c18-visual-smoke/f10-real-20260707T192609Z/fb-current-visible.jpg`;
- `/home/builder/c18-visual-smoke/remote-key-test-20260707T193053Z/fb-after-down-visible.jpg`;
- `/home/builder/c18-visual-smoke/real-wifi-wizard-20260707T190917Z/fb-real-wifi-list-visible-rgb.jpg`.

## Achados A Carregar

- Display atual esta em `1024x768`; TV widescreen pode esticar a imagem.
- Esse modo vem de fallback/EDID limitado e pertence a frente de display.
- `Esc` restaurou player e limpou lock/request, mas deixou
  `totem-open-settings.service` como `failed` por `Result=signal` e
  `ExecMainStatus=15`. Foi limpo com `systemctl reset-failed`.
- Ajuste recomendado: cancelamento por `Esc` deve encerrar a unidade de forma
  limpa, sem deixar estado `failed`, mantendo o mesmo comportamento funcional.

## C19.1 Investigacao De Navegacao

Rodada: `20260707T194848Z-wizard-navigation`.

Evidencia:
`docs/evidence/c19-visual-qa/20260707T194848Z-wizard-navigation/`.

O wizard foi aberto via `totem-open-settings.service`, navegado por teclas no
`tty2`, capturado em cada etapa e encerrado por `Esc`. Resultado final:
`kiosky-player.service=active`, MPV vivo, `PLAYER_STATUS=playing`,
lock/request ausentes, `real_config_written=false` e `wifi_changed=false`.

Problemas priorizados:

1. P1: lista real de Wi-Fi invade o rodape em `1024x768`.
2. P1: `Esc` volta a midia, mas deixa `totem-open-settings.service` como
   `failed` por `Result=signal` / `ExecMainStatus=15`.
3. P2: indicador de sinal aparece como `????`.
4. P2: display em `1024x768` reduz espaco util e pertence a frente de display.

Causas ja localizadas:

- overlap: quinto card da lista chega a `y=728`, enquanto o rodape inicia em
  `y=638`;
- `????`: `signal_bars()` usa blocos Unicode que a fonte/renderizacao atual nao
  suporta.

## C19.2 Plano De Correcao

Objetivo: corrigir apenas o que bloqueia uso real basico do wizard, sem entrar
em redesign visual nem resolver display/EDID nesta rodada.

Escopo P1:

1. Lista de Wi-Fi caber em `1024x768`.
   - Correcao minima recomendada: page size responsivo.
   - Landscape: 4 redes por pagina.
   - Portrait: manter 5 redes por pagina.
   - Nao alterar `option_cards()` globalmente agora, para evitar regressao em
     outras telas.

2. `Esc` encerrar settings de forma limpa.
   - Cancelamento do wizard (`WIZARD_RC=130` ou `setup-cancelled.json`) deve
     cair no caminho normal de restore quando `EXPECTED_RESULT=any|cancelled`.
   - Nao exigir `config.candidate.json` apos cancelamento.
   - `kill_visual_if_running()` nao deve matar o proprio session runner.
   - Nao mascarar com `SuccessExitStatus=SIGTERM`; isso esconderia falha real.

Fora de escopo nesta rodada:

- trocar `????` do sinal;
- corrigir modo HDMI `1024x768`;
- redesign visual amplo;
- escrita real de Wi-Fi/config.

Validacao obrigatoria apos correcao:

- `python3 scripts/board/totem_setup_visual_wizard.py --self-test`;
- galeria/smoke local sem writer nem rede real;
- placa real via `F10`;
- capturas `*-visible.jpg` da lista Wi-Fi pagina 1, page down e page up;
- nenhum card invadindo rodape em `1024x768`;
- sair com `Esc`;
- `totem-open-settings.service` sem `failed`;
- `kiosky-player.service=active`, MPV vivo, `PLAYER_STATUS=playing`;
- lock/request ausentes;
- `real_config_written=false` e `wifi_changed=false`;
- repetir `F10 -> Esc` duas vezes para provar reentrada limpa.

## C19.2 Resultado

Rodada: `20260707T201204Z-p1-fix-validation` e
`20260707T201447Z-esc-clean-cycles`.

Resultado:

- P1 Wi-Fi/rodape corrigido: em paisagem, a lista de Wi-Fi mostra 4 redes por
  pagina; em retrato, continua mostrando 5.
- PageDown/PageUp acompanham o tamanho real da pagina.
- P1 lifecycle corrigido: `Esc` na tela inicial encerra o settings sem deixar
  `totem-open-settings.service` como `failed`.
- Dois ciclos de abrir settings e sair com `Esc` terminaram com
  `Result=success`, `ExecMainStatus=0`, `kiosky-player.service=active`,
  MPV vivo, lock/request ausentes.

Evidencia:

- `docs/evidence/c19-visual-qa/20260707T201204Z-p1-fix-validation/`;
- `docs/evidence/c19-visual-qa/20260707T201447Z-esc-clean-cycles/`.

Observacao operacional:

- Na imagem atual, `/opt/totem/bin` contem wrappers C17.5. O codigo ativo do
  `totem-core` vem de `/data/core/totem/current/bin` quando existe. Validacoes
  em placa devem alterar/copiar scripts no alvo ativo, preservando os wrappers.

Observacao de UX:

- `Esc` dentro da lista de Wi-Fi volta para a etapa de conexao; isso e
  comportamento de navegacao local, nao encerramento global. Para cancelar o
  wizard a partir da lista, voltar ao ponto anterior ou usar cancelamento
  global (`q`).

Pendencias fora desta rodada:

- display segue em `1024x768` fallback;
- QA visual de escrita real de Wi-Fi/config continua fora de escopo.

## C19.3 Resultado

Rodada: `20260707T203245Z-signal-ascii-preview-burst`.

Objetivo: remover o `????` do indicador de sinal Wi-Fi sem mexer em scan,
senha, NetworkManager, escrita real ou layout amplo.

Correcao:

- `signal_bars()` deixou de usar blocos Unicode (`████`);
- indicador passou a usar ASCII: `[####]`, `[###.]`, `[##..]`, `[#...]`;
- percentual, classificacao textual e seguranca continuam iguais.

Resultado:

- self-test local passou;
- preview sintetico gerou SVG com `[####]` e sem blocos Unicode;
- placa real exibiu lista Wi-Fi pelo renderer local com indicador ASCII e sem
  `????`;
- player voltou ativo ao final do teste.

Evidencia decisiva:

- `docs/evidence/c19-visual-qa/20260707T203245Z-signal-ascii-preview-burst/`.

Evidencias auxiliares nao decisivas:

- `20260707T202930Z-signal-ascii-validation`: navegou pelo wizard real, mas o
  screenshot capturado nao foi a tela de Wi-Fi;
- `20260707T203145Z-signal-ascii-preview`: capturou o preview, mas caiu na tela
  de senha Wi-Fi, nao na lista.

Pendencias fora desta rodada:

- display segue em `1024x768` fallback;
- QA visual de escrita real de Wi-Fi/config continua fora de escopo.

## C19.4 Pacote Totem-Core

Rodada: `20260707T211121Z-apply-rollback`.

Pacote:
`c19.visual-settings-20260707T205630Z-5df93c1`.

Resultado:

- pacote `totem-core` de homologacao gerado sem dirty tree;
- gate C18 especifico do manifest/payload passou;
- apply local na placa passou;
- `current` apos apply virou o pacote C19;
- self-test do updater e self-test do wizard passaram;
- playback deep-health curto passou apos apply;
- rollback voltou para `c18.ota-core-prod-20260705T184013Z-ccaf5a1`;
- playback deep-health curto passou apos rollback;
- cleanup restaurou a topologia inicial: policy `stable`,
  `allow_prerelease=false`, timer ativo/habilitado, `current` C18 e
  `previous` C17.6.

Evidencia:

- `releases/core-updates/c19.visual-settings-20260707T205630Z-5df93c1/`;
- `docs/evidence/c19-totem-core-ota/20260707T211121Z-apply-rollback/`.

Nao-claims:

- C19 nao foi publicado;
- C19 nao foi promovido para `stable`;
- Wi-Fi real/config real e display/EDID seguem fora do escopo desta rodada.

## Regra Curta

Para QA visual confiavel: abrir wizard pelo fluxo real, capturar durante a
sessao, validar retorno para midia e salvar `*-visible.jpg`. SVG ajuda debug,
mas nao substitui screenshot real.
