# Fase A - status/splash local minimo

Status: detalhamento tecnico para implementacao incremental. Nao altera
launcher, player, systemd ou placa.

Data: 2026-05-01

## Objetivo

A Fase A deve introduzir uma camada visual local minima para o totem mostrar
identidade Dadooh e estado operacional legivel, sem depender de terminal e sem
adicionar desktop, Chromium, Xorg, Wayland ou compositor.

O resultado desejado e que o operador veja uma tela simples e publica enquanto
o player ainda nao deve ou nao pode assumir a tela. Quando o player puder
iniciar, o status/splash deve sair completamente do caminho.

## Escopo explicito

Incluido:

- mostrar Dadooh + estado;
- mostrar mensagem curta e dica de acao nao sensivel;
- agregar estado local a partir de arquivos ja existentes ou planejados;
- manter todos os artefatos mutaveis em `/data` ou `/tmp`;
- preparar validacao incremental antes de qualquer integracao ao launcher.

Fora do escopo desta fase:

- onboarding;
- Wi-Fi setup;
- QR code;
- Chromium, desktop, Xorg, Wayland ou compositor;
- alteracao do `kiosky-player`;
- alteracao de systemd nesta etapa de documentacao/prototipo;
- coleta ou exibicao de secrets, URLs privadas, IDs privados, SSID, IP publico,
  paths reais ou payloads privados.

## Estados suportados na primeira versao

`booting`

: O sistema local iniciou, mas ainda nao consolidou launcher, config e player.
  Mensagem publica sugerida: "Inicializando totem".

`display_missing`

: Nenhum conector DRM esta reportando display conectado. Como nao ha tela fisica
  nessa condicao, o estado existe principalmente para status local,
  manutencao futura e telemetria sanitizada. O player nao deve iniciar.

`config_missing`

: A configuracao publica minima para iniciar o player nao esta disponivel ou
  nao foi validada. O player nao deve iniciar. Nesta fase a tela deve apenas
  informar que a configuracao esta pendente, sem QR code e sem setup.

`starting_player`

: O launcher ja decidiu iniciar o player. O status/splash ainda pode estar
  visivel por uma janela curta, mas deve encerrar antes do MPV do player tomar
  DRM/KMS.

`player_running`

: O player assumiu reproducao. O status/splash nao deve permanecer desenhando
  na tela nem manter descritor aberto em DRM/KMS.

`player_error`

: O player saiu inesperadamente, falhou ao iniciar ou reportou erro recuperavel.
  A mensagem publica deve ser generica e a causa tecnica sensivel deve ficar em
  logs/diagnostico sanitizado.

`maintenance_placeholder`

: Estado reservado para manutencao local basica futura. Nesta fase nao abre
  painel, nao executa comandos e nao oferece reset.

## Fontes de dados

Fontes locais previstas para o agregador de status:

- `/data/state/kiosky-player/launcher-status.json`: fonte principal do launcher;
- `/tmp/kiosky-launcher-status.json`: fallback do launcher quando `/data` nao
  estiver gravavel;
- `/tmp/kiosky-status.json`: status proprio do `kiosky-player`, quando o app
  estiver ativo;
- estado de `systemctl`, se necessario em fase futura, apenas como complemento.

O consumidor de UX nao deve copiar esses arquivos brutos para a tela. Ele deve
ler, normalizar, reduzir e sanitizar os campos antes de publicar qualquer
estado agregado.

## Contrato de status agregado sanitizado

A Fase A usa o contrato definido em
`docs/product/STATUS_CONTRACT_V0.md`. O contrato publico representa um estado
agregado do appliance, nao um dump do launcher ou do player.

A implementacao local A1.1 fica em
`scripts/board/totem_status_aggregate.py` e esta documentada em
`docs/product/04_STATUS_AGGREGATOR_A1.md`. Ela gera
`/tmp/dadooh-status/status.json` e `/tmp/dadooh-status/status.svg`, ainda sem
exibir nada na tela e sem integracao com o launcher.

Campos esperados:

- `schema_version`;
- `updated_at`;
- `state`;
- `display_connected`;
- `network_state`;
- `config_state`;
- `player_state`;
- `service_state`;
- `error_code`;
- `public_message`;
- `action_hint`;
- `device_label` opcional;
- `version` sem secrets.

O agregador deve mapear estados internos existentes para os estados publicos da
Fase A. Exemplos:

| Fonte | Estado bruto | Estado publico |
| --- | --- | --- |
| launcher | `starting` | `booting` ou `starting_player` |
| launcher | `display_missing` | `display_missing` |
| launcher | `running` + player `playing` | `player_running` |
| launcher | `app_exited` | `player_error` |
| player ausente por config invalida | n/a | `config_missing` |

## Politica de privacidade

A tela, o status publico e diagnosticos compartilhaveis nunca devem mostrar:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`;
- URLs privadas;
- payloads de API;
- paths reais de midia;
- nomes privados de arquivos, campanhas, ambientes ou unidades;
- SSID;
- senha ou material derivado de senha;
- IP publico;
- tokens, headers ou cookies.

Mensagens de erro devem ser orientadas por codigos estaveis e genericos, como
`DISPLAY_MISSING`, `CONFIG_MISSING` ou `PLAYER_EXITED`. O detalhe bruto pode
existir em logs locais restritos, mas nao na camada publica.

## Estrategia de renderizacao

### Preferencia para a primeira versao operacional

A primeira versao operacional deve usar quadros estaticos locais gerados a
partir do contrato sanitizado e exibidos por um processo de status separado,
controlado pelo launcher.

O caminho preferencial para A1 e:

1. gerar um frame simples a partir do estado agregado sanitizado;
2. iniciar um renderizador curto apenas enquanto o player nao deve assumir a
   tela;
3. encerrar e aguardar o renderizador terminar;
4. iniciar o `kiosky-player` somente depois que o renderizador liberou DRM/KMS.

Como a imagem atual ja valida MPV com DRM/KMS, um candidato pragmatico para A1
e usar um processo MPV separado apenas para exibir asset local estatico. Esse
processo nao e o player, nao acessa playlist, nao le config privada e deve ser
tratado como descartavel. A implementacao so deve ser aceita se ficar provado
que o processo encerra antes do player.

### Alternativas avaliadas

Renderizador direto em DRM/KMS

: Arquiteturalmente limpo e evita depender de MPV para splash, mas aumenta o
  risco de codigo nativo ou biblioteca nao presente na imagem. Deve ser avaliado
  depois de A0/A1, nao como primeiro passo bloqueante.

Framebuffer/fbdev

: Pode ser simples quando `/dev/fb*` estiver disponivel, mas a base validada do
  player usa DRM/KMS direto. A disponibilidade e o comportamento em todas as
  placas precisam ser comprovados antes de virar dependencia.

MPV separado exibindo imagem local

: Reaproveita o binario ja presente e o caminho DRM/KMS validado. O risco e
  disputa de DRM/KMS se o processo nao for encerrado corretamente. Deve ser
  estritamente controlado pelo launcher.

Splash de boot apenas

: Ajuda a esconder logs no inicio, mas nao resolve `config_missing`,
  `player_error` ou manutencao futura. Pode complementar, mas nao substitui a
  camada de status.

Chromium/compositor

: Rejeitado para a Fase A. Aumenta superficie, consumo e dependencias ainda nao
  validadas nesta base.

## Risco de disputa DRM/KMS

DRM/KMS e um recurso exclusivo para o objetivo desta fase. Se status/splash e
player tentarem desenhar ao mesmo tempo, o resultado pode ser tela preta, falha
de inicializacao do MPV, loop de restart ou perda de controle visual.

Mitigacoes obrigatorias:

- launcher deve ser o dono da ordem dos processos;
- status/splash deve ter timeout curto e caminho de encerramento explicito;
- antes de iniciar player, launcher deve enviar termino ao status/splash;
- launcher deve aguardar a saida do status/splash;
- em caso de falha ao encerrar status/splash, o launcher deve preferir rollback
  ou estado seguro a iniciar concorrencia em DRM/KMS;
- validacao deve procurar processos remanescentes e erros KMS/GPU.

## Regra critica

Status/splash deve parar antes do player tomar DRM/KMS.

Essa regra vale para qualquer renderer escolhido. Nenhum processo de splash deve
permanecer ativo, segurando descritor de DRM/KMS, quando o `kiosky-player`
iniciar MPV.

## Criterios de aceite

Para A0:

- contrato de status agregado documentado e sem campos sensiveis;
- preview local gera layout textual sem internet, sem MPV e sem `/dev/dri`;
- `git diff --check` limpo.

Para A1:

- com HDMI conectado, status/splash aparece antes do player;
- player entra em reproducao como nas rodadas aprovadas;
- nenhum processo de status/splash permanece ativo depois do player iniciar;
- sem erro DRM/KMS/GPU novo;
- sem escrita em `/opt/totem/kiosky-player`;
- sem secrets, URLs privadas, IDs privados, SSID, IP publico ou paths reais na
  tela/status publico.

Para A2:

- boot sem HDMI registra `display_missing`;
- app/MPV nao iniciam sem HDMI;
- reconectar HDMI segue iniciando o player automaticamente;
- config ausente resulta em `config_missing` sem iniciar player;
- `systemctl --failed` permanece sem falhas relevantes.

Para A3:

- layout fica legivel em 16:9 e orientacao futura documentada;
- mensagens publicas ficam curtas e acionaveis;
- refinamento visual nao altera a ordem de processos nem o contrato.

## Criterios de rollback

Rollback de A0:

- remover ou ignorar documentos/prototipos locais antes da integracao;
- nenhum impacto operacional esperado.

Rollback de A1/A2:

- desabilitar o componente de status/splash;
- voltar o launcher ao comportamento atual: detectar HDMI, iniciar o player
  quando conectado e registrar `display_missing` quando ausente;
- manter `/data/state/kiosky-player/launcher-status.json` e fallback em `/tmp`;
- preservar a configuracao e o player existentes;
- remover apenas artefatos temporarios de status/splash em `/tmp`.

Rollback so deve ser considerado aprovado se o comportamento ja validado
continuar intacto: com HDMI conectado, player ativo; sem HDMI, sem app/MPV e
launcher em `display_missing`.
