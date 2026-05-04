# C9.6.3 - Diagnostico de falha Wi-Fi e retentativa

Status: implementado e validado em bancada com evidencia sanitizada.

Data: 2026-05-04

## Objetivo

Classificar a falha de ativacao Wi-Fi sem publicar identificadores e repetir uma
unica tentativa controlada com console local, mantendo rollback-after-test e
restauracao automatica do player.

## Implementado

- `--diagnose-last-failure` no adapter C9.6;
- categoria publica `failure_category`;
- modo remoto `--local-console-diagnose-retry-with-player-pause`;
- instrucao operacional curta no TTY para confirmar rede/senha testadas em
  outro dispositivo, WPA/WPA2 comum, sem portal cativo e sinal forte;
- diagnostico apenas por artefatos sanitizados e flags agregadas;
- cleanup do secrets-file confirmado por existencia, sem leitura do conteudo.

## Resultado de Bancada

- diagnostico da falha anterior: `nm_activation_failed_generic`;
- retentativa real: executada uma vez;
- resultado da ativacao: `failure`;
- categoria final: `nm_activation_failed_generic`;
- rollback: tentado e efetivo para remover o perfil dedicado;
- servico final: `active/enabled`;
- `NRestarts`: `0`;
- playback final: `playing`;
- player/MPV ativos ao final, renderer/setup ausentes;
- SSH permaneceu acessivel;
- secrets-file final ausente.

Uma retentativa adicional com outra rede WPA/WPA2 simples tambem retornou
`failure` com categoria publica `nm_activation_failed_generic`; rollback foi
efetivo, perfil dedicado ficou ausente, servico voltou `active/enabled`,
`NRestarts=0` e playback `playing`.

Uma correcao estreita posterior tornou o apply efetivo: o adapter passou a
verificar o perfil dedicado por `connection.id` e a manter a origem do perfil
durante a ativacao. A nova retentativa controlada retornou:

- resultado da ativacao: `success`;
- categoria final: `none`;
- rollback-after-test: efetivo;
- perfil dedicado final: ausente;
- servico final: `active/enabled`;
- `NRestarts`: `0`;
- playback final: `playing`;
- player/MPV ativos ao final, renderer/setup ausentes;
- SSH permaneceu acessivel;
- secrets-file final ausente.

## Dados Publicos Permitidos

- NetworkManager/nmcli disponivel;
- Wi-Fi device presente;
- ativacao tentada;
- resultado de ativacao;
- categoria publica da falha;
- rollback status;
- perfil dedicado presente/ausente;
- secrets-file removido;
- network_changed.

## Fora de Escopo

- C9.7;
- integracao ao wizard;
- hotspot ou portal;
- writer/config real;
- alteracao do `kiosky-player`;
- loop de retentativas.

## Proximo Passo

C9.7 pode integrar o resultado controlado ao Setup Produto Local V0, ainda sem
hotspot/portal e sem writer/config real.
