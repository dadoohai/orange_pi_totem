# C18 Display Profile Steering

Estado inicial: 2026-07-06.

Este documento registra a frente de tela/display sem mudar o centro macro da
C18. O objetivo e resolver compatibilidade de display com velocidade, mas sem
transformar um ajuste de tela em regressao de player, boot ou OTA.

## Objetivo

Criar uma trilha controlada para diagnosticar e, quando necessario, padronizar
resolucao/taxa de HDMI em placas C18.

O resultado esperado nao e "mexer no player ate aparecer imagem". O resultado
esperado e saber, por placa/display, se a tela esta:

- conectada;
- negociando EDID/modo corretamente;
- rodando em modo aceitavel;
- precisando de perfil de tela;
- ou exigindo imagem com modo forcado.

## Estado Atual

Hoje a C18 nao tem gerenciador completo de resolucao.

O que existe:

- o launcher detecta HDMI conectado/desconectado via `/sys/class/drm/*/status`;
- se nao ha tela, o player nao sobe e o estado publico fica `display_missing`;
- o player usa MPV direto em DRM/KMS, fullscreen;
- a resolucao/taxa fica a cargo da negociacao HDMI/DRM;
- rotacao existe como configuracao do player;
- ha coletor read-only `scripts/board/c18_display_status_collect.py` no repo.

O que nao existe:

- perfil oficial de tela;
- escolha governada de `720p60`, `1080p60`, `safe`, etc.;
- forca de modo por cliente/modelo;
- instalacao universal do coletor de display em todas as imagens ja gravadas;
- garantia de que EDID ruim sera corrigido por OTA comum.

## Evidencia Viva Inicial

Coleta read-only em `2026-07-06T02:11:35-03:00` na placa lab:

- HDMI `connected`;
- conector `enabled`;
- DPMS `On`;
- servico `kiosky-player.service` ativo;
- MPV vivo via `/opt/totem/hwdecode/bin/mpv`;
- MPV usando `--vo=gpu`, `--gpu-context=drm`, `--hwdec=v4l2request-copy`;
- player publico em `playing`;
- EDID com `0` bytes;
- modos disponiveis: `1024x768`, `800x600`, `848x480`, `640x480`;
- modo corrente observado por auditoria: `1024x768@60`;
- `/proc/cmdline` sem `video=...` forcando HDMI.

Leitura: a placa esta viva e exibindo, mas caiu em modo seguro baixo porque o
display nao entregou EDID util. Isso e problema de compatibilidade/negociacao de
display, nao prova de regressao do player.

## Evidencia D1 Versionada

Rodada D1 registrada em:

`docs/evidence/c18-update-validation/20260706T052600Z-display-profile-d1-73bb204/`

Resultado:

- gate read-only antigo: `board_readonly_diagnostics_evidence_accepted`;
- gate de baseline D1: `display_profile_baseline_accepted`;
- classificacao D1: `edid_missing_low_mode_fallback`;
- HDMI conectado e enabled;
- EDID com `0` bytes;
- modos disponiveis: `1024x768`, `800x600`, `848x480`, `640x480`;
- sem override `video=...` na cmdline sanitizada.

Isso fecha o primeiro baseline da tela atual. A decisao segue a mesma: nao
alterar `player-runtime` nem forcar resolucao por OTA comum para resolver esse
caso.

## Fronteiras

### `totem-core`

Pode carregar melhoria de diagnostico, status, tela de suporte e UI de escolha
de perfil, desde que nao tente forcar HDMI diretamente sem base preparada.

### `player-runtime`

Pode alterar `kiosk.py`, flags do MPV, rotacao e comportamento de exibicao.
Qualquer mudanca aqui precisa seguir a trilha `player-runtime` governada, com
health e rollback.

### `media-system` / imagem

E a frente correta para forcar modo HDMI de forma confiavel, por exemplo via
boot args como `video=HDMI-A-1:1280x720@60` ou equivalente validado.

Essa frente exige imagem/base e homologacao. Nao deve ser empurrada como OTA
comum para frota existente.

## Perfis Candidatos

Comecar com poucos perfis:

- `auto`: comportamento atual, usa negociacao HDMI/EDID;
- `safe-1024x768-60`: fallback conservador para displays problematicos;
- `hdmi-720p60`: `1280x720@60`;
- `hdmi-1080p60`: `1920x1080@60`, apenas quando validado no display alvo.

Nao assumir `1080p60` como padrao universal sem matriz de telas.

## Plano Incremental

1. Observabilidade primeiro.
   Registrar modo observado, estado HDMI, classificacao e player health sem
   reiniciar player nem alterar display.

2. Matriz curta de telas.
   Testar pelo menos: display atual problematico, monitor/TV 1080p comum, boot
   sem HDMI, reconexao HDMI e power-cycle apenas da tela.

3. Perfil sem modeset.
   Registrar `requested_profile` e `observed_mode`, inicialmente sem forcar
   resolucao em runtime.

4. Imagem lab com modo forcado.
   Se a matriz provar necessidade, gerar imagem lab com um unico modo forcado
   allowlisted e fallback claro por cartao/imagem.

5. Promocao seletiva.
   So promover perfil forcado para lote quando ele superar `auto` nos displays
   alvo sem regressao de boot, player, OTA ou rollback.

## Regras De Nao Regressao

- Nao forcar resolucao por OTA comum em placas existentes.
- Nao colocar modo HDMI arbitrario em `/data/config/config.json`.
- Nao introduzir X11/Wayland/compositor para resolver esta frente.
- Nao criar loop agressivo de DPMS/modeset.
- Nao reiniciar board automaticamente quando a evidencia aponta para sink/tela
  travada mas player saudavel.
- Nao bloquear M5/M4 se display nao for risco real de lote.

## Proximo Marco

Marco D1: coletar baseline de display com a tela real do cliente/lab e registrar
se o problema e:

- EDID ausente/ruim;
- modo baixo mas funcional;
- tela preta com board saudavel;
- player/decode travado;
- ou config/rotacao.

Depois de D1, decidir se seguimos com apenas diagnostico/status ou se abrimos
imagem lab de perfil forcado.

Estado de D1 em 2026-07-06: fechado para a tela atual. Proximo passo pratico e
rodar a matriz curta com outro display 1080p comum e, se possivel, o display
real do cliente/lote antes de criar imagem com modo forcado.
