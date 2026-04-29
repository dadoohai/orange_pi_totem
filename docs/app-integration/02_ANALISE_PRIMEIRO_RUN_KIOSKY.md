# Analise do primeiro run manual do kiosky-player

Data da analise: 2026-04-29

## Escopo

Esta analise usa apenas artefatos locais ja coletados da rodada `20260429-144234-kiosky-manual-probe`.

Artefatos principais analisados:

- `kiosky-manual-20260429-143320-0300.tar.gz`
- `totem-diag-20260429-144151-0300.tar.gz`

Os artefatos foram extraidos localmente em `/tmp/totem-kiosky-manual-review`. Nenhum comando foi executado na Orange Pi, `kiosk.py` nao foi iniciado, MPV nao foi iniciado e nenhum pacote foi instalado.

## Resumo do primeiro run

O `kiosky-player` foi executado manualmente como usuario `totem`, com timeout controlado de 300 segundos, usando a config privada ja existente na placa em `/data/config/config.json`.

Resultado consolidado:

- `app-run` retornou `124`, coerente com timeout controlado.
- `stderr` do app ficou vazio.
- O app atualizou playlist com 5 itens.
- O app criou 5 arquivos de midia em `/data/media/kiosky-player`.
- O app criou 3 arquivos de estado em `/data/state/kiosky-player`.
- `/tmp/kiosky-status.json` existia ao final.
- O status final indicava `playback_state=playing`, `playlist_size=5` e `mpv_running=true`.
- `systemctl --failed` permaneceu com `0 loaded units listed`.
- Nao houve processo real `kiosk.py` ou `mpv` remanescente apos o timeout.
- A auditoria por marcador nao encontrou escrita em `/opt/totem/kiosky-player`.
- O operador confirmou que algumas midias apareceram fisicamente na tela, e tambem observou momentos de tela preta ou retorno ao terminal.

## Achados sobre IPC/restart

O stdout do app registrou 21 ocorrencias de `MPV IPC unresponsive`, todas com `restarting`.

Momentos aproximados:

- de 14:33:35 a 14:38:23;
- cadencia frequente, perto de um aviso a cada 13-14 segundos durante boa parte do run;
- a ultima ocorrencia apareceu apos o `Signal 15 received`, durante o encerramento por timeout.

Tambem houve 5 ocorrencias de `Failed to load media, restarting MPV`:

- aproximadamente em 14:35:23;
- aproximadamente em 14:36:05;
- aproximadamente em 14:36:33;
- aproximadamente em 14:37:43;
- aproximadamente em 14:38:10.

As falhas de load nao imprimem identificador de midia. Pela sequencia de `Playing` com aliases sanitizados, elas ocorreram em transicoes de playlist antes de retries bem-sucedidos. Nao ha evidencia de falha definitiva de uma unica midia, porque todas as 5 midias foram reproduzidas em logs e cada alias sanitizado apareceu 6 vezes.

O status final era favoravel apesar dos avisos:

- `playback_state=playing`;
- `mpv_running=true`;
- `consecutive_failures=0`;
- `blocked_media_count=0`;
- `last_poll_error=null`;
- `last_render_error=null`.

## Kernel, systemd e display

Nao apareceram bloqueadores no corpo dos filtros criticos:

- sem `Internal error: Oops`;
- sem `kernel panic`;
- sem `EXT4-fs error`;
- sem `Aborting journal`;
- sem `Remounting filesystem read-only`;
- sem `mmc timeout/reset`;
- sem alerta de voltage.

O filtro de display/DRM antes e depois do probe ficou identico. Ele mostra inicializacao de HDMI/DRM/GPU no boot, sem novo erro associado ao run manual do app.

`systemctl --failed` antes, depois e no diagnostico consolidado permaneceu em `0 loaded units listed`.

## Hipoteses possiveis

1. O watchdog do app pode estar recebendo timeout no ping IPC do MPV mesmo quando a reproducao continua. Isso explica restarts frequentes sem queda final do app.
2. Pode haver corrida entre restart do watchdog e transicao de midia. Nesse caso, o `loadfile` falha uma vez porque o IPC esta sendo fechado/reaberto, o app reinicia MPV e o retry funciona.
3. Pode haver sensibilidade a uma combinacao de midia, codec, tamanho ou duracao, mas os artefatos nao apontam para uma unica midia. Os retries apareceram antes de aliases diferentes e todos os aliases tocaram.
4. Como o app descarta stdout/stderr do MPV, os artefatos nao permitem distinguir entre travamento real do MPV, atraso de resposta IPC, reinicializacao do processo, problema de decode ou perda temporaria de contexto DRM/KMS.
5. A observacao humana de tela preta ou retorno ao terminal e compativel com restarts/falhas de load, mas nao prova causa sem captura do MPV ou marcacao de tempo visual mais precisa.

## Proximos testes propostos

Ainda sem systemd, sem apt e sem iniciar teste longo:

1. Fazer um segundo teste manual curto, de 5 a 10 minutos, com instrumentacao maior de MPV/IPC.
2. Capturar stderr/stdout do MPV em artefato temporario sanitizavel, ou adicionar log de geracao/restart do controlador, antes de repetir teste longo.
3. Registrar timestamps humanos quando aparecer tela preta ou retorno ao terminal, para comparar com os horarios de `MPV IPC unresponsive` e `Failed to load media`.
4. Se os retries continuarem concentrados nos mesmos aliases sanitizados, testar essas midias isoladamente com MPV manual via DRM/KMS, sem publicar URL, nome ou payload.
5. Considerar teste A/B controlado de config, por exemplo watchdog menos agressivo ou decodificacao sem hardware, apenas se documentado como variante temporaria de bancada.

## Criterios para liberar teste mais longo

Liberar teste manual mais longo somente quando um teste curto direcionado demonstrar:

- reducao clara dos avisos `MPV IPC unresponsive`;
- zero ou raras falhas `Failed to load media`, sempre com recuperacao imediata;
- nenhuma volta ao terminal observada pelo operador;
- status final `playing` e `mpv_running=true`;
- `consecutive_failures=0` e `blocked_media_count=0`;
- todas as midias esperadas aparecendo em logs e na tela;
- `systemctl --failed` com `0 loaded units listed`;
- nenhum `Oops`, `panic`, erro EXT4, remount read-only ou `mmc timeout/reset`;
- nenhuma escrita em `/opt/totem/kiosky-player`;
- nenhum processo `kiosk.py` ou `mpv` remanescente apos timeout.

## Recomendacao

A rodada permanece aprovada como primeiro run manual com ressalvas, porque o app iniciou, baixou midias, reproduziu, manteve status final coerente e encerrou por timeout controlado.

Porem, os avisos de IPC/restart foram frequentes demais para liberar teste longo ou systemd imediatamente. O proximo passo deve ser um teste manual curto e instrumentado, ainda sem systemd.
