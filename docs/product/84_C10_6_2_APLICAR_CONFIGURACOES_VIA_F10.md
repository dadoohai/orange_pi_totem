# C10.6.2 - Aplicar Configuracoes via F10

Data: 2026-05-05

## Objetivo

Fechar o caminho de produto em que o operador abre Configuracoes pelo gatilho
persistente `F10`, conclui o wizard visual e aplica a configuracao no totem.

## O que mudou

O `totem-open-settings.service` continua abrindo o wizard visual existente, mas
agora a sessao aceita uma politica temporaria restrita em
`/run/dadooh-settings/apply-policy.json`.

Sem politica, o comportamento segue seguro: o wizard gera candidata ou permite
cancelar, sem writer real. Com politica autorizada pelo runner:

- `dry-run` le valores privados aprovados da config ativa, monta candidata
  privada e roda C5.1 `real-dry-run`, sem escrever `/data/config`;
- `real-write` faz handoff privado, roda writer real, cria backup, atualiza
  `/data/config/config.json`, atualiza `orientation.json` publico seguro e
  reinicia o player.

A politica e one-shot: depois de consumida pela sessao, ela e removida de
`/run/dadooh-settings`.

## Orientacao

Ao salvar, `rotation_deg` segue este contrato:

- entra na candidata visual;
- passa pelo handoff privado;
- chega a config real;
- atualiza `/data/state/totem-display/orientation.json`;
- e usado por splash/transicoes via contrato publico;
- e carregado pelo player apos reinicio do servico.

`orientation.json` contem somente campos allowlisted:

- `schema_version`;
- `updated_at`;
- `rotation_deg`;
- `orientation_label`.

## Validacao

Executado em bancada:

- `--prepare-only`;
- `--diagnose-current-flow`;
- `--run-f10-cancel`;
- `--run-f10-apply-dry-run`;
- `--run-f10-apply-real`;
- `--verify-orientation-propagation`.

Resultado da escrita real:

- writer chamado;
- config real escrita;
- backup criado;
- `rotation_deg` esperado corresponde a config ativa;
- `orientation.json` atualizado e correspondente;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player/MPV ativos;
- renderer/setup ausentes;
- Wi-Fi/NetworkManager nao alterados.
- politica temporaria removida ao final.

## Fora do escopo

- PIN/senha local;
- Suporte Local V0;
- hotspot/portal;
- read-only;
- corte seco;
- alteracao do repo `kiosky-player`;
- publicacao de config, valores privados, ambiente, SSID, senha, IP, MAC ou logs
  brutos.

## Observacao humana

A verificacao automatica confirma propagacao para config, `orientation.json` e
splash. A observacao humana no HDMI confirmou que as midias ficaram corretas na
orientacao escolhida e que nao houve flash de shell/login no fluxo
F10 -> wizard -> salvar -> player.

## Proximo passo

Seguir para C10.7 - auditoria de reprodutibilidade placa -> repo para preparar
imagem.
