# C6.4 - start controlado com config real na placa de desenvolvimento

Data: 2026-05-02

## Objetivo

Iniciar `kiosky-player.service` controladamente com a config real ja escrita em
C6.3A, observar o launcher/player por curto periodo e registrar evidencia
sanitizada sem alterar config real.

## Escopo

- Placa: desenvolvimento, sem registrar IP ou hostname.
- Placa de homologacao: fora de escopo.
- Config real: ja escrita por C6.3A.
- Conteudo de `/data/config/config.json`: nao lido.
- `/data/config/config.json`: nao escrito e nao alterado nesta rodada.
- Launcher, renderer, unit systemd, `kiosky-player`, NetworkManager e Wi-Fi:
  nao alterados.
- `nmcli`, `apt` e `journalctl`: nao executados.

## Preflight read-only

Sem ler conteudo da config:

- `/data/config/config.json` existe: true.
- Tipo: arquivo comum.
- Mode: `640`.
- Owner/group: `root:totem`.
- Leitura por `totem`: true.
- Gravacao por `totem`: false.
- Servico antes do start: `inactive`.
- Servico enabled: sim.
- HDMI/display: conectado.

## Start controlado

Comando executado:

```sh
systemctl start kiosky-player.service
```

Estado apos start:

- `systemctl is-active`: `active`.
- `ActiveState`: `active`.
- `SubState`: `running`.
- `User`: `totem`.
- `Group`: `totem`.

Nao houve loop de restart observado durante o observer.

## Observer

Duração: 120 segundos.

Amostras sanitizadas foram coletadas em 0, 30, 60, 90 e 120 segundos.

Resultado final observado:

- Servico: `active/running`.
- `NRestarts`: 0.
- Status publico agregado presente: true.
- `public_state`: `player_running`.
- `public_display_connected`: true.
- `public_config_state`: `valid`.
- `public_player_state`: `running`.
- `public_service_state`: `active`.
- `public_error_code`: `none`.
- Launcher status presente: true.
- `launcher_state`: `running`.
- `launcher_display_connected`: true.
- Player status presente: true.
- `playback_state`: `playing`.
- `mpv_running`: true.
- `playlist_size`: observado como numero agregado.
- `current_index`: observado como numero agregado.
- `last_poll_success`: campo presente.
- `kiosk.py`: ativo.
- MPV: ativo.
- Renderer ativo junto com player: nao observado na checagem final.

Observacao: uma checagem inicial por argumento de processo indicou renderer
ativo, mas esse metodo podia casar com o proprio comando de observacao. A
checagem final por `/proc` sem imprimir argumentos confirmou:

- `renderer_script_active`: false.
- `renderer_script_count`: 0.
- `mpv_process_count`: 1.
- `kiosk_py_count`: 1.

## Sanitizacao

- `/tmp/dadooh-status/status.json` nao apresentou marcador de secret.
- `/tmp/dadooh-status/status.svg` nao apresentou marcador de secret, exceto o
  namespace SVG padrao, que foi excluido da checagem.
- `/tmp/kiosky-status.json` foi tratado como status bruto do player e lido
  somente por campos allowlisted; seu conteudo nao foi publicado nem copiado.
- Nenhum conteudo da config real foi lido.
- Nenhum `api_key`/token foi publicado.
- Nenhuma `api_url` real foi publicada.
- Nenhum `environment_id` real foi publicado.
- Nenhum `station_id` real foi publicado.
- Nenhum payload, URL privada, nome de midia, log bruto ou journal foi
  publicado.

## Decisao final do servico

Nao houve decisao humana explicita para parar o servico ao final. Como o start
foi bem-sucedido, o observer passou e nao houve falha, foi mantido o estado
atual observado:

- Decisao final: servico rodando.
- Player iniciado: sim.
- Estado final: `active/running`.

## Conclusao

C6.4 passou na placa de desenvolvimento. Com HDMI conectado e config real ja
escrita por C6.3A, o servico iniciou, o launcher considerou a config valida, o
player entrou em `player_running`, o MPV ficou ativo e nao houve restart loop
visivel durante 120 segundos.

## Proximos bloqueios

- Revisao humana desta evidencia.
- Definir proxima rodada de observacao prolongada, se necessario.
- Definir criterio de rollback/parada caso o player apresente falha em uso
  prolongado.
