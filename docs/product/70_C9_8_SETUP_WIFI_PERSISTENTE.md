# C9.8 - Setup Wi-Fi Persistente

Status: implementado e validado em bancada com HDMI/teclado.

Data: 2026-05-04

## Objetivo

Evoluir o Setup Produto Local V0 para configurar Wi-Fi dedicado persistente,
ainda sem hotspot, portal, writer ou escrita de config real.

## Implementado

- o adapter Wi-Fi ganhou gate explicito para manter perfil dedicado;
- persistencia exige `--persistent-product-wifi`, `--keep-dedicated-profile` e
  a frase `CONFIRMO MANTER WIFI DEDICADO C9.8`;
- perfis persistentes ficam limitados aos prefixos `dadooh-c9-8-` ou
  `dadooh-product-wifi-`;
- o wizard agora separa `Testar Wi-Fi e desfazer ao final` de
  `Configurar Wi-Fi deste totem`;
- credenciais continuam entrando somente no totem, via TTY/HDMI, e secrets
  temporario sob `/tmp` e removido ao final;
- o runner C9.8 pausa/restaura `kiosky-player.service` apenas durante o fluxo
  local.

## Diferenca de Modos

- teste com rollback: ativa Wi-Fi, valida, remove o perfil dedicado ao final;
- Wi-Fi persistente: ativa Wi-Fi e mantem apenas o perfil dedicado do produto;
- em ambos os casos, status e summary publicam somente campos agregados.

## Continua Bloqueado

- hotspot e portal;
- backend/login;
- writer real;
- leitura ou escrita de `/data/config/config.json`;
- alteracao do `kiosky-player`;
- reboot automatico.

## Validacao

Passou:

- `python3 scripts/board/totem_wifi_nm_adapter.py --self-test`;
- `python3 scripts/board/totem_setup_local_wizard.py --self-test`;
- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --prepare-only`;
- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --run-cancel`;
- `scripts/remote/run_c9_8_setup_wifi_persistent.sh <host> --run-complete-with-wifi-persistent`.

C5.1 `--allow-mock` deve passar para a candidata. C5.1 `--real-dry-run` deve
continuar falhando enquanto backend/API usam placeholders.

Resultado de bancada:

- Wi-Fi activation `success`;
- perfil dedicado final presente;
- secrets removido;
- candidata gerada;
- C5.1 `--allow-mock` passou;
- C5.1 `--real-dry-run` falhou como esperado;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback final `playing`;
- player/MPV ativos e renderer/setup ausentes.

## Proximo Passo

C10.0 deve tratar writer/config real controlado depois do Wi-Fi persistente
validado, sem misturar hotspot/portal.
