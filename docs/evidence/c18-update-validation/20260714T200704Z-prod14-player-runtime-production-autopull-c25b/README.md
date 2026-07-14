# Prod14 player-runtime production auto-pull C25B

Resultado: gate offline verde, com `mechanics_passed=true`,
`product_distribution_cleanliness_passed=true` e `blockers=[]`.

## Escopo provado

- imagem `c18-hwdecode-prod-14` / `c18.image-prod.14` gravada do zero;
- marker da imagem com SHA256
  `ef56eec47a977bb4f0d8d3f50a7934ae0ac5b1219fa52eaccb76f8483c4fb8f2`;
- onboarding real concluido, config privada persistida e player embutido ativo;
- estado `pre` sem `current` ou `previous`, adotando
  `/opt/totem/kiosky-player`;
- timer production disparou em `2026-07-14T19:47:43Z`, baixou a tag GitHub
  exata e adotou C25B por `/data/player-runtime/current`;
- segunda invocacao foi `no-op`, sem mudar state, links ou a invocacao do
  player;
- rollback autorizado voltou ao fallback da imagem, removeu os dois links e
  reiniciou/verificou o player;
- nova aplicacao autorizada restaurou C25B sem criar `previous`;
- janela restaurada de 600 segundos passou com 560 amostras, zero
  `media_load_failed`, restart de MPV, restart de servico, erro/timeout de IPC,
  acao de watchdog, falha panfrost, MMC ou ext4;
- freeze publico de `player-runtime` permaneceu em `rc=44` nas cinco fases.

A imagem declara C25B como baseline e o alvo remoto e a release C25B exata. A
prova material verifica o caminho remoto e a topologia: timer real, download e
hashes exatos da release, origem GitHub autorizada, promocao para `/data`,
`no-op`, retorno ao `/opt` da imagem e reaplicacao. Ela nao clama equivalencia
byte a byte de toda a arvore embarcada nem mudanca funcional entre os alvos.

## Diagnostico preservado

A primeira coleta iniciada imediatamente apos o rollback foi vermelha. Ela
capturou quatro amostras do status anterior, quatro amostras transitórias em
`waiting_for_content` e depois recuperacao continua para `playing`, sem
`media_load_failed`, restart ou falha de frame. O rollback em si tinha
terminado com `service_health_passed=true`.

Essa janela esta em `diagnostic-rollback-immediate/` e nao e entrada do gate.
Sem repetir o rollback ou alterar estado OTA, uma nova janela foi coletada
depois que a nova invocacao publicou status proprio; ela passou e continuou
presa ao mesmo `last_operation` de rollback. O runbook foi corrigido para
exigir nova `InvocationID`, novo `status.started_at`, `playing`, MPV ativo e
item atual antes de iniciar deep-health apos uma troca.

## Non-claims

- nao autoriza `latest` amplo nem futuros alvos de `player-runtime`;
- nao prova delta funcional de payload, rollout por grupos ou attestation no
  device;
- nao altera MPV, ffmpeg, kernel, imagem base, midia ou config por OTA;
- nao prova o timer independente de `totem-core`, que ficou desabilitado
  somente durante esta sequencia para evitar mutacao concorrente;
- reboot final e alinhamento da release `totem-core stable` pertencem aos
  marcos seguintes.
