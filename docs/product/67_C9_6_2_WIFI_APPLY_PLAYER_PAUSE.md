# C9.6.2 - Wi-Fi apply com pausa controlada do player

Status: patch de bancada para liberar HDMI/TTY durante apply Wi-Fi real.

Data: 2026-05-04

## Objetivo

C9.6.1 confirmou que o caminho com console local e rollback era viavel, mas o
TTY nao ficou visivel quando o player/MPV continuou ocupando a HDMI. C9.6.2
autoriza uma pausa operacional curta do `kiosky-player.service` somente durante
coleta local de credenciais e apply Wi-Fi controlado.

## Implementado

- novo modo `--local-console-apply-with-player-pause` no runner local-console;
- snapshot inicial e final sanitizados;
- confirmacao textual especifica antes de parar o servico;
- `systemctl stop kiosky-player.service` apenas durante o teste;
- verificacao de HDMI livre por contagem agregada de player/MPV/renderer/setup;
- fluxo TTY2 por `openvt` para coleta local de SSID/senha;
- janela operacional de operador maior que o timeout tecnico do `nmcli`;
- apply com perfil dedicado `dadooh-c9-6-wifi-test`, timeout e rollback-after-test;
- restauracao do servico em `trap` para sucesso, falha, cancelamento ou timeout.

## Garantias

- credenciais sao digitadas apenas no totem;
- senha e identificadores de rede nao entram em argv, stdout persistente, docs
  ou evidencia;
- o arquivo temporario de credenciais e solicitado com cleanup ao final do apply;
- o runner nao le nem escreve `/data/config/config.json`;
- writer, player repo, MPV flags, hotspot, portal e reboot seguem fora;
- rollback toca somente o perfil dedicado C9.6.

## Validacao

```bash
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_wifi_local_credentials_tty.py --self-test
bash -n scripts/remote/run_c9_6_1_wifi_local_console_apply.sh
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --prepare-only
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-preflight
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-apply-with-player-pause
```

O ultimo comando exige humano no HDMI/teclado e a frase exata de pausa
operacional antes de parar o player.

Resultado de bancada: o TTY apareceu apos pausar o player e o apply real foi
tentado. A ativacao Wi-Fi retornou `failure`; o rollback foi tentado, o perfil
dedicado ficou ausente ao fim, o servico foi restaurado `active/enabled` com
`NRestarts=0` e o playback voltou a `playing`. Nenhum dado sensivel foi
publicado na evidencia.

## Fora de Escopo

- manter Wi-Fi permanente;
- hotspot ou portal;
- integracao ao wizard;
- escrita de config real;
- writer;
- alteracao do `kiosky-player`.

## Proximo Passo

C9.7 deve consumir o resultado agregado do Wi-Fi controlado no Setup Produto
Local V0, ainda sem portal/hotspot e sem writer/config real.
