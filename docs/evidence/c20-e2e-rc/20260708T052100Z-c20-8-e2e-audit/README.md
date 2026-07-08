# C20.8 Wizard E2E Audit

Data: 2026-07-08

Alvo: `totem-core` C20.8 na placa de homologacao.

Current na placa:
`releases/c20.8-clock-all-steps-20260708T045317Z-661c582`.

Previous/rollback:
`releases/c20.7-clock-metadata-20260708T042733Z-b9d8a00`.

## Veredito

Status: **passou para o primeiro E2E de guardrails**.

O fluxo provado nesta rodada:

- trigger F10 por evento de teclado abriu o wizard;
- wizard abriu em framebuffer real;
- navegacao chegou em `Revisao`;
- revisao bloqueou configuracao incompleta;
- `Enter` nao gerou candidata parcial;
- cancelamento saiu do wizard;
- player voltou ativo;
- `totem-open-settings.service` voltou a `inactive`;
- lock/request ficaram ausentes;
- guard de apply voltou verde;
- current/previous de `totem-core` ficaram coerentes.

## Nao-Claims

Esta rodada nao prova:

- escrita real de Wi-Fi;
- escrita real de config de ambiente;
- publish remoto;
- stable/producao;
- player-runtime;
- display/kernel/MPV;
- timezone, NTP ou RTC;
- imagem final de referencia.

O fluxo valido completo foi exercitado em modo `candidate-only` scripted, sem
writer real e sem rede real.

## Evidencias Principais

- `local/c20-e2e-rc-local-replay-20260708T052101Z/`: replay offline,
  18/18 assertions.
- `probe-v3/`: abertura por service-start controlado, revisao bloqueada,
  `Enter` bloqueado e retorno posterior limpo.
- `f10-uinput-probe-v2/`: abertura pelo trigger F10 via `/dev/uinput`,
  revisao bloqueada, `Enter` bloqueado, cancelamento e retorno limpo apos
  espera.
- `scripted-valid/`: fluxo valido `candidate-only`, com
  `candidate_generated=true`, `writer_called=false`,
  `real_config_written=false`, `wifi_changed=false` e `backend_called=false`.
- `board/f10-uinput-v2-post-wait-status.txt`: estado final limpo apos espera:
  player ativo, settings inativo, sem lock/request e guard verde.

Capturas reais decisivas:

- `f10-uinput-probe-v2/session-probe/captures/01-current-opened.jpg`;
- `f10-uinput-probe-v2/session-probe/captures/02-review.jpg`;
- `f10-uinput-probe-v2/session-probe/captures/03-enter-after-review.jpg`.

## Achados

### Passou

- A revisao incompleta fica bloqueada e explicita `Sem candidata parcial`.
- `Enter` na revisao incompleta muda a acao para correcao, sem salvar.
- O slot superior mostra data/hora tambem na etapa `Tela`.
- Nao houve faixa branca/corte no framebuffer real de revisao.
- A placa terminou saudavel apos espera: player ativo, settings inativo,
  guard verde.

### Nao-Blockers

- O estado logo apos cancelar pode ficar transitoriamente como
  `open_settings_service_activating`; apos espera curta ele limpa.
- A primeira tentativa de F10 virtual curto nao abriu o wizard porque o trigger
  escuta dispositivos por ciclos. O helper de QA foi ajustado para manter F10
  com repeticao e passou na segunda tentativa.
- A tentativa com `printf` direto no TTY foi descartada como harness invalido.

### Pendencias Para RC Completo

- Rodar um fluxo interativo valido ponta a ponta quando houver decisao explicita
  de testar escrita real ou quando o modo `candidate-only` for formalizado como
  criterio suficiente para esta fase.
- Incorporar o probe de C20 ao ritual de QA para proximas rodadas.
- Decidir se o cleanup transitorio merece polimento ou se permanece aceitavel
  como comportamento de systemd durante a saida.

## Scripts Adicionados

- `scripts/qa/c20_uinput_key_sequence.py`: injeta sequencias pequenas de tecla
  por `/dev/uinput` para QA de placa.
- `scripts/qa/c20_board_e2e_probe.sh`: probe controlado que abre settings por
  service-start e valida revisao/cancelamento.
- `scripts/qa/c20_board_open_wizard_probe.sh`: probe para uma sessao de wizard
  ja aberta ou aberta pelo trigger F10.
