# C1 - mapa de estados do onboarding minimo

Status: contrato documental planejado. Nao implementa mudancas operacionais.

Data: 2026-05-02

## Objetivo

Este documento define os estados minimos para o fluxo C1 de
`config_missing` ate inicio do player. O escopo e documental: nao altera
launcher, renderer, NetworkManager, systemd ou `kiosky-player`.

## Regra obrigatoria DRM/KMS

Player principal e renderer/setup visual nao podem disputar DRM/KMS.

- Estado que exige player rodando deve parar renderer/setup antes.
- Estado que exige setup/renderizacao nao deve iniciar `kiosk.py` nem MPV
  principal.
- Se renderer/setup nao parar, o player deve continuar bloqueado e o sistema
  deve publicar erro controlado.

## Dados proibidos em todos os estados

Nenhum estado publico, diagnostico, README ou tela publica de status deve
conter:

- `api_key`;
- senha Wi-Fi;
- URL privada;
- payload privado;
- token, header, cookie ou segredo;
- SSID real fora da lista local temporaria de escolha Wi-Fi;
- IP publico;
- `environment_id` real fora do formulario de edicao local;
- `station_id`;
- path real de midia;
- nome privado de ambiente, unidade, campanha ou arquivo.

Na tabela, "dados proibidos" sempre inclui esta lista global. Telas locais de
entrada podem mostrar temporariamente o dado que o operador esta editando, mas
esse dado nao deve ir para status publico, diagnostico, logs compartilhaveis ou
documentacao.

## Estados

### booting

| Campo | Definicao |
| --- | --- |
| Descricao | Sistema inicializando antes de decidir entre display, config, setup ou player. |
| Mensagem publica | "Dadooh / inicializando". |
| Acao do operador | Aguardar. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Pode haver splash/status futuro; renderer operacional atual foi validado apenas para `config_missing`. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global. |
| Transicoes | `display_missing`, `config_missing`, `starting_player`, `setup_error`. |
| Suporte atual | Parcial: estado existe no contrato publico; fluxo operacional ainda nao e onboarding. |

### display_missing

| Campo | Definicao |
| --- | --- |
| Descricao | HDMI/display nao detectado. Sem tela fisica para mostrar setup. |
| Mensagem publica | "Tela nao detectada". |
| Acao do operador | Verificar cabo HDMI e energia da tela. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Nao, porque nao ha display. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global. |
| Transicoes | `booting` apos reavaliacao, `config_missing` se HDMI volta e config falta, `starting_player` se HDMI volta e config e valida. |
| Suporte atual | Suportado em desenvolvimento. |

### config_missing

| Campo | Definicao |
| --- | --- |
| Descricao | Config ausente, ilegivel, invalida ou incompleta. |
| Mensagem publica | "Configuracao pendente". |
| Acao do operador | Iniciar configuracao quando a acao existir em fase futura. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim, renderer Dadooh/status pode rodar enquanto o player esta bloqueado. |
| Pode alterar rede? | Nao no estado atual; apenas transiciona para setup futuro. |
| Dados proibidos | Lista global e qualquer conteudo bruto da config. |
| Transicoes | `setup_start`, `display_missing`, `starting_player` se config valida aparecer por provisionamento externo, `setup_error`. |
| Suporte atual | Suportado em desenvolvimento para tela Dadooh B1, sem setup. |

### setup_start

| Campo | Definicao |
| --- | --- |
| Descricao | Inicio do fluxo assistido de configuracao minima. |
| Mensagem publica | "Configuracao assistida". |
| Acao do operador | Confirmar inicio do fluxo quando existir UI. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim, setup visual planejado. |
| Pode alterar rede? | Nao; ainda e entrada do fluxo. |
| Dados proibidos | Lista global. |
| Transicoes | `wifi_select`, `config_missing`, `setup_error`, `display_missing`. |
| Suporte atual | Planejado. |

### wifi_select

| Campo | Definicao |
| --- | --- |
| Descricao | Lista ou escolha de rede Wi-Fi em fluxo futuro. |
| Mensagem publica | "Escolha a rede Wi-Fi". |
| Acao do operador | Selecionar uma rede disponivel. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Nao em C1 documental; futuramente apenas via adapter controlado. |
| Dados proibidos | Lista global; SSID real nao deve entrar em status publico ou diagnostico. |
| Transicoes | `wifi_password`, `wifi_error`, `config_missing`, `display_missing`. |
| Suporte atual | Planejado. |

### wifi_password

| Campo | Definicao |
| --- | --- |
| Descricao | Entrada de senha da rede escolhida. |
| Mensagem publica | "Digite a senha da rede". |
| Acao do operador | Informar senha Wi-Fi. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Nao ate confirmar teste de conexao em fase futura. |
| Dados proibidos | Lista global; senha nunca deve ir para logs, status ou diagnostico. |
| Transicoes | `wifi_testing`, `wifi_select`, `wifi_error`, `display_missing`. |
| Suporte atual | Planejado. |

### wifi_testing

| Campo | Definicao |
| --- | --- |
| Descricao | Teste de associacao, IP, internet basica e, futuramente, backend. |
| Mensagem publica | "Testando conexao". |
| Acao do operador | Aguardar. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Sim em fase futura, mas apenas de forma controlada e com rollback. |
| Dados proibidos | Lista global; nao exibir senha, SSID real, IP publico, hostname ou URL. |
| Transicoes | `wifi_ok`, `wifi_error`, `display_missing`, `setup_error`. |
| Suporte atual | Planejado. |

### wifi_ok

| Campo | Definicao |
| --- | --- |
| Descricao | Conectividade minima aprovada para avancar. |
| Mensagem publica | "Conexao funcionando". |
| Acao do operador | Avancar para ambiente. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Nao neste estado; operador pode voltar para trocar rede se permitido. |
| Dados proibidos | Lista global. |
| Transicoes | `environment_input`, `wifi_select`, `display_missing`, `setup_error`. |
| Suporte atual | Planejado. |

### wifi_error

| Campo | Definicao |
| --- | --- |
| Descricao | Falha recuperavel de senha, associacao, IP, internet ou backend futuro. |
| Mensagem publica | "Nao foi possivel conectar". |
| Acao do operador | Corrigir senha, tentar novamente ou escolher outra rede. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Sim em fase futura, via retorno para selecao/teste controlado. |
| Dados proibidos | Lista global; erro bruto de NetworkManager, DNS ou backend nao deve aparecer. |
| Transicoes | `wifi_select`, `wifi_password`, `wifi_testing`, `config_missing`, `display_missing`. |
| Suporte atual | Planejado. |

### environment_input

| Campo | Definicao |
| --- | --- |
| Descricao | Entrada manual de `environment_id`. |
| Mensagem publica | "Informe o ambiente". |
| Acao do operador | Digitar `environment_id`. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Nao; pode voltar ao fluxo Wi-Fi se necessario. |
| Dados proibidos | Lista global; valor real nao deve sair do formulario local para status ou diagnostico. |
| Transicoes | `environment_invalid`, `config_saving`, `wifi_select`, `display_missing`. |
| Suporte atual | Planejado. |

### environment_invalid

| Campo | Definicao |
| --- | --- |
| Descricao | `environment_id` vazio ou com formato minimo invalido. |
| Mensagem publica | "Ambiente invalido". |
| Acao do operador | Corrigir o valor informado. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global; nao publicar o valor recusado. |
| Transicoes | `environment_input`, `config_missing`, `display_missing`. |
| Suporte atual | Planejado. |

### config_saving

| Campo | Definicao |
| --- | --- |
| Descricao | Validacao e gravacao futura da config minima. |
| Mensagem publica | "Salvando configuracao". |
| Acao do operador | Aguardar. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim ate a config ser salva e antes de iniciar o player. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global; config privada nao deve ser impressa. |
| Transicoes | `config_saved`, `setup_error`, `environment_invalid`, `display_missing`. |
| Suporte atual | Planejado. |

### config_saved

| Campo | Definicao |
| --- | --- |
| Descricao | Config minima validada e salva com sucesso em fase futura. |
| Mensagem publica | "Configuracao salva". |
| Acao do operador | Aguardar inicio do player. |
| Player deve rodar? | Ainda nao; transicao deve preparar parada do setup. |
| Renderer/setup deve rodar? | Pode mostrar sucesso breve, depois deve parar antes do player. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global. |
| Transicoes | `starting_player`, `setup_error`, `display_missing`. |
| Suporte atual | Planejado. |

### starting_player

| Campo | Definicao |
| --- | --- |
| Descricao | Launcher iniciando o player com config valida. |
| Mensagem publica | "Iniciando exibicao". |
| Acao do operador | Aguardar. |
| Player deve rodar? | Sim, em inicio. |
| Renderer/setup deve rodar? | Nao. Deve ter parado antes de `kiosk.py`/MPV principal. |
| Pode alterar rede? | Nao. |
| Dados proibidos | Lista global. |
| Transicoes | `player_running`, `player_error` futuro, `config_missing`, `display_missing`. |
| Suporte atual | Suportado em desenvolvimento como estado publico de transicao. |

### player_running

| Campo | Definicao |
| --- | --- |
| Descricao | Player ativo e reproduzindo conteudo. |
| Mensagem publica | "Exibicao em andamento". |
| Acao do operador | Nenhuma. |
| Player deve rodar? | Sim. |
| Renderer/setup deve rodar? | Nao. |
| Pode alterar rede? | Nao pelo fluxo C1. |
| Dados proibidos | Lista global. |
| Transicoes | `display_missing`, `config_missing` se config deixar de ser valida em reavaliacao futura, `player_error` futuro. |
| Suporte atual | Suportado em desenvolvimento. |

### setup_error

| Campo | Definicao |
| --- | --- |
| Descricao | Erro recuperavel generico do fluxo de setup. |
| Mensagem publica | "Nao foi possivel concluir a configuracao". |
| Acao do operador | Tentar novamente ou chamar suporte autorizado. |
| Player deve rodar? | Nao. |
| Renderer/setup deve rodar? | Sim, se houver display. |
| Pode alterar rede? | Nao diretamente; deve transicionar para estado especifico. |
| Dados proibidos | Lista global; stack trace, comandos, paths e payloads nao devem aparecer. |
| Transicoes | `config_missing`, `setup_start`, `wifi_select`, `environment_input`, `display_missing`. |
| Suporte atual | Planejado. |

## Resumo de suporte atual

| Estado | Atual ou planejado |
| --- | --- |
| `booting` | Parcial pelo contrato publico. |
| `display_missing` | Suportado em desenvolvimento. |
| `config_missing` | Suportado em desenvolvimento com renderer B1. |
| `setup_start` | Planejado. |
| `wifi_select` | Planejado. |
| `wifi_password` | Planejado. |
| `wifi_testing` | Planejado. |
| `wifi_ok` | Planejado. |
| `wifi_error` | Planejado. |
| `environment_input` | Planejado. |
| `environment_invalid` | Planejado. |
| `config_saving` | Planejado. |
| `config_saved` | Planejado. |
| `starting_player` | Suportado em desenvolvimento. |
| `player_running` | Suportado em desenvolvimento. |
| `setup_error` | Planejado. |
