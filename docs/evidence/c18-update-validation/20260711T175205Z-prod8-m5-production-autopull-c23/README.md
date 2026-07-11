# Prod8 M5 production auto-pull C23

Resultado: `player_runtime_production_autopull_evidence_ready`.

## Escopo provado

- imagem `c18-hwdecode-prod-8` / `c18.image-prod.8` gravada do zero;
- onboarding real pelo wizard, pareamento autorizado e config privada gravada
  como `0640 root:totem`, sem publicar valores;
- playback apos onboarding verde, com um MPV, nove itens e HW decode
  `v4l2request-copy`;
- baseline rollback-safe
  `c18.player-runtime-homolog-20260703-baseline-bridge-8ac1c63` preparado
  localmente e validado antes de abrir o timer;
- timer production original disparou em `2026-07-11T17:22:47Z`, buscou a tag
  GitHub exata e adotou
  `c18.player-runtime-homolog-20260710-c23-ipc-fe4347c`;
- segunda invocacao foi no-op sem mudar state, current ou previous;
- rollback autorizado voltou ao bridge e reiniciou/verificou o player;
- segunda troca autorizada restaurou C23 e deixou o bridge como previous;
- janela restaurada canonica de 600 segundos passou com 564 amostras, zero
  `media_load_failed`, restart de MPV, restart do servico, timeout/erro de IPC,
  acao de watchdog, falha panfrost, MMC ou ext4;
- freeze publico de `player-runtime` permaneceu em `rc=44` nas cinco fases.

O gate offline `m5-evidence-gate.json` passou com:

- `mechanics_passed=true`;
- `product_distribution_cleanliness_passed=true`;
- `blockers=[]`.

## Diagnostico preservado

A primeira janela restaurada usou intervalo nao canonico de 5 segundos. Essa
cadencia ficou alinhada a videos de 5/15 segundos e excedeu o limite agregado
de atrasos de transicao, embora tenha registrado zero falhas operacionais. Ela
esta em `diagnostic-interval5/` como diagnostico nao decisivo. A evidencia
decisiva foi recoletada com o intervalo padrao de 1 segundo, sem mudar player,
gate ou estado OTA.

O snapshot diagnostico preserva `artifact_dir_name=restored-deep-health`, nome
original no momento da coleta; o diretorio foi arquivado depois como
`restored-interval5-negative-deep-health` e o JSON nao foi reescrito.

## Observacao independente de totem-core

Durante a janela, o timer independente de `totem-core` tentou a release stable
remota antiga `c18.ota-core-prod-20260705T184013Z-ccaf5a1`. O updater recusou
corretamente o downgrade sobre o core C21.9 embutido, com `rc=45`, sem alterar
o core atual. Isso nao invalida a prova C23, mas deve ser tratado na frente de
publicacao/promotion de `totem-core` para evitar uma unit failed recorrente.
Depois do diagnostico, o estado failed foi limpo sem alterar core ou timers; a
placa terminou com zero units failed, ambos os timers ativos, C23 em current e
o bridge em previous.

## Non-claims

- nao libera `latest` amplo nem futuros alvos de `player-runtime`;
- nao promove stable generico ou H2 por inferencia;
- nao prova rollout por grupos, dashboard ou attestation no device;
- nao atualiza MPV, ffmpeg, kernel, imagem base, midia ou config por OTA;
- nao declara a tentativa de intervalo 5 segundos como evidencia positiva.
