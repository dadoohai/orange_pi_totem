# Status Atual

Data: 2026-04-29

## Resumo executivo

O Candidato A avancou alem da validacao inicial da imagem base. A placa passou por boot inicial, reboots curtos, rede cabeada/NetworkManager, stress leve CPU/RAM de 30 minutos, layout `/data`, Wi-Fi cliente 5 GHz e desativacao dos servicos Bluetooth conhecidos sem regressao observada. O Wi-Fi cliente 5 GHz permaneceu funcional apos as desativacoes de Bluetooth/AW859A. Tambem foi feita a preparacao inicial de usuario/diretorios para o `kiosky-player`, a instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, a garantia de `/tmp/kiosky`, a aprovacao do `check_app_prereqs.sh` e o primeiro teste manual de MPV via DRM/KMS com confirmacao visual HDMI.

Ainda nao ha homologacao para producao. A proxima etapa deve focar no teste manual controlado do player/app, mantendo DRM/KMS como caminho principal, ainda sem iniciar `kiosk.py` por systemd ou habilitar systemd da aplicacao.

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
- Instalacao controlada do runtime minimo `mpv`, `ffmpeg` e `python3-requests`, sem upgrades/removes e sem tocar em kernel/Armbian.
- `/tmp/kiosky` criado como `totem:totem`, modo `0750`.
- `check_app_prereqs.sh` aprovado apos o runtime minimo e a garantia de `/tmp/kiosky`.
- MPV manual aprovado via DRM/KMS direto, com `vo=drm` e `vo=gpu --gpu-context=drm` funcionando como root e como usuario `totem`, e com confirmacao visual HDMI.

## O que foi alterado na placa

- Criado layout persistente em `/data`.
- Criado usuario/grupo `totem`.
- Criados diretorios de aplicacao em `/opt/totem`, `/data/.../kiosky-player` e `/tmp/kiosky`.
- Ajustado ownership de diretorios mutaveis para `totem:totem` onde previsto.
- Usuario `totem` adicionado aos grupos existentes `audio`, `video` e `render`.
- Instalados pacotes de runtime `mpv`, `ffmpeg` e `python3-requests` com `--no-upgrade --no-install-recommends`.
- Criado `/tmp/kiosky` como `totem:totem`, modo `0750`.
- `bluetooth.service` foi desabilitado.
- `aw859a-bluetooth.service` foi desabilitado e o estado falhado foi limpo.

Nenhum deploy do app foi executado, `kiosk.py` nao foi iniciado e nenhum servico systemd da aplicacao foi ativado. Apenas o teste manual de MPV foi executado.

## O que ainda esta pendente

- `pip` ausente por decisao desta fase.
- `/opt/totem/venv` ainda sem `bin/python` e `bin/pip` executaveis, esperado enquanto `python3-pip`/venv ficam fora.
- `python3-pip` e `python3-venv` continuam fora desta fase.
- Xorg, Wayland, compositor e Chromium continuam fora desta fase; nao ha indicacao atual para instala-los apos o teste MPV via DRM/KMS.
- Deploy do app ainda nao executado.
- Configuracao privada ainda nao aplicada.
- Teste manual do player ainda nao executado.
- Unit systemd da aplicacao ainda nao instalada/habilitada na placa.
- Root read-only ainda nao validado.
- Corte seco ainda nao validado.

## Proximos 3 passos tecnicos

1. Preparar o deploy manual supervisionado do `kiosky-player`, preservando config privada fora do Git.
2. Fazer teste manual controlado do player/app usando DRM/KMS como caminho principal, ainda sem habilitar systemd.
3. Planejar a garantia definitiva de `/tmp/kiosky`, preferencialmente com `RuntimeDirectory` na unit systemd futura, antes de qualquer enable/start do servico.

## Regras que continuam proibidas

Nao executar na placa:

- `apt upgrade`
- `apt full-upgrade`
- `apt dist-upgrade`
- `armbian-upgrade`

## Artefatos brutos

Os artefatos brutos `.tar.gz` permanecem fora do Git. Eles podem existir localmente como arquivos ignorados para auditoria, mas nao devem ser adicionados ao repositorio.
