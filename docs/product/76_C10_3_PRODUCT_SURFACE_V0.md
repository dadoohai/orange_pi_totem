# C10.3 - Superficie de Produto V0

Status: implementado e validado em bancada com confirmacoes humanas explicitas.

Data: 2026-05-04

## Objetivo

Fechar problemas visiveis antes de read-only/homologacao: reduzir exposicao de
Linux, colocar orientacao no inicio do setup e tornar a etapa Wi-Fi mais
operavel.

## Implementado

- orientacao virou a primeira etapa do wizard visual;
- as telas seguintes registram o layout escolhido e adaptam largura de cards e
  campos para paisagem/retrato;
- a etapa Conexao agora oferece:
  - `Usar Wi-Fi ja configurado`;
  - `Selecionar rede Wi-Fi`;
  - `Continuar em modo de bancada`;
- a lista Wi-Fi usa `nmcli` somente em modo read-only;
- SSIDs aparecem somente no HDMI local para escolha do operador;
- status/summary/candidata registram apenas contagem e categorias:
  `wifi_networks_found_count`, `selected_network_present`,
  `selected_network_signal_bucket` e `selected_network_security_present`;
- senha Wi-Fi continua oculta;
- o runner C10.3 prepara preview, cancelamento, conclusao com Wi-Fi existente,
  preview de lista Wi-Fi e guardrails reversiveis de boot.

## Boot Visual

O runner possui modos separados para aplicar e reverter guardrails:

- `--apply-boot-visual-guardrails`;
- `--rollback-boot-visual-guardrails`;
- `--reboot-visual-check`.

Esses modos exigem confirmacao humana explicita. A aplicacao faz backup de
`/boot/armbianEnv.txt`, adiciona argumentos silenciosos quando o arquivo existe
e desabilita `getty` em TTYs visiveis do produto. O rollback restaura o backup
e o estado anterior dos gettys.

Nada disso e aplicado por padrao.

## Guardrails

- writer real nao e chamado;
- `/data/config/config.json` nao e lido nem escrito;
- Wi-Fi/NetworkManager nao e alterado em preview/listagem;
- SSID e senha nao entram em status, summary, docs ou evidencia;
- IP, MAC, BSSID, gateway, DNS, hostname, UUID e logs brutos continuam
  proibidos;
- hotspot, portal, backend/login, root read-only e corte seco seguem fora.

## Validacao

Validacoes locais:

- self-tests do wizard visual;
- self-tests do adapter Wi-Fi;
- self-tests do coletor TTY;
- C5.1 self-test;
- `git diff --check`;
- `bash -n` do runner C10.3.

Validacao remota executada:

```bash
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --prepare-only
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --preview-wizard
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-wifi-list-preview
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-cancel
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --run-complete-existing-wifi
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --apply-boot-visual-guardrails
scripts/remote/run_c10_3_product_surface_v0.sh <board-host> --reboot-visual-check
```

Resultados:

- preview visual passou;
- lista Wi-Fi local passou com 7 redes encontradas e somente categorias em
  artefatos;
- cancelamento passou;
- conclusao com Wi-Fi dedicado existente passou;
- candidata gerada com `rotation_deg=90`;
- C5.1 `allow-mock` passou;
- C5.1 `real-dry-run` falhou como esperado por placeholders;
- guardrails visuais de boot aplicados com rollback registrado;
- reboot visual controlado passou por snapshot sanitizado;
- estado final `active/enabled`, `NRestarts=0`, `public_state=player_running`,
  playback `playing`, player/MPV ativos, renderer/setup ausentes.

Observacao: o runner foi ajustado apos a validacao para aguardar retorno de SSH
por TCP/22 antes do SSH final, pois o acesso atual usa senha interativa.

## Proximo Passo

C10.4 deve rodar o fluxo completo com Product Surface V0 + writer real apenas
se as mudancas de wizard/boot forem aceitas em bancada. C11.0 segue reservado
para auditoria de readiness de root read-only.
