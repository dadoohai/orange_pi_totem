# C2 - mock visual/formulario

Status: preparacao documental. Nao implementa mudancas operacionais.

Data: 2026-05-02

## Objetivo

C2 prepara a primeira materializacao visual do fluxo C1 sem tocar em rede,
config real ou player. O objetivo e validar entendimento do operador, ordem das
telas, mensagens publicas e estados planejados antes de qualquer integracao com
NetworkManager, hotspot, portal funcional ou config writer real.

C2 deve deixar claro para revisao e evidencia que o fluxo e mock. Ele nao deve
ser confundido com configuracao funcional de campo.

## Escopo

Incluido:

- mock visual/formulario para Wi-Fi + `environment_id`;
- telas estaticas, preview local ou prototipo sem acao operacional;
- lista de redes ficticias, se houver lista;
- campo de senha mock sem persistencia;
- validacao local apenas do formato proposto de `environment_id`;
- mensagens publicas para sucesso, erro e transicao;
- documentacao da ordem de telas e estados.

Fora de escopo:

- rede real;
- NetworkManager;
- hotspot;
- portal funcional;
- QR funcional;
- varredura real de redes;
- senha real persistida;
- escrita real de config;
- escrita em `/data/config/config.json`;
- alteracao de scripts, systemd ou `kiosky-player`;
- instalacao de pacotes;
- backend de ativacao;
- login ou lista de ambientes.

## O que deve ser validado

- Se o operador entende que a configuracao esta pendente.
- Se a acao para iniciar configuracao e clara.
- Se a ordem das telas faz sentido.
- Se mensagens de sucesso e erro sao legiveis.
- Se estados planejados de C1 aparecem de forma coerente.
- Se renderer/setup visual continua separado do player.
- Se a transicao para "iniciando player" deixa claro que o mock terminaria
  antes do player real.
- Se nenhuma tela, screenshot, status, log ou evidencia contem secrets.
- Se o mock nao parece pronto para uso operacional.

## Telas e estados sugeridos

| Tela/estado | Objetivo | Observacao de C2 |
| --- | --- | --- |
| Configuracao pendente | Reaproveitar o ponto de entrada `config_missing`. | Deve continuar sem iniciar player. |
| Iniciar configuracao | Mostrar acao unica para entrar no fluxo. | Rotular como mock/prototipo em evidencia. |
| Escolher rede mock | Mostrar lista ficticia de redes. | Nao usar SSID real. |
| Digitar senha mock sem persistencia | Simular etapa de senha. | Nao pedir senha real; nao salvar; nao logar. |
| Testando conexao mock | Mostrar espera curta/estado planejado. | Nao testar rede real. |
| Conexao ok mock | Mostrar sucesso ficticio. | Nao afirmar conectividade real. |
| Conexao erro mock | Mostrar erro recuperavel ficticio. | Nao exibir erro bruto de sistema. |
| Inserir `environment_id` | Simular entrada manual do ambiente. | Nao usar valor real em evidencia. |
| `environment_id` invalido | Mostrar validacao local de formato. | Sem backend. |
| Configuracao pronta mock | Mostrar que dados minimos passariam para writer futuro. | Nao escrever config real. |
| Iniciando player mock | Mostrar transicao planejada para player. | Renderer/setup real deve parar antes do player em fase futura. |

## Formato minimo proposto para environment_id no mock

C2 nao valida contra backend. A validacao deve ser apenas local e provisoria:

- aplicar trim de espacos no inicio e no fim;
- rejeitar valor vazio apos trim;
- tamanho minimo proposto: 3 caracteres;
- tamanho maximo proposto: 128 caracteres;
- caracteres permitidos propostos: letras ASCII, numeros, `_`, `-`, `.`, `:`;
- nao permitir espacos internos;
- nao publicar o valor digitado em status publico, log, screenshot de evidencia
  ou README.

Exemplos em evidencia devem usar apenas placeholders como
`ENVIRONMENT_ID_MOCK`, nunca valores reais.

## Textos publicos sugeridos

Textos devem ser curtos, sem termos de terminal e sem prometer operacao real:

| Estado | Texto sugerido |
| --- | --- |
| Configuracao pendente | "Configuracao pendente" |
| Iniciar configuracao | "Iniciar configuracao" |
| Escolher rede mock | "Escolha uma rede de exemplo" |
| Senha mock | "Digite uma senha de teste. Ela nao sera salva." |
| Testando conexao mock | "Testando conexao de exemplo" |
| Conexao ok mock | "Conexao de exemplo aprovada" |
| Conexao erro mock | "Nao foi possivel concluir o teste de exemplo" |
| Ambiente | "Informe o ambiente" |
| Ambiente invalido | "Ambiente invalido" |
| Configuracao pronta mock | "Configuracao pronta para validacao futura" |
| Iniciando player mock | "Iniciando exibicao" |

Quando o mock for mostrado em evidencia, a tela ou o README da rodada deve
deixar claro: "Mock visual. Nao altera rede nem salva configuracao."

## Dados proibidos

C2 nao deve conter, em tela, status, logs, screenshots, README ou artefatos
compartilhaveis:

- `api_key`;
- senha real;
- SSID real;
- URL privada;
- IP publico;
- `environment_id` real;
- `station_id`;
- payload privado;
- path real de midia;
- nome privado de ambiente, unidade, campanha ou arquivo;
- token, header, cookie ou segredo;
- erro bruto de NetworkManager, backend, shell ou stack trace.

## Criterios de aceite

- Documento C2 aprovado antes de qualquer implementacao visual.
- Mock identificado explicitamente como mock/prototipo.
- Nenhuma rede real e listada ou alterada.
- Nenhuma senha real e solicitada, persistida ou registrada.
- Nenhum `environment_id` real aparece em evidencia.
- Nenhum arquivo de config real e escrito.
- Nenhum script, systemd, NetworkManager ou `kiosky-player` e alterado.
- Estados sugeridos cobrem sucesso, erro e retorno.
- Regra renderer/player permanece preservada: setup visual e player principal
  nao rodam juntos.
- `git diff --check` limpo.

## Criterios de rollback

Rollback de C2 deve ser simples:

- remover ou desabilitar o mock visual;
- voltar para a tela B1 `config_missing`;
- manter o launcher atual sem iniciar player quando a config falta;
- preservar qualquer config real existente;
- nao deixar arquivo temporario com dados de entrada do operador.

Como C2 nao altera rede nem config real, rollback nao deve exigir comandos de
NetworkManager, limpeza de `/data/config` ou restauracao do `kiosky-player`.

## Como C2 prepara C3/C4/C5

C2 prepara C3 ao definir quais estados de conectividade precisam aparecer antes
de medir rede de verdade: Wi-Fi associado, IP obtido, internet basica e backend
futuro.

C2 prepara C4 ao validar a ordem e as mensagens antes de qualquer alteracao
real de Wi-Fi em bancada. Assim, C4 pode focar em seguranca operacional,
Ethernet preservada, snapshots e rollback.

C2 prepara C5 ao exercitar o formato minimo de `environment_id` e os erros de
provisionamento sem escrever config real. C5 deve transformar esse aprendizado
em config writer minimo/mock, ainda antes de substituir a config ativa.
