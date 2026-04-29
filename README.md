# Orange Pi Totem

Documentação técnica e operacional para construção, validação e evolução de uma imagem Armbian customizada para totens baseados em Orange Pi Zero 3.

## Estado atual

**Candidato A**: Armbian Build v25.11 + Debian Bookworm Minimal + kernel `6.12.58-current-sunxi64` + U-Boot `2025.04`.

Status: aprovado em boot inicial, reboots curtos, baseline de rede cabeada/NetworkManager e stress leve CPU/RAM de 30 minutos. Ainda não homologado para produção.

## Documentos principais

- [Índice e plano estratégico](docs/00_INDICE_E_PLANO_ESTRATEGICO.md)
- [Decisão técnica e justificativa](docs/01_DECISAO_TECNICA_E_JUSTIFICATIVA.md)
- [Geração da imagem base](docs/02_GERACAO_DA_IMAGEM_BASE.md)
- [Testes iniciais e evidências](docs/03_TESTES_INICIAIS_E_EVIDENCIAS.md)
- [Roadmap de produto, testes, atualização e monitoramento](docs/04_ROADMAP_PRODUTO_TESTES_ATUALIZACAO_MONITORAMENTO.md)
- [Política de atualização](docs/05_POLITICA_DE_ATUALIZACAO.md)
- [Template de evidências do Candidato A](docs/evidence/candidate-a/README.md)
- [Documentação consolidada](docs/DOCUMENTACAO_COMPLETA_TOTEM_ORANGEPI_ZERO3.md)

## Scripts de bancada

- `scripts/board/`: scripts para coleta de diagnóstico, snapshot de rede, stress leve, criação idempotente do layout `/data` (`config`, `media/kiosky-player`, `state/kiosky-player`, `spool/kiosky-player`, `logs/kiosky-player`) e desativação idempotente de Bluetooth.
- `scripts/remote/push_and_run.sh`: wrapper local para copiar um script de `scripts/board/` para a placa e executá-lo via SSH quando essa etapa for liberada.

## Regra operacional crítica

Não rodar `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade` em campo. A base foi validada com kernel/DTB/U-Boot/BSP congelados. Atualizações devem seguir fluxo controlado por release.
