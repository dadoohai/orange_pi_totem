# C1 - config_missing e onboarding minimo

Status: escopo documental refinado. Nao implementa mudancas operacionais.

Data: 2026-05-02

## Objetivo

C1 define um escopo minimo e provisorio para evoluir a experiencia de
`config_missing` quando o totem ja tem sistema, servico, launcher e HDMI
funcionando, mas falta configuracao essencial para iniciar o player.

O objetivo desta fase e permitir, em implementacoes futuras, que um operador nao
tecnico complete o minimo necessario sem terminal:

- configurar Wi-Fi;
- confirmar que a conexao esta funcionando;
- informar `environment_id` manualmente;
- salvar uma config minima;
- iniciar o player.

C1 nao implementa rede real, hotspot, portal, formulario, QR funcional ou
gravacao real de config. A fase documenta o recorte de produto e os limites
tecnicos antes de qualquer mudanca operacional.

## Por que C1 refina C0

C0 e ADR-0008 desenharam uma visao mais ampla de onboarding, incluindo hotspot,
portal local por celular e ativacao por codigo curto. Essa direcao continua
valida como visao futura.

C1 reduz o escopo atual porque a necessidade imediata e menor: quando o sistema
ja inicializa, o HDMI esta conectado e o launcher chega a `config_missing`, o
operador precisa de um caminho simples para completar apenas Wi-Fi e
`environment_id`.

Portanto:

- C0 permanece como historico e arquitetura mais ampla;
- ADR-0008 permanece como proposta de futuro para ativacao por codigo;
- C1 nao reescreve o passado;
- C1 adiciona uma camada minima para desenvolvimento incremental.

## Tres casos diferentes

### config_missing atual

O estado atual ja foi validado em desenvolvimento:

- launcher detecta config ausente, invalida ou incompleta;
- `kiosk.py` nao inicia;
- MPV principal do player nao inicia;
- renderer Dadooh mostra "Configuracao pendente";
- renderer e player principal nao rodam juntos;
- ao restaurar config valida, renderer para e o player inicia.

Esse comportamento e uma protecao do sistema. Ele ainda nao permite ao operador
configurar Wi-Fi ou preencher dados pela tela.

### Onboarding minimo desta fase

O onboarding minimo C1 e o fluxo planejado para sair de `config_missing` sem
terminal. Ele considera que:

- a imagem/sistema ja esta preparado;
- o servico do totem ja sobe;
- o launcher ja coordena display, config e player;
- existe HDMI conectado;
- falta configuracao importante para o player.

O fluxo futuro deve coletar somente o necessario para esta fase:

- Wi-Fi;
- sinal claro de conexao funcionando;
- `environment_id` manual;
- config minima validada antes de ativar o player.

### Primeira inicializacao completa de cartao virgem

A primeira inicializacao de um cartao Armbian recem-gravado fica fora desta
fase. Esse caso tem outras camadas:

- usuario inicial;
- senha inicial;
- rede inicial;
- fuso horario;
- idioma;
- SSH;
- hardening;
- provisionamento pos-gravacao.

C1 nao tenta resolver esse fluxo. Ele parte de um totem que ja tem base tecnica
e servico operacional.

## Usuario alvo

O usuario desta tela e um operador nao tecnico que encontrou o totem sem
configuracao importante.

Esse operador pode estar:

- na primeira instalacao operacional de um totem ja preparado;
- em uma situacao posterior em que a config essencial foi removida, corrompida
  ou ficou incompleta.

Esse operador nao e tecnico de bancada e nao deve precisar de terminal, SSH,
editor de JSON ou conhecimento interno do `kiosky-player`.

## O que o operador deve conseguir fazer futuramente

- Escolher ou configurar Wi-Fi por um fluxo assistido.
- Ver se a conexao esta funcionando.
- Inserir `environment_id`.
- Receber erro claro se o campo estiver vazio ou invalido.
- Salvar a config minima.
- Ver o sistema iniciar o player depois da config valida.

## O que o operador nao deve fazer

- Editar JSON.
- Usar terminal.
- Usar SSH.
- Digitar `api_key`.
- Ver `api_key`.
- Escolher rotacao.
- Trocar ambiente com player rodando.
- Executar reset.
- Fazer manutencao avancada.
- Ver URLs privadas, payloads privados, paths reais de midia, IP publico,
  SSID, senha ou identificadores reais em tela publica, docs ou diagnostico.

## Premissas

- `api_key` vem de variavel de ambiente, mock ou provisionamento separado.
- `api_key` nao aparece na UI e nao e digitada pelo operador.
- Idioma e fuso horario ficam para pos-gravacao ou primeira instalacao
  completa.
- A estetica final sera refinada depois.
- Esta fase nao implementa rede real.
- Esta fase nao implementa hotspot.
- Esta fase nao implementa portal local.
- Esta fase nao implementa escrita real de config.
- Esta fase nao altera NetworkManager.
- Esta fase nao altera scripts, systemd ou `kiosky-player`.
- C1 nao libera producao.

## Nota tecnica sobre api_key

A config minima atual do player/launcher ainda espera campos privados como
`api_key`. A decisao de manter `api_key` fora da UI exige uma decisao tecnica
futura antes de implementar o writer real:

- o config writer pode injetar `api_key` a partir de env, mock ou
  provisionamento separado sem mostrar ao operador; ou
- launcher/player podem passar a aceitar `api_key` por variavel de ambiente ou
  provisionamento separado.

C1 apenas documenta essa dependencia. Nenhuma mudanca tecnica deve ser feita
nesta tarefa.

## Fluxo base

1. Totem liga.
2. Tela Dadooh indica inicializacao.
3. Launcher verifica HDMI.
4. Launcher verifica config.
5. Se a config e valida, o renderer nao permanece ativo e o player inicia.
6. Se a config esta ausente ou incompleta, aparece a tela de configuracao
   pendente.
7. Em fase futura, operador configura Wi-Fi e informa `environment_id`.
8. Sistema valida e salva config minima.
9. Renderer/setup para.
10. Player inicia.

## Regras de nao regressao

- Player principal e renderer/setup visual nunca devem disputar DRM/KMS.
- Estado que precisa do player deve parar renderer/setup antes de iniciar
  `kiosk.py` ou MPV principal.
- Estado que precisa de setup/renderizacao nao deve iniciar `kiosk.py` ou MPV
  principal.
- `display_missing` continua sem tentar renderizar enquanto nao ha display.
- `config_missing` continua sem iniciar player.
- Status publico e tela continuam sanitizados.
- Desenvolvimento C1 continua separado da homologacao `v0.1-rc1` e de qualquer
  decisao de producao.
