# C10.6 - Abrir Configuracoes do Totem com player rodando

Data: 2026-05-05

## Objetivo

Validar o caminho correto de produto para abrir as Configuracoes do Totem
enquanto o player esta rodando. Nesta frente, Configuracoes do Totem e o wizard
visual existente. Nao ha menu paralelo de manutencao, terminal local, shell,
login Linux ou modo root na UI do operador.

## Conceito validado

O fluxo C10.6 e:

1. player esta em exibicao;
2. um gatilho controlado de bancada abre Configuracoes;
3. splash/transicao cobre a HDMI;
4. `kiosky-player.service` e pausado temporariamente;
5. o wizard visual assume a tela;
6. operador cancela ou conclui;
7. ao cancelar, o player volta sem alterar config;
8. ao concluir em dry-run, candidata e handoff privado sao validados sem writer;
9. escrita real continua bloqueada por confirmacao explicita e pelo runner C10.4
   ja validado;
10. player volta e o estado publico converge para `player_running`.

## O que C10.6 nao faz

- nao cria menu de manutencao/suporte;
- nao expõe terminal, root, shell ou login Linux;
- nao implementa PIN final;
- nao implementa botao fisico final;
- nao cria hotspot ou portal;
- nao altera Wi-Fi/NetworkManager sem fluxo explicitamente autorizado;
- nao chama writer no cancelamento ou dry-run;
- nao altera `/data/config/config.json` no cancelamento ou dry-run;
- nao altera `kiosky-player`;
- nao habilita root read-only;
- nao faz corte seco.

## Acesso futuro

Nesta rodada, o acesso e de bancada via runner remoto autorizado. O contrato de
produto fica separado:

- operador acessa "Configuracoes do Totem" por gatilho local controlado;
- PIN/senha local, tecla/combinacao ou botao fisico ficam para rodada futura;
- suporte tecnico, diagnostico, reboot/desligamento e terminal/root ficam fora
  da UI comum de configuracao.

## Runner

Runner:

```bash
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --prepare-only
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --preview-open-settings
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-open-cancel
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-open-complete-dry-run
```

Modos que pausam o player exigem confirmacao humana explicita. O dry-run pode
usar uma fonte privada sob `/tmp` ou a config ativa como fonte privada somente
com confirmacao adicional, sem publicar valores.

## Proximo passo

C10.7 deve tratar Suporte Local V0 como frente separada: diagnostico,
reiniciar exibicao, reboot seguro, desligamento seguro e PIN/senha local.
