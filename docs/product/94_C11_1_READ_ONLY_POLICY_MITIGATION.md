# C11.1 - Read-only Policy & Mitigation

Data: 2026-05-06

Status: politica definida e probe read-only concluido na placa dev. Root
read-only ainda nao foi habilitado.

## Objetivo

Transformar os blockers do C11.0 em politica concreta para C11.2, sem alterar
a placa, sem remount, sem writer, sem config real, sem Wi-Fi/NetworkManager e
sem logs brutos.

## Politica

A raiz do sistema deve ficar imutavel somente depois de C11.2. Durante runtime
normal:

- persistente fica em `/data`;
- temporario fica em `/tmp` ou `/run`;
- codigo em `/opt/totem` nao recebe escrita;
- `/etc`, `/boot` e perfis NetworkManager so mudam em janela explicita de
  manutencao/instalador com backup e rollback;
- logs brutos do sistema nao entram em evidencia.

O manifest versionado da politica ficou em:

```text
scripts/board/totem_read_only_policy.json
```

## Paths

Persistentes permitidos:

- `/data/config`;
- `/data/state`;
- `/data/media`;
- `/data/logs`.

Runtime permitido:

- `/tmp`;
- `/run`.

Escrita proibida em runtime normal:

- `/opt/totem`;
- `/opt/totem/kiosky-player`;
- raiz generica fora das excecoes controladas.

## NetworkManager

Politica escolhida: manter perfis no caminho nativo do NetworkManager:

```text
/etc/NetworkManager/system-connections
```

Nao mover para `/data` nesta fase. A troca de Wi-Fi deve ocorrer em uma janela
controlada de manutencao/configuracao, que permita escrita no root apenas no
passo de apply do NetworkManager, preserve perfis nao pertencentes ao produto e
retorne para read-only ao final.

C11.2 deve validar essa janela com rollback e sem publicar nomes de perfil,
SSID, senha, IP, MAC, DNS ou gateway.

## Journald / Logs

Politica escolhida: journald volatil na imagem de produto. Logs de produto e
diagnosticos sanitizados devem ficar em `/data/logs` ou `/data/state`.

C11.2 deve aplicar uma configuracao reversivel para journald volatil e limites
de uso. C11.1 nao apagou logs existentes e nao coletou logs brutos.

## `/boot`, `/etc` e `/var`

- `/boot`: imutavel em runtime; alteracao so por guardrail/instalador com
  backup e rollback.
- `/etc`: imutavel em runtime; units e arquivos do appliance mudam apenas por
  instalador/manutencao controlada.
- `/var/lib/systemd`: estado de sistema volatil/overlay a validar.
- `/var/lib/NetworkManager`: estado runtime volatil/overlay a validar; perfis
  persistentes continuam no caminho nativo do NetworkManager.

## Resultado Dev

Probe executado apenas na placa dev:

- `root_read_only_ready=false`;
- `ready_for_read_only_enablement=false`;
- `ready_for_c11_2_enablement=true`;
- `blockers_remaining_count=0` para a politica;
- `public_state=player_running`;
- playback `playing`;
- servicos principais `active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`.

Nada operacional foi alterado.

## Proximo Passo

C11.2 pode iniciar para aplicar mitigacoes reversiveis:

- journald volatil;
- politica de `/var`;
- janela controlada para NetworkManager;
- verificacao de rollback.

Ainda nao habilitar root read-only, nao fazer corte seco e nao gerar imagem
final.
