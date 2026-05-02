# C2 - preview visual e evidencia

Status: preview local estatico. Nao implementa mudancas operacionais.

Data: 2026-05-02

## Objetivo

Este documento registra a primeira implementacao de preview visual C2 para o
onboarding minimo definido em C1. O objetivo e revisar UX, sequencia de telas,
textos publicos e estados planejados sem tocar em rede, config real, player,
launcher operacional ou placa.

O preview e mock. Ele nao configura Wi-Fi, nao testa conectividade real, nao
salva config e nao inicia player.

## Arquivos

- Script local: `scripts/board/totem_c2_mock_preview.py`
- Saida padrao: `/tmp/dadooh-c2-preview`
- Indice gerado: `/tmp/dadooh-c2-preview/index.txt`

O script usa apenas Python 3 standard library.

## Como rodar localmente

```sh
python3 scripts/board/totem_c2_mock_preview.py --out-dir /tmp/dadooh-c2-preview
```

Ajuda:

```sh
python3 scripts/board/totem_c2_mock_preview.py --help
```

O argumento `--out-dir` deve apontar para um diretorio dedicado dentro de
`/tmp`. O script recusa saida fora de `/tmp`.

## O que o preview nao faz

- Nao usa SSH.
- Nao toca nas placas.
- Nao usa MPV.
- Nao acessa `/dev/dri`.
- Nao usa `systemd`.
- Nao chama `nmcli`.
- Nao usa NetworkManager.
- Nao cria hotspot.
- Nao cria portal local.
- Nao cria servidor HTTP.
- Nao gera QR funcional.
- Nao le redes reais.
- Nao le config real.
- Nao le status real.
- Nao escreve em `/data`.
- Nao escreve `/data/config/config.json`.
- Nao altera scripts operacionais, launcher, renderer operacional ou
  `kiosky-player`.

## Telas geradas

O script gera SVGs estaticos para:

1. `config_missing`
2. `setup_start`
3. `wifi_select_mock`
4. `wifi_password_mock`
5. `wifi_testing_mock`
6. `wifi_ok_mock`
7. `wifi_error_mock`
8. `environment_input_mock`
9. `environment_invalid_mock`
10. `config_ready_mock`
11. `starting_player_mock`

Todos os SVGs mostram a marca Dadooh, titulo, mensagem curta, acao esperada,
estado/codigo publico e aviso explicito:

```text
Mock visual - nao altera rede nem salva configuracao.
```

## Dados ficticios

O preview usa apenas dados ficticios:

- redes de exemplo: `Rede Exemplo 1`, `Rede Exemplo 2`,
  `Rede Convidado Mock`;
- ambiente de exemplo: `ENVIRONMENT_ID_MOCK`;
- credencial visual: valor mascarado.

Nao usar dados reais em screenshots, READMEs de evidencia, commits ou revisoes.

## Sanitizacao

O script aplica uma checagem simples sobre textos renderizados e redige termos
ou padroes sensiveis como:

- `api_key`;
- `token`;
- `secret`;
- `password`;
- `senha`;
- URLs `http://` ou `https://`;
- atribuicoes diretas de `environment_id`;
- `station_id`;
- paths como `/data/media` ou `/opt/totem`.

O rótulo tecnico `environment_id` pode aparecer, mas o valor real nao pode. O
placeholder permitido e `ENVIRONMENT_ID_MOCK`.

## Criterios de revisao humana

Revisar:

- clareza da tela `config_missing`;
- clareza da acao para iniciar configuracao;
- ordem do fluxo;
- textos publicos;
- legibilidade em 1280x720;
- estados planejados;
- ausencia de terminal, stack trace, path interno ou JSON;
- ausencia de secrets e dados reais;
- risco de o mock parecer funcional;
- clareza de que a transicao para player exige parar setup/renderer antes.

## Decisoes antes de C3/C4/C5

Antes de avancar:

- confirmar se os nomes das telas sao compreensiveis para operador nao
  tecnico;
- confirmar se a etapa de credencial deve existir no mock visual ou ser apenas
  representada;
- aprovar o formato minimo de `environment_id`;
- decidir quais sinais de conectividade C3 deve medir em modo read-only;
- definir plano de bancada C4 para Wi-Fi real com Ethernet preservada;
- definir como C5 vai simular ou validar `api_key` fora da UI sem escrever
  config real.
