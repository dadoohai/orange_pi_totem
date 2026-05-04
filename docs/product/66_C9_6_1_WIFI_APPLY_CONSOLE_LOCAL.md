# C9.6.1 - Wi-Fi apply com console local

Status: implementado para bancada com HDMI/teclado local e rollback automatico.

Data: 2026-05-04

## Por que existe

C9.6 bloqueou apply remoto quando o preflight classificou o caminho SSH como
Wi-Fi. Sem Ethernet disponivel, trocar Wi-Fi pode derrubar a sessao remota.
C9.6.1 permite prosseguir somente porque ha console local para acompanhar e
recuperar o teste.

## Implementado

- `totem_wifi_local_credentials_tty.py` coleta credenciais na propria tela do
  totem;
- `run_c9_6_1_wifi_local_console_apply.sh` abre o fluxo local por `openvt`;
- o adapter aceita a excecao `--allow-ssh-risk-with-local-console-confirmed`
  somente junto de `--local-console-confirmed`;
- a frase de apply com console local e separada:
  `CONFIRMO APPLY WIFI REAL C9.6 COM CONSOLE LOCAL`;
- rollback-after-test e o default operacional desta rodada;
- o perfil tocado continua limitado ao dedicado C9.6.

## Credenciais

O operador digita rede e senha no totem. A senha nao passa por chat, argumento
de processo ou evidencia. O arquivo temporario fica sob `/tmp`, com diretorio
`0700` e arquivo `0600`, e nao e copiado para docs ou evidencia.

## Recuperacao Local

A tela local mostra que o Wi-Fi esta sendo aplicado com rollback automatico. Se
a sessao remota cair, o processo local continua no TTY. O operador pode acionar
rollback manual limitado ao perfil dedicado pressionando `R`.

## Validacao

Seguro:

```bash
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_wifi_local_credentials_tty.py --self-test
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --prepare-only
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-preflight
```

Apply real:

```bash
scripts/remote/run_c9_6_1_wifi_local_console_apply.sh <host> --local-console-apply-rollback-after-test
```

Esse modo exige humano olhando HDMI/teclado, confirmacao textual remota e
credencial digitada localmente no totem.

Observacao de bancada: se o player/MPV estiver exibindo midia e segurando a
HDMI, o TTY local pode nao ficar visivel. Nesta rodada o runner deve tratar
isso como bloqueio seguro: sem credencial local coletada e sem status do
adapter, o apply nao e considerado executado.

## Fora de Escopo

- hotspot;
- portal;
- integracao ao wizard C9.4;
- writer/config real;
- player, MPV, renderer ou flags MPV;
- reboot;
- persistencia permanente do perfil como default.

## Proximos Passos

C9.7 deve integrar o resultado agregado do teste Wi-Fi ao Setup Produto Local
V0. Hotspot, portal e writer continuam frentes separadas.
