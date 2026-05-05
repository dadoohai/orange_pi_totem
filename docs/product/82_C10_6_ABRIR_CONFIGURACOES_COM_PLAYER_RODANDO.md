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
2. um gatilho local V0 por teclado ou um runner de bancada abre Configuracoes;
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

## Acesso V0 em C10.6

Nesta rodada, o acesso local V0 foi validado em bancada por runner e gatilho
temporario. A rodada seguinte, C10.6.1, transforma o acesso em servico
persistente.

O caminho de produto definido e `F10` segurado por 5 segundos. `Ctrl+I` e `F12`
nao sao caminho principal; ficam apenas como alternativas tecnicas se flags de
desenvolvimento forem habilitadas explicitamente.

O trigger monitora `/dev/input` em modo read-only, detecta apenas o gesto longo
permitido e grava uma solicitacao publica restrita em
`/run/dadooh-settings/request.json`:

- `schema_version`;
- `requested_at`;
- `trigger_type=keyboard_f10_hold`;
- `action=open_settings`.

Depois disso, o wizard visual de Configuracoes abre diretamente. PIN/senha local
e confirmacao modal ficam para rodada posterior.

O contrato de produto fica separado:

- operador acessa "Configuracoes do Totem" por gatilho local controlado;
- PIN/senha local ou botao fisico ficam para rodada futura;
- suporte tecnico, diagnostico, reboot/desligamento e terminal/root ficam fora
  da UI comum de configuracao.

## Runner

Runner:

```bash
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --prepare-only
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --preview-open-settings
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-open-cancel
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-open-complete-dry-run
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --install-trigger-temporary
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --run-trigger-local-human
scripts/remote/run_c10_6_open_settings_from_player.sh <host> --uninstall-trigger-temporary
```

Modos que pausam o player exigem confirmacao humana explicita. O dry-run pode
usar uma fonte privada sob `/tmp` ou a config ativa como fonte privada somente
com confirmacao adicional, sem publicar valores.

## Validacao

Validado nesta frente:

- self-test do trigger: F10 curto nao abre, F10 longo abre, Ctrl+I longo abre,
  outras teclas nao abrem e caracteres nao sao registrados;
- abertura do wizard visual a partir do player pelo runner;
- cancelamento sem alterar config;
- restauracao do player;
- trigger temporario local com F10/Ctrl+I abrindo o wizard visual.

O trigger temporario de systemd fica em `/run/systemd/system` e nao e habilitado
de forma persistente. A instalacao e reversivel por
`--uninstall-trigger-temporary`.

## Proximo passo

C10.6.1 instala o gatilho persistente por `F10` longo. C10.7 deve tratar
Suporte Local V0 como frente separada: diagnostico, reiniciar exibicao, reboot
seguro e desligamento seguro.
