# C11.0 - Read-only Readiness Audit

Data: 2026-05-06

Status: auditoria read-only concluida na placa dev. Root read-only ainda nao
deve ser habilitado.

## Objetivo

Auditar se o appliance esta pronto para root read-only/overlay sem habilitar
read-only, sem corte seco, sem poweroff, sem writer, sem alteracao de config
real, sem Wi-Fi/NetworkManager e sem pacotes.

## Resultado

Conclusao:

- `root_read_only_ready=false`;
- `ready_for_read_only_enablement=false`;
- `ready_for_c11_1_policy=true`.

O appliance operacional esta saudavel na dev:

- `public_state=player_running`;
- playback `playing`;
- servicos principais `active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`.

## Paths Gravaveis Esperados

Compatíveis com root read-only se mantidos fora da raiz imutavel:

- `/data/config`: config real e backups controlados;
- `/data/media/kiosky-player`: midia/cache do player;
- `/data/state/kiosky-player`: estado do player/launcher;
- `/data/state/totem-display`: `orientation.json` publico seguro;
- `/data/state/totem-settings`: contexto privado de configuracao;
- `/data/state/totem-boot-visual`: rollback state dos guardrails visuais;
- `/data/state/totem-appliance`: manifest/estado instalado;
- `/data/logs/kiosky-player`: logs do player, se persistidos;
- `/tmp/kiosky`: runtime IPC/socket;
- `/tmp/dadooh-status`: status publico temporario;
- `/run/dadooh-settings`: request/lock do gatilho F10.

## Blockers

### NetworkManager

Classificacao: `NEEDS_NETWORKMANAGER_POLICY`.

Perfis Wi-Fi ficam em:

```text
/etc/NetworkManager/system-connections
```

O perfil dedicado do produto existe, mas troca/aplicacao de Wi-Fi ainda exige
politica antes de root read-only:

- excecao controlada para escrita em `/etc/NetworkManager`;
- ou janela temporaria root-writable durante manutencao;
- ou fluxo futuro dedicado de configuracao de rede.

Nenhum perfil foi alterado nesta auditoria.

### Logs / journald

Classificacao: `NEEDS_LOG_POLICY`.

`/var/log/journal` esta presente e journald esta em configuracao default. Antes
de root read-only, C11.1 deve decidir:

- journald volatil;
- journald persistente em caminho apropriado;
- ou politica de logs em `/data`.

Nenhum log bruto foi coletado ou apagado.

### `/var` e `/etc`

Classificacoes relevantes:

- `/var/lib/systemd`: `NEEDS_VAR_POLICY`;
- `/var/lib/NetworkManager`: `NEEDS_VAR_POLICY`;
- `/etc/systemd/system`: `NEEDS_ETC_EXCEPTION`;
- `/boot/armbianEnv.txt`: `NEEDS_ETC_EXCEPTION`.

Esses itens nao sao falhas imediatas, mas precisam de politica antes do
enablement.

## Installer / Manifest

O instalador ja prepara a maior parte dos paths mutaveis em `/data`, `/tmp` e
`/run`. O manifest deve registrar que:

- `root_read_only_ready=false`;
- `ready_for_read_only_enablement=false`;
- blockers atuais: NetworkManager e journald/log policy;
- C11.1 pode iniciar para resolver politicas, ainda sem habilitar read-only.

## Nao Alterado

- read-only nao habilitado;
- poweroff nao executado;
- corte seco nao executado;
- writer nao chamado;
- config real nao lida/escrita;
- Wi-Fi/NetworkManager nao alterados;
- `kiosky-player` nao alterado;
- pacotes nao instalados.

## Proximo Passo

C11.1 deve ser uma rodada de politica/mitigacao:

- decidir NetworkManager em root read-only;
- decidir journald/logs;
- mapear excecoes `/var`, `/etc` e `/boot`;
- definir o plano de enablement reversivel.

Ainda nao habilitar root read-only nem executar corte seco.
