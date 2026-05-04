# C10.1 - Reboot/Autoboot com Config Real

Status: implementado e validado em bancada com confirmacao humana explicita.

Data: 2026-05-04

## Objetivo

Validar que o appliance reinicia de forma controlada e volta sozinho para
`player_running` com Wi-Fi persistente e config real ja escrita pelo fluxo
C10.0.

## Implementado

- `scripts/remote/run_c10_1_reboot_autoboot_config_real.sh`;
- modos `--prepare-only`, `--preflight` e `--reboot-autoboot`;
- snapshot sanitizado antes e depois do reboot;
- espera pelo retorno do SSH sem depender de autenticacao por chave;
- validacao de servico, status publico, playback, processos, config real por
  metadados, perfil Wi-Fi dedicado e filtros criticos agregados;
- bloco de readiness read-only apenas observacional.

## Validado

- `--prepare-only` passou;
- `--preflight` passou sem ler/escrever config real;
- `--reboot-autoboot` executou um reboot controlado com a frase
  `CONFIRMO REBOOT CONTROLADO C10.1`;
- SSH voltou em 46 segundos;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player/MPV ativos;
- renderer/setup ausentes;
- perfil Wi-Fi dedicado presente;
- config real presente com `root:totem` `0640`;
- usuario `totem` le e nao escreve;
- `systemctl --failed` sem falhas;
- filtro critico de kernel sem ocorrencias.

## Guardrails

- config real nao foi lida nem escrita;
- writer nao foi chamado;
- Wi-Fi e NetworkManager nao foram alterados;
- hotspot/portal nao foram criados;
- repo `kiosky-player` nao foi alterado;
- root read-only nao foi habilitado;
- corte seco nao foi executado;
- logs brutos, config, backup e identificadores privados nao foram publicados.

## Observacao C10.0

O retorno bruto `wizard_rc=8` do wrapper `openvt` observado em C10.0 fica
classificado como retorno de wrapper nao bloqueante para boot/autoboot: a
candidata foi gerada, handoff/writer passaram e C10.1 reiniciou com estado
operacional correto. A limpeza desse codigo de retorno pode ficar para
hardening futuro, sem bloquear C10.1.

## Read-only Readiness

`read_only_not_enabled=true` e `power_cut_not_tested=true`.

Pendencias antes de corte seco/root read-only:

- politica de NetworkManager e perfil Wi-Fi em root read-only;
- politica de logs/journald;
- auditoria de `/var/lib` e `/etc`;
- validacao de corte seco continua bloqueada;
- cache/config em `/data` e runtime em `/tmp` estao nos caminhos esperados.

## Proximo Passo

C10.2 deve validar o fluxo `config_missing` real controlado: simular ausencia
de config de forma segura, subir wizard visual, escrever config real pelo
writer e iniciar o player.
