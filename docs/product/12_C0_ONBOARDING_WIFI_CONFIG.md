# C0 - onboarding Wi-Fi/configuracao

Status: planejamento. Nao implementa mudancas operacionais.

Data: 2026-05-01

## Refinamento posterior - C1

Este documento registra a visao original e ampla de onboarding desenhada em C0.
Depois dele, o escopo vigente para a proxima evolucao incremental foi refinado
em C1/ADR-0009 para um onboarding minimo e provisorio: Wi-Fi, sinal claro de
conexao funcionando e `environment_id` manual.

A ativacao por codigo continua como alternativa e visao futura, conforme
ADR-0008, mas nao faz parte desta fase atual. Nesta C1, `api_key` fica fora da
UI e deve vir futuramente de variavel de ambiente, mock ou provisionamento
separado.

Trechos abaixo que falam em codigo curto, operador nao manipular
`environment_id`, backend de ativacao, hotspot ou portal local devem ser lidos
como visao C0/futura, nao como implementacao imediata. A fase atual trabalha
com `environment_id` manual e `api_key` fora da UI.

C1 e C2 nao implementam Wi-Fi real, NetworkManager, hotspot, portal funcional,
ativacao backend ou escrita real de `/data/config/config.json`.

Referencias do refinamento:

- `docs/product/14_C1_CONFIG_MISSING_MINIMAL_ONBOARDING.md`;
- `docs/product/15_C1_MINIMAL_USER_FLOW.md`;
- `docs/product/16_C1_MINIMAL_STATE_MACHINE.md`;
- `docs/DECISIONS/ADR-0009-minimal-config-environment-id.md`;
- `docs/product/17_C2_MOCK_VISUAL_FORMULARIO.md`.

## Objetivo

C0 define a arquitetura de onboarding Wi-Fi/configuracao antes de qualquer
implementacao. Esta fase nao cria hotspot, nao cria portal local, nao altera
NetworkManager, nao grava Wi-Fi, nao escreve `/data/config/config.json` e nao
integra ativacao backend.

Tambem nao implementa reset real, manutencao operacional, telemetria,
update/rollback ou qualquer mudanca no `kiosky-player`.

O objetivo futuro e eliminar terminal, SSH e edicao manual de JSON para o
operador nao tecnico. Um totem novo deve conseguir orientar a configuracao pela
tela Dadooh e por um celular, preservando seguranca, privacidade e capacidade
de recuperacao em bancada.

Este documento fica depois do marco status/splash B1. A homologacao
`v0.1-rc1` permanece separada e nao absorve automaticamente este planejamento.

## Experiencia desejada do operador

Fluxo ideal futuro:

1. Operador liga um totem novo.
2. A tela Dadooh aparece assim que houver display disponivel.
3. Se a config estiver ausente ou invalida, a tela mostra "Configuração
   pendente".
4. A tela mostra orientacao curta para configuracao assistida, sem terminal e
   sem instrucoes tecnicas longas.
5. Operador usa um celular para entrar no fluxo de setup local.
6. Operador seleciona ou informa a rede Wi-Fi.
7. Totem testa a conexao sem derrubar caminho de recuperacao quando houver
   Ethernet de bancada.
8. Operador informa um codigo curto de ativacao.
9. Backend troca o codigo por config segura.
10. Totem valida e salva a config localmente.
11. Launcher detecta config valida, encerra qualquer tela de setup/status e
    inicia o player.
12. Player entra em `player_running` sem o operador manipular `api_key`,
    `environment_id`, `station_id` ou JSON.

## Estados do onboarding

Estados publicos propostos para status/tela/logica de setup:

| Estado | Significado publico | Acao esperada |
| --- | --- | --- |
| `config_missing` | Config minima ausente, ilegivel, invalida ou incompleta. | Mostrar tela Dadooh de configuracao pendente. |
| `waiting_for_setup` | Totem pronto para iniciar configuracao assistida, mas sem canal de setup ativo. | Orientar operador a iniciar setup local. |
| `setup_hotspot_active` | Hotspot de setup ativo em fase futura. | Operador conecta o celular ao setup. |
| `wifi_scanning` | Totem procurando redes disponiveis. | Aguardar lista publica de redes. |
| `wifi_credentials_pending` | Rede escolhida, credencial ainda nao informada ou incompleta. | Operador informa senha no portal local. |
| `wifi_connecting` | Tentando conectar na rede escolhida. | Aguardar teste de conexao. |
| `wifi_connected_no_internet` | Wi-Fi conectou, mas internet/backend nao esta acessivel. | Mostrar erro recuperavel e permitir troca de rede. |
| `wifi_connected` | Wi-Fi conectado com conectividade minima aprovada. | Avancar para ativacao. |
| `activation_pending` | Aguardando codigo de ativacao ou resposta do backend. | Operador informa codigo curto. |
| `activation_failed` | Codigo invalido, expirado ou backend recusou ativacao. | Mostrar codigo publico e permitir nova tentativa. |
| `config_saved` | Config validada e gravada com sucesso. | Preparar transicao para player. |
| `starting_player` | Launcher iniciando player apos config valida. | Renderer/setup deve sair. |
| `player_running` | Player ativo. | Setup deve ficar inativo. |
| `setup_error` | Erro generico recuperavel no setup. | Mostrar mensagem publica e opcao de retry/voltar. |

Estados publicos nao podem conter SSID privado completo se houver risco de
exposicao em diagnostico compartilhavel, senha, token, URL privada, `api_key`,
IDs privados, payloads ou paths reais de midia.

## Separacao de responsabilidades

### Launcher

Orquestra estados locais. Decide se deve manter status/splash, setup,
manutencao ou player. Nao deve conter regra de negocio de Wi-Fi, ativacao ou
portal.

### Status aggregator

Gera estado publico sanitizado a partir de fontes locais allowlisted. Nao deve
ler nem publicar config privada.

### Renderer Dadooh

Mostra estados publicos quando o player nao deve rodar. Deve parar antes do MPV
principal. Nao deve acessar Wi-Fi, backend, secrets ou config privada.

### Futuro setup service

Servico local responsavel pelo fluxo de onboarding por celular. Deve expor
apenas APIs limitadas de setup, sem shell e sem acesso direto ao player.

### NetworkManager adapter

Camada futura e estreita para ler redes, criar/alterar perfis de setup e testar
conectividade. Deve ter rollback claro e preservar Ethernet quando presente.

### Activation client

Cliente futuro que troca codigo curto por config segura. Deve tratar erros sem
vazar detalhes internos do backend.

### Config writer

Responsavel por validar schema, gravar config de forma atomica em
`/data/config/config.json`, ajustar permissoes e preservar ultima config valida
quando aplicavel.

### Maintenance/reset service

Servico futuro para acoes limitadas de reparo, reset e diagnostico sanitizado.
Nao faz parte de C0 e nao deve expor shell.

### kiosky-player

Continua focado em playlist, cache, MPV, watchdog e status proprio. O player
nao deve virar configurador. O setup nao deve tocar MPV nem depender do player.

Regra geral: todo estado mutavel de setup/config fica em `/data` ou `/tmp`.

## Seguranca e privacidade

Regras obrigatorias para as fases futuras:

- Operador nunca digita `api_key`.
- Operador nao ve `environment_id` ou `station_id`.
- API real nao aparece na tela publica.
- Senha Wi-Fi nunca entra em logs, status, diagnostico ou README.
- Config privada nunca aparece em status publico.
- Diagnostico de produto deve ser sanitizado antes de ser exibido, baixado ou
  enviado.
- Portal local nao deve expor shell, comandos arbitrarios, paths internos ou
  stack traces.
- Acoes sensiveis exigem confirmacao explicita.
- Tokens, codigos de ativacao e sessoes de setup devem expirar.
- Erros publicos devem usar codigos allowlisted, nao mensagens brutas.

## Arquitetura tecnica proposta

Esta arquitetura e plano, nao implementacao.

- Usar NetworkManager como backend de rede, preservando a escolha ja validada
  na imagem base.
- Manter modo cliente Wi-Fi para operacao normal.
- Criar hotspot Dadooh Setup somente em fase propria, com criterio de
  recuperacao e sem derrubar Ethernet de bancada.
- Servir portal local simples para celular, sem Chromium local no totem.
- Usar QR code futuro apenas como atalho para o portal/setup; C0 nao gera QR
  funcional.
- Usar codigo curto de ativacao em vez de secrets digitados pelo operador.
- Gravar `/data/config/config.json` por writer atomico: escrever arquivo
  temporario, validar, ajustar permissoes e substituir a config ativa.
- Manter rollback se Wi-Fi falhar: nao apagar conexao anterior valida antes da
  nova conexao ser aprovada.
- Se setup ficar incompleto, retornar para estado publico recuperavel
  (`config_missing`, `waiting_for_setup` ou erro especifico), sem iniciar player
  com config parcial.

## Modelo de ativacao por codigo

Fluxo proposto:

1. Portal local pede um codigo curto ao operador.
2. Totem envia o codigo para o backend de ativacao por canal seguro.
3. Backend valida codigo, expiracao e associacao operacional.
4. Backend retorna a config necessaria de forma segura, incluindo campos como
   `api_url`, `api_key`, `environment_id` e `station_id` apenas para gravacao
   local.
5. Totem valida schema e campos obrigatorios.
6. Config writer salva a config em `/data/config/config.json` com permissoes
   restritas.
7. Codigo/token expira e nao pode ser reutilizado indefinidamente.
8. Em falha, a tela mostra apenas erro publico, por exemplo
   `ACTIVATION_FAILED`, sem URL, token, payload ou motivo interno detalhado.

O operador nunca manipula `api_key`, IDs internos ou JSON.

## Fluxos de erro

| Erro | Comportamento esperado |
| --- | --- |
| Senha Wi-Fi errada | Voltar para `wifi_credentials_pending`, informar erro recuperavel e nao registrar a senha. |
| Rede sem internet | Publicar `wifi_connected_no_internet`, permitir trocar rede ou tentar novamente. |
| DNS falha | Tratar como conectividade incompleta, sem expor hostname privado ou detalhes de resolver. |
| API inacessivel | Manter Wi-Fi conectado, publicar erro publico de ativacao/conectividade e permitir retry. |
| Codigo de ativacao invalido | Publicar `activation_failed`, permitir nova tentativa e nao revelar regra interna de validacao. |
| Config invalida | Rejeitar gravacao, preservar config anterior se existir e voltar para `activation_pending` ou `setup_error`. |
| Queda de energia durante setup | Na volta, detectar setup incompleto e retornar para estado publico seguro sem config parcial ativa. |
| Usuario fecha portal no meio | Manter estado `waiting_for_setup` ou ultimo passo recuperavel, com timeout de sessao. |
| Ethernet disponivel | Preservar Ethernet como caminho de recuperacao e nao desconectar automaticamente. |
| Wi-Fi inexistente | Mostrar lista vazia/erro publico e permitir nova varredura ou uso de Ethernet. |
| HDMI ausente durante setup | Nao tentar renderizar; publicar estado local e continuar seguro ate o display voltar. |

## Estrategia para nao derrubar bancada/SSH

Primeiras validacoes devem comecar conservadoras:

- leitura read-only de estado de rede;
- Ethernet preservada;
- nenhuma desconexao automatica;
- nenhum `nmcli connection down` sem prompt humano;
- snapshots antes/depois de rede e NetworkManager;
- rollback documentado para qualquer perfil criado;
- prompt humano antes de mexer em conexao ativa;
- hotspot apenas depois de fase especifica e com recuperacao validada;
- logs e artefatos brutos fora do Git;
- nenhum teste em placa de homologacao sem plano proprio.

## Fases propostas

| Fase | Objetivo | Implementa rede/config real? |
| --- | --- | --- |
| C0 | Documentacao, arquitetura, riscos e criterio de aceite. | Nao. |
| C1 | QR placeholder e texto de setup na tela, sem QR funcional. | Nao. |
| C2 | Portal local mock, sem mexer em rede. | Nao. |
| C3 | Diagnostico Wi-Fi read-only. | Nao altera rede. |
| C4 | Configuracao Wi-Fi em bancada com Ethernet de recuperacao. | Sim, controlado. |
| C5 | Hotspot Dadooh Setup. | Sim, fase propria. |
| C6 | Ativacao backend por codigo. | Sim, sem secrets na UI. |
| C7 | Gravacao segura de config. | Sim, writer atomico. |
| C8 | Reset/reparo. | Sim, limitado e protegido. |
| C9 | Validacao de campo. | Sim, criterios completos. |

## Criterios de aceite para C0

- Documento C0 criado.
- Riscos principais mapeados em documento proprio.
- ADR proposta criada.
- Nenhum codigo operacional alterado.
- Nenhum script alterado.
- Nenhuma alteracao em rede ou NetworkManager.
- Nenhum secret, URL privada, SSID, IP publico, ID privado, payload privado ou
  path real de midia publicado.
- Roadmap atualizado.
- `git diff --check` limpo.
