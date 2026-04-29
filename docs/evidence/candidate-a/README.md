# Evidencias - Candidato A

Status: em validacao. O Candidato A ainda nao esta homologado para producao.

## Composicao da imagem

| Item | Valor |
| --- | --- |
| Build | Armbian Build v25.11 |
| Release | Debian Bookworm Minimal |
| Board | Orange Pi Zero 3 |
| Kernel | `6.12.58-current-sunxi64` |
| U-Boot | `2025.04` |
| BSP freeze | `BSPFREEZE=yes` |
| Rede | NetworkManager |
| Desktop | ausente |

## Regra operacional

Nao executar atualizacao ampla em campo. Kernel, DTB, U-Boot e BSP permanecem congelados; qualquer mudanca de sistema operacional deve gerar nova imagem e nova homologacao.

## Evidencias ja registradas

| Teste | Data | Resultado | Evidencia |
| --- | --- | --- | --- |
| Boot inicial | 2026-04-28 | Aprovado | [Testes iniciais](../../03_TESTES_INICIAIS_E_EVIDENCIAS.md) |
| Reboots curtos | 2026-04-28 | Aprovado | [Testes iniciais](../../03_TESTES_INICIAIS_E_EVIDENCIAS.md) |
| Baseline de rede cabeada/NetworkManager | 2026-04-28 | Aprovado | [network-before-stress.txt](../../EVIDENCIAS/2026-04-28/network-before-stress.txt) |
| Stress leve CPU/RAM 30 min | 2026-04-28 | Aprovado | [stress-30m.txt](../../EVIDENCIAS/2026-04-28/stress-30m.txt) |

## Coletas padronizadas

Os scripts de bancada ficam em `scripts/board/` e gravam artefatos em `/root/totem-diag/` na placa.

| Script | Saida esperada |
| --- | --- |
| `collect_diag.sh` | diretorio `/root/totem-diag/<timestamp>/` e arquivo `/root/totem-diag/totem-diag-<timestamp>.tar.gz` |
| `network_snapshot.sh` | diretorio `/root/totem-diag/network-<timestamp>/` e arquivo `/root/totem-diag/network-snapshot-<timestamp>.tar.gz` |
| `stress_light_30m.sh` | diretorio `/root/totem-diag/stress-light-30m-<timestamp>/` e arquivo `/root/totem-diag/stress-light-30m-<timestamp>.tar.gz` |
| `disable_bluetooth.sh` | diretorio `/root/totem-diag/bluetooth-disable-<timestamp>/` e arquivo `/root/totem-diag/bluetooth-disable-<timestamp>.tar.gz` |

## Template de registro

### Identificacao

- Data:
- Operador:
- Placa:
- Fonte:
- Cartao microSD:
- Imagem:
- Hash da imagem:
- Observacoes de bancada:

### Comandos executados

```bash
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/collect_diag.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/network_snapshot.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/stress_light_30m.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/setup_data_layout.sh
./scripts/remote/push_and_run.sh root@orangepizero3 scripts/board/disable_bluetooth.sh
```

### Artefatos coletados

| Artefato | Origem na placa | Destino no repositorio | Observacoes |
| --- | --- | --- | --- |
|  | `/root/totem-diag/` | `docs/evidence/candidate-a/` |  |

### Resultado

- Resultado geral:
- Falhas observadas:
- Reboots realizados:
- Temperatura observada:
- Rede cabeada:
- Wi-Fi:
- Bluetooth:
- Kernel tainted:
- Servicos falhados:

### Criterios para prosseguir

- Sem `kernel panic`.
- Sem `Internal error: Oops`.
- Sem erro EXT4.
- Sem reset ou timeout recorrente de MMC.
- Sem servico falhado relevante em `systemctl --failed`.
- Pacotes criticos Armbian permanecem em hold.
- NetworkManager mantem conectividade esperada.

### Pendencias

- Validar Wi-Fi de campo.
- Validar hotspot, se entrar no escopo.
- Validar aplicacao do totem.
- Validar layout `/data`.
- Validar politica de logs.
- Validar comportamento com cortes de energia em bancada controlada.
