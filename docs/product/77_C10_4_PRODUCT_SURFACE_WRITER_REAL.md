# C10.4 - Product Surface V0 com Writer Real

Status: implementado e validado em bancada com confirmacao humana explicita.

Data: 2026-05-05

## Objetivo

Validar o fluxo completo com a superficie de produto C10.3:
orientacao primeiro, Wi-Fi por lista/read-only, wizard visual, handoff privado,
writer real, config real e start controlado do player.

## Implementado

- `scripts/remote/run_c10_4_product_surface_writer_real.sh`;
- modos `--prepare-only`, `--preflight`, `--run-dry-run` e
  `--run-real-write-start`;
- host obrigatorio informado no comando, sem IP fixo no runner;
- dry-run visual real em HDMI/TTY com pausa controlada do player;
- reuso do handoff privado C10.0;
- reuso do writer real guardado C6;
- status final sanitizado com orientacao, categorias de Wi-Fi, writer, backup,
  permissoes, servico e processos.

## Fluxo

O dry-run exige confirmacao para pausar o player, roda o wizard visual C10.3,
monta candidata privada sob `/tmp`, valida C5.1 `real-dry-run` e remove
temporarios privados. Ele nao chama writer e nao escreve `/data/config`.

O modo real exige a frase:

```text
CONFIRMO PRODUCT SURFACE WRITER REAL C10.4
```

Somente depois disso o runner chama o writer real, cria backup, aplica
permissoes esperadas e reinicia o player.

## Guardrails

- config real, backup e candidata privada nao sao publicados;
- api_key, api_url real, environment_id real e station_id real nao sao
  publicados;
- SSID, senha, IP, MAC, BSSID, gateway, DNS, hostname, UUID e logs brutos nao
  sao publicados;
- Wi-Fi/NetworkManager nao e alterado;
- hotspot, portal, backend/login, root read-only, corte seco e reboot seguem
  fora desta rodada;
- repo `kiosky-player` nao e alterado.

## Validacao

Comandos executados:

```bash
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --prepare-only
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --preflight
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --run-dry-run --private-values-from-active-config
scripts/remote/run_c10_4_product_surface_writer_real.sh <board-host> --run-real-write-start --private-values-from-active-config
```

Se a fonte privada vier da config ativa, o runner exige confirmacao adicional
antes de ler somente endpoint/credencial e gravar arquivo temporario restrito
sob `/tmp`, sem imprimir valores.

Resultados:

- `--prepare-only` passou;
- `--preflight` passou;
- `--run-dry-run` passou sem writer e sem escrita em `/data/config`;
- `--run-real-write-start` passou com writer real;
- orientacao `portrait_right`, `rotation_deg=90`;
- `network_step=existing_configured_wifi`;
- C5.1 `real-dry-run` privado passou;
- writer retornou `passed`;
- backup criado;
- config real escrita com `root:totem` `0640`;
- usuario `totem` le e nao escreve;
- temporarios privados removidos;
- servico final `active/enabled`, `NRestarts=0`;
- `public_state=player_running`, playback `playing`;
- player/MPV ativos, renderer/setup ausentes;
- Wi-Fi/NetworkManager nao foi alterado.

## Proximo Passo

C10.5 deve focar boot/shutdown sem Linux aparente, mantendo rollback e ainda sem
root read-only ou corte seco.
