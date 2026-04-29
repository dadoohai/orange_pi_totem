# Status Atual

Data: 2026-04-29

## Resumo executivo

O Candidato A avançou alem da validacao inicial da imagem base. A placa passou por boot inicial, reboots curtos, rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, layout `/data`, Wi-Fi cliente 5 GHz e desativacao dos servicos Bluetooth conhecidos sem regressao observada. O Wi-Fi cliente 5 GHz permaneceu funcional apos as desativacoes de Bluetooth/AW859A. Tambem foi feita a preparacao inicial de usuario e diretorios para o `kiosky-player`.

Ainda nao ha homologacao para producao. A proxima etapa deve focar em display/runtime e planejamento de `mpv`, `pip` e venv antes de iniciar o player ou habilitar systemd da aplicacao.

## Composicao do Candidato A

- Armbian Build v25.11.
- Debian Bookworm Minimal.
- Orange Pi Zero 3.
- Kernel `6.12.58-current-sunxi64`.
- U-Boot `2025.04`.
- BSP congelado com `BSPFREEZE=yes`.
- Rede gerenciada por NetworkManager.
- Desktop ausente.

## O que foi aprovado

- Boot inicial.
- Reboots curtos.
- Baseline de rede cabeada/NetworkManager.
- Stress leve CPU/RAM de 30 minutos.
- Criacao idempotente do layout `/data`.
- Wi-Fi cliente 5 GHz com conexao NetworkManager existente, mantido funcional apos desabilitar Bluetooth/AW859A.
- Desativacao de `bluetooth.service` sem regressao observada.
- Desativacao de `aw859a-bluetooth.service` com `systemctl --failed` voltando para `0 loaded units listed`.
- Criacao de usuario/grupo `totem` e diretorios iniciais para a aplicacao.

## O que foi alterado na placa

- Criado layout persistente em `/data`.
- Criado usuario/grupo `totem`.
- Criados diretorios de aplicacao em `/opt/totem`, `/data/.../kiosky-player` e `/tmp/kiosky`.
- Ajustado ownership de diretorios mutaveis para `totem:totem` onde previsto.
- `bluetooth.service` foi desabilitado.
- `aw859a-bluetooth.service` foi desabilitado e o estado falhado foi limpo.

Nenhum deploy do app foi executado, `kiosk.py` nao foi iniciado, MPV nao foi iniciado e nenhum servico systemd da aplicacao foi ativado.

## O que ainda esta pendente

- `mpv` ausente.
- `pip` ausente.
- `/opt/totem/venv` ainda sem `bin/python` e `bin/pip` executaveis.
- Stack de display/runtime ainda nao validada.
- Deploy do app ainda nao executado.
- Configuracao privada ainda nao aplicada.
- Teste manual do player ainda nao executado.
- Unit systemd da aplicacao ainda nao instalada/habilitada na placa.
- Root read-only ainda nao validado.
- Corte seco ainda nao validado.

## Proximos 3 passos tecnicos

1. Fazer probe controlado de display/runtime para decidir como o MPV sera executado.
2. Planejar a entrega de `mpv`, `pip` e venv sem `apt` na placa, preferencialmente via imagem ou pacote controlado.
3. Preparar roteiro de deploy manual supervisionado do `kiosky-player`, com config privada fora do Git e sem habilitar systemd antes do teste manual.

## Regras que continuam proibidas

Nao executar na placa:

- `apt upgrade`
- `apt full-upgrade`
- `apt dist-upgrade`
- `armbian-upgrade`

## Artefatos brutos

Os artefatos brutos `.tar.gz` permanecem fora do Git. Eles podem existir localmente como arquivos ignorados para auditoria, mas nao devem ser adicionados ao repositorio.
