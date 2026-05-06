# C10.10.2 - Shutdown UX

Data: 2026-05-06

Status: validado em placa dev e segunda placa, sem executar poweroff real.

## Objetivo

C10.10.1 classificou o incidente de tela preta/SSH indisponivel como
`POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`: o boot anterior terminou em
`clean_poweroff`. C10.10.2 transforma isso em UX explicita de produto.

## O Que Mudou

- O splash local ganhou uma tela de `Desligamento seguro`.
- A mensagem informa que, quando a tela apagar, e necessario remover e
  reconectar a energia para ligar novamente.
- O splash tambem passa a ter modo `reboot`, separado de `shutdown`.
- O runner `run_c10_10_2_shutdown_ux.sh` adiciona preview/simulacao sem
  executar poweroff por padrao.
- O modo `--execute-poweroff` existe apenas atras da frase forte:
  `CONFIRMO DESLIGAR TOTEM`.

## Semantica de Produto

- `Reiniciar totem`: reboot controlado. O appliance deve voltar sozinho.
- `Desligar com seguranca`: poweroff/halt. F10, teclado e SSH deixam de
  funcionar, e religar exige power cycle fisico.

## Validacao Executada

```bash
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@dev> --prepare-only
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@dev> --inspect
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@dev> --preview-shutdown-screen
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@dev> --simulate-shutdown-flow-no-poweroff
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@test> --prepare-only
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@test> --inspect
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@test> --preview-shutdown-screen
scripts/remote/run_c10_10_2_shutdown_ux.sh <root@test> --simulate-shutdown-flow-no-poweroff
```

Resultado:

- dev validada primeiro;
- segunda placa validada depois de reconectar HDMI;
- tela `Desligamento seguro` renderizou;
- mensagem menciona power cycle fisico;
- preview/simulacao nao executaram poweroff;
- servico final `active/enabled`;
- `public_state=player_running`;
- playback `playing`;
- `NRestarts=0`.

## Guardrails

- Nao altera `/data/config/config.json`.
- Nao chama writer.
- Nao altera Wi-Fi/NetworkManager.
- Nao instala pacotes.
- Nao habilita read-only.
- Nao faz corte seco.
- Nao publica secrets, config real, SSID, IP, MAC, DNS ou logs brutos.

## Proximo Passo

O manifest passa a marcar `shutdown_ux_followup_required=false` e
`ready_for_c11_readiness=true`.

Proxima rodada recomendada: C11.0 read-only readiness audit. Ainda nao gerar
imagem final, nao habilitar read-only e nao executar corte seco.
