# C10.5 - Visual Boot/Shutdown + Rotation UX

Status: validacao parcial em bancada.

Data: 2026-05-05

Atualizacao C10.5.1: a rotacao fisica de bitmap continua removida. A rodada
seguinte implementa o contrato correto: navegacao por setas, confirmacao por
lista, canvas nativo `1280x720`/`720x1280`, renderer de framebuffer com
mapeamento proporcional de texto e splash aceitando `--rotation-deg`. Ver
`docs/product/79_C10_5_1_ORIENTATION_UX_CONTRACT.md`.

Validacao C10.5.1: os fluxos remotos `--preview-orientation-flow`,
`--run-complete-portrait`, `--run-complete-landscape` e
`--preview-splash-orientations` passaram em bancada com HDMI/teclado. O estado
final voltou para `active/enabled`, `NRestarts=0`, `public_state=player_running`
e playback `playing`.

Atualizacao C10.5.2: o contrato de orientacao passa a ter caminho publico
allowlisted em `/data/state/totem-display/orientation.json`, usado por splash e
transicoes quando nenhum `--rotation-deg` explicito e informado. O runner
`run_c10_5_2_visual_guard_boot_shutdown.sh` adiciona inspecao sanitizada,
preview de splash de transicao, stress curto, aplicacao/rollback de guardrails
persistentes e reboot visual controlado. Ver
`docs/product/80_C10_5_2_VISUAL_GUARD_BOOT_SHUTDOWN.md`.

## Objetivo

Fechar a superficie visual antes de read-only: reduzir texto tecnico visivel no
boot/transicoes, adicionar splash basico de produto e tornar a orientacao uma
etapa visual com preview, confirmacao e cancelamento.

## Implementado

- wizard visual com preview da orientacao antes da confirmacao;
- tela de confirmacao da orientacao com possibilidade de voltar;
- layout compacto sinalizando paisagem/retrato, sem aplicar rotacao fisica do
  framebuffer;
- candidato continua registrando `rotation_deg`;
- splash simples de framebuffer em `scripts/board/totem_visual_splash.py`;
- runner `scripts/remote/run_c10_5_visual_boot_rotation.sh` com modos de
  preview, guardrails reversiveis e reboot visual controlado.

## Validado em HDMI

- texto tecnico de login/getty deixou de disputar a UI quando o runner pausa
  temporariamente o getty da TTY de produto;
- comandos voltaram a responder com uma unica tecla;
- transicoes passaram a exibir splash Dadooh limpo em vez de texto tecnico;
- o player foi restaurado ao final dos testes, com `active/enabled`,
  `NRestarts=0`, `public_state=player_running` e playback `playing`.

A tentativa de rotacionar a UI inteira diretamente no renderizador de
framebuffer foi rejeitada: a tela girava, mas textos ficavam distorcidos. C10.5
mantem preview, confirmacao e `rotation_deg`; a rotacao visual completa do
wizard deve usar uma camada propria de renderizacao em rodada futura.

## Boot e Shutdown

O runner aplica guardrails somente com confirmacao humana explicita. A alteracao
e reversivel e pode:

- manter argumentos silenciosos de boot em `/boot/armbianEnv.txt`, com backup;
- desabilitar gettys visiveis do produto, preservando estado anterior;
- instalar um servico systemd de splash Dadooh antes do player;
- desenhar mensagens publicas como `Inicializando`, `Preparando`,
  `Iniciando player`, `Abrindo configuracao` e `Encerrando`.

Rollback restaura backup de boot, estado dos gettys e remove/restaura o servico
de splash conforme o estado salvo.

## Guardrails

- sem desktop, Chromium, Xorg, Wayland ou compositor;
- sem writer por padrao;
- sem leitura/escrita de config real;
- sem alteracao de Wi-Fi/NetworkManager;
- sem hotspot/portal/backend/login;
- sem root read-only;
- sem corte seco;
- sem publicar SSID, senha, IP, MAC, DNS, gateway, api_key, api_url real,
  environment_id real, config, backup ou logs brutos.

## Validacao

Comandos previstos:

```bash
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --prepare-only
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --preview-wizard
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --preview-orientation-flow
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --apply-boot-visual-guardrails
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --reboot-visual-check
```

Se o wizard novo for materialmente alterado em bancada, rodar tambem:

```bash
scripts/remote/run_c10_5_visual_boot_rotation.sh <board-host> --run-complete-existing-wifi
```

## Pendencias

- aplicar guardrails persistentes de boot/getty/splash somente com confirmacao
  humana explicita;
- validar reboot visual controlado com humano observando a tela, se os
  guardrails forem aplicados;
- substituir o splash estatico por loading/animacao de produto em rodada futura;
- evoluir a qualidade visual fina da orientacao/splash em rodada futura;
- manter root read-only e corte seco para rodadas futuras.

## Proximo Passo

C10.6 deve revalidar rapidamente o fluxo integrado com a superficie visual nova
se C10.5 for aceito em bancada. Depois, C11.0 segue como auditoria de
read-only readiness.
