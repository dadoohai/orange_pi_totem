# Rodada 20260429-012638 - Layout /data

Status: aprovado para a criacao inicial do layout `/data`. O Candidato A ainda nao esta homologado para producao.

## Objetivo

Criar a estrutura inicial de diretorios persistentes em `/data` e coletar diagnostico imediatamente depois para registrar a evidencia de auditoria.

## Scripts executados

- `scripts/board/setup_data_layout.sh`
- `scripts/board/collect_diag.sh`
- `scripts/remote/pull_artifacts.sh`

## Resultado antes/depois

Antes da execucao:

```text
/data does not exist
```

Depois da execucao:

```text
drwxr-xr-x root root /data
drwxr-xr-x root root /data/config
drwxr-xr-x root root /data/logs
drwxr-xr-x root root /data/media
drwxr-xr-x root root /data/spool
```

Confirmacao pela coleta posterior em `data-layout.txt`:

```text
drwxr-xr-x root root /data
drwxr-xr-x root root /data/config
drwxr-xr-x root root /data/logs
drwxr-xr-x root root /data/media
drwxr-xr-x root root /data/spool
```

## Diagnostico pos-layout

- `systemctl --failed`: `0 loaded units listed`.
- Kernel tainted: `1024`, observado e esperado nesta fase de validacao da base.
- Filtro critico do kernel: sem Oops, panic, erro EXT4, journal abortado, remount read-only ou timeout/reset de MMC.
- O filtro amplo continua registrando mensagens de boot `Error applying setting, reverse things back` associadas a UART/SPI/MMC, sem impacto critico observado nesta rodada.

## Artefatos brutos

Arquivos `.tar.gz` copiados para este diretorio sao artefatos locais de auditoria e nao devem ser commitados no repositorio publico. Eles podem conter IPs, hostnames, IPv6 completo, UUIDs do NetworkManager, nomes de conexao e SSIDs.

Arquivos presentes nesta rodada local:

- `totem-diag-20260429-012629-0300.tar.gz`
- artefatos anteriores existentes em `/root/totem-diag/` tambem podem ter sido copiados pelo `pull_artifacts.sh`, porque o script nao apaga nem filtra arquivos remotos.

## Resultado

Aprovado. O layout `/data` foi criado de forma idempotente e a coleta posterior confirmou os diretorios esperados sem servicos falhados ou eventos criticos novos no kernel.
