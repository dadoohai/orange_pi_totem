# C11.2 - Read-only Mitigation Apply

Data: 2026-05-06

Status: mitigacoes reversiveis aplicadas e validadas na placa dev. Root
read-only ainda nao foi habilitado.

## Objetivo

Aplicar a primeira camada pratica da politica C11.1, somente na dev, preparando
o caminho para root read-only sem corte seco, sem placa teste, sem writer, sem
config real e sem alteracao de Wi-Fi/NetworkManager.

## Aplicado

### Journald

Foi criado um drop-in reversivel para journald volatil:

```text
/etc/systemd/journald.conf.d/90-dadooh-volatile.conf
```

Politica efetiva:

- `Storage=volatile`;
- limite de runtime controlado;
- logs brutos do sistema nao persistem por padrao na imagem de produto;
- evidencia continua sem logs brutos.

Foi criado backup/rollback sob:

```text
/data/state/totem-read-only-mitigation
```

### NetworkManager

Nenhum perfil foi movido ou alterado. A mitigacao C11.2 registra a politica
operacional:

- perfis continuam em `/etc/NetworkManager/system-connections`;
- troca de Wi-Fi exige janela controlada de manutencao/configuracao;
- perfis nao pertencentes ao produto devem ser preservados;
- nomes de perfil, SSID e credenciais nao entram em evidencia.

### `/var`

Nenhum bind/overlay global foi habilitado. A politica registrada e:

- estado de runtime de systemd/NetworkManager fica para validacao em C11.3;
- estado de produto continua em `/data`;
- runtime temporario continua em `/tmp` e `/run`.

### `/boot` e `/etc`

Nenhum boot arg novo foi aplicado. A politica registrada e:

- `/boot` e `/etc` sao imutaveis durante runtime normal;
- alteracoes ocorrem apenas por instalador/manutencao com backup e rollback.

## Validação

Rodado na dev:

- `--prepare-only`;
- `--inspect`;
- `--dry-run`;
- `--apply-dev`;
- `--verify`;
- `--reboot-check`.

Resultado pos-reboot:

- `journald_storage_effective=volatile`;
- `rollback_state_present=true`;
- `ready_for_c11_3_enablement=true`;
- `public_state=player_running`;
- playback `playing`;
- servicos principais `active/enabled`;
- `NRestarts=0`;
- `systemctl_failed_count=0`.

## Nao Alterado

- root read-only nao habilitado;
- corte seco nao executado;
- poweroff nao executado;
- placa teste nao tocada;
- config real nao lida/escrita;
- writer nao chamado;
- Wi-Fi e perfis NetworkManager nao alterados;
- `kiosky-player` nao alterado;
- pacotes nao instalados.

## Rollback

O runner C11.2 possui `--rollback`, que remove os estados C11.2 e restaura ou
remove o drop-in do journald conforme o estado anterior registrado.

Rollback deve ser usado antes de qualquer investigacao destrutiva se a politica
volatil de journald causar regressao operacional.

## Risco Residual

`root_read_only_ready=false` e `ready_for_read_only_enablement=false` continuam
corretos. C11.2 preparou mitigacoes, mas ainda nao habilitou overlay/root
read-only nem testou corte seco.

Riscos que ficam para C11.3:

- validar comportamento de `/var` com overlay/tmpfs;
- validar janela controlada para NetworkManager em root read-only;
- validar rollback antes de teste de corte seco.

## Proximo Passo

C11.3 pode iniciar como enablement controlado de root read-only/overlay na dev,
com rollback e sem placa teste ate a dev passar.

## Follow-up C11.3

C11.3 inspecionou o mecanismo oficial do Armbian e encontrou
`module_overlayfs`, mas `overlayroot`/`overlayroot-chroot` nao estao presentes.
Como a rodada C11.3 proibe instalacao de pacotes, o enablement foi bloqueado
com seguranca:

- `enable_executed=false`;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `ready_for_c11_4=false`.

As mitigacoes C11.2 continuam validas e aplicadas; o proximo corte deve decidir
como aprovisionar o mecanismo read-only oficial ou levar isso para a imagem
base.

C11.3.1 decidiu e instalou o prerequisito na dev, sem habilitar read-only: o
mecanismo oficial do Armbian requer o pacote `overlayroot`. O dry-run de
instalacao foi seguro e sem upgrades/remocoes; a imagem base C12 deve incluir o
mesmo pacote.
