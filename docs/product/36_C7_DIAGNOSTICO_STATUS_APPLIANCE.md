# C7.0 - diagnostico/status sanitizado do appliance

Status: contrato e snapshot local/offline. Nao executa acoes operacionais em
placa.

Data: 2026-05-02

## 1. Objetivo

C7 inicia uma camada de diagnostico/status sanitizado do appliance.

Objetivos:

- criar um contrato de diagnostico/status sanitizado do appliance;
- permitir que suporte, UX, homologacao e automacoes futuras entendam o estado
  da config real, servico, launcher, player, MPV, renderer e privacidade sem
  ler segredos;
- preparar uma futura validacao em placa;
- padronizar evidencias curtas e seguras;
- nao substituir homologacao longa.

C7.0 e uma etapa local/offline. Ela nao usa SSH, nao toca placa, nao executa
`systemctl`, nao consulta journal, nao usa NetworkManager, nao inicia/parar
servico e nao le o conteudo de `/data/config/config.json`.

## 2. Relacao com C6

C6 consolidou o primeiro marco com config real ativa em desenvolvimento:

- C6.3A escreveu a config real em `/data/config/config.json` com o servico
  parado, backup restrito e permissoes observadas `root:totem` `0640`;
- C6.4 iniciou o servico controladamente e observou `player_running`, playback
  `playing`, MPV ativo, `kiosk.py` ativo e `NRestarts=0` em smoke curto;
- C6.5 consolidou esse resultado como marco de desenvolvimento, nao
  homologacao e nao producao.

C7 foca em observabilidade curta e segura. Ela ajuda a responder "qual e o
estado agregado agora?" sem transformar o smoke C6.4 em teste prolongado.
Observer de 30-60 minutos, varias horas, reboot/autoboot, segunda placa/cartao,
root read-only, corte seco e rollback real continuam na fila de homologacao.

## 3. Status publico, status bruto e diagnostico

### Status publico

Status publico e seguro para tela, suporte e evidencias sanitizadas. Ele deve
conter somente estados agregados, mensagens publicas, codigos publicos e
campos allowlisted. O contrato v0 ja publica exemplos em
`/tmp/dadooh-status/status.json` e SVG publico.

Exemplos de campos publicos:

- estado publico;
- display conectado como booleano ou desconhecido;
- estado publico da config;
- estado publico do player;
- estado publico do servico;
- codigo publico de erro.

### Status bruto do player

Status bruto do player e a saida interna do `kiosky-player`, hoje observavel em
`/tmp/kiosky-status.json`. Esse arquivo pode conter dados sensiveis ou campos
operacionais que nao devem ser copiados para README, tela, suporte ou
telemetria.

C7 so pode ler campos explicitamente allowlisted desse status bruto. Campos
desconhecidos devem ser ignorados, mesmo que parecam uteis para debug.

### Diagnostico C7

Diagnostico C7 e um agregado sanitizado. Ele combina sinais publicos e
metadados seguros sem copiar config real, sem copiar status bruto completo e
sem publicar logs brutos.

O diagnostico C7 nao e um dump de arquivos internos. Ele deve:

- usar allowlist fechada;
- redigir ou marcar falha de privacidade quando valor allowlisted parecer
  sensivel;
- registrar ausencia/desconhecido sem falha destrutiva;
- publicar apenas arquivos restritos em `/tmp`;
- manter `config_file_content_read=false`.

## 4. Fontes permitidas em C7.0/C7.1

Fontes planejadas para C7:

| Fonte | C7.0 local/offline | C7.1 futura em placa | Regra |
| --- | --- | --- | --- |
| `/tmp/dadooh-status/status.json` | Permitida por fixture ou root local | Permitida read-only | Somente campos publicos allowlisted. |
| `/tmp/kiosky-status.json` | Permitida por fixture ou root local | Permitida read-only | Somente campos allowlisted; nunca copiar o JSON completo. |
| `/data/config/config.json` | Somente metadados relativos ao `--root` | Somente metadados read-only | Nunca abrir conteudo. |
| Presenca de processos | Fora de C7.0 | Possivel em C7.1 se aprovado | Apenas contagens/booleanos sanitizados. |
| `systemd` read-only | Fora de C7.0 | Possivel em fase futura se aprovado | Apenas campos allowlisted, sem journal. |
| Journal bruto | Proibido | Proibido | Nunca publicar journal bruto. |

C7.0 nao deve executar comandos externos. C7.1, se aprovada, precisa de roteiro
separado antes de observar processos ou `systemd` na placa.

## 5. Dados proibidos

O diagnostico C7 nao deve conter:

- `api_key` ou token;
- `api_url` real;
- `environment_id` real;
- `station_id` real;
- payload;
- URL privada;
- nomes de midia;
- paths privados;
- conteudo de config;
- conteudo de backup;
- SSID;
- senha;
- IP;
- hostname;
- MAC;
- BSSID;
- gateway;
- DNS;
- logs brutos.

Tambem nao deve publicar nomes de arquivos privados, argumentos de processo,
respostas de backend, headers, cookies, tracebacks com dados internos ou
conteudo bruto de qualquer arquivo operacional.

## 6. Campos agregados propostos

Schema proposto para o snapshot C7:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `schema_version` | string | Versao do contrato C7. |
| `generated_at` | string | Timestamp UTC do snapshot. |
| `source_presence` | object | Presenca ou indisponibilidade das fontes. |
| `public_state` | string | Estado publico agregado ou `unknown`. |
| `public_config_state` | string | Estado publico da config ou `unknown`. |
| `public_player_state` | string | Estado publico do player ou `unknown`. |
| `public_service_state` | string | Estado publico do servico ou `unknown`. |
| `public_display_connected` | boolean/string | `true`, `false` ou `unknown`. |
| `public_error_code` | string/null | Codigo publico allowlisted ou `null`. |
| `launcher_state` | string | Estado derivado de fonte publica ou `unknown`. |
| `launcher_display_connected` | boolean/string | Display derivado de fonte publica ou `unknown`. |
| `playback_state` | string | Estado de playback allowlisted ou `unknown`. |
| `mpv_running` | boolean/string | Flag allowlisted do player ou `unknown`. |
| `playlist_size_present` | boolean | Indica se tamanho de playlist numerico foi observado. |
| `playlist_size_value` | number/null | Valor numerico seguro, se presente. |
| `current_index_present` | boolean | Indica se indice atual numerico foi observado. |
| `current_index_value` | number/null | Valor numerico seguro, se presente. |
| `last_poll_success_present` | boolean | Indica se o campo existia no status do player. |
| `config_file_exists` | boolean | Presenca do arquivo de config por metadado. |
| `config_file_mode` | string/null | Mode observado por `stat`, sem conteudo. |
| `config_file_owner_group_category` | string | Categoria agregada de owner/group. |
| `config_file_content_read` | boolean | Deve ser sempre `false`. |
| `service_observed` | boolean/string | `unknown` em C7.0. |
| `renderer_active` | boolean/string | `unknown` em C7.0. |
| `kiosk_active` | boolean/string | `unknown` em C7.0. |
| `mpv_process_count` | number/string | `unknown` em C7.0. |
| `privacy_scan` | string | `ok` ou `failed`. |
| `warnings` | array | Codigos publicos e sanitizados. |

Campos auxiliares podem ser adicionados somente se seguirem a mesma regra:
valor agregado, allowlist fechada, sem paths privados e sem texto bruto
arbitrario.

## 7. Criterios de aceite

C7.0 e aceito quando:

- nenhum dado sensivel aparece nos outputs;
- o conteudo da config real nao e lido;
- o status bruto completo nao e copiado;
- os campos de status usam allowlist rigida;
- o script escreve apenas em `/tmp`;
- os arquivos gerados usam permissao restrita;
- o self-test usa fixtures com dados sensiveis e prova que a saida nao vaza;
- valores allowlisted suspeitos sao redigidos ou geram `privacy_scan=failed`;
- fontes ausentes viram `unavailable`/`unknown` sem erro destrutivo;
- `git diff --check` fica limpo.

## 8. Relacao com homologacao

C7 nao substitui observer prolongado. O objetivo e padronizar uma fotografia
sanitizada do estado do appliance para apoiar suporte, UX, homologacao e
automacoes futuras.

A fila de homologacao continua separada. C7 pode ajudar a montar evidencias
futuras com formato consistente, mas nao prova estabilidade de longa duracao,
reboot/autoboot, segunda placa/cartao, root read-only, corte seco, rollback real
ou producao.

## 9. Promocao de governanca C18

Na linha C18, `scripts/board/totem_appliance_status_snapshot.py` permanece
compativel com o schema C7, mas adiciona metadados de governanca:

- `c18_governance.schema=dadooh.c18.appliance_public_state.governance.v1`;
- `responsibility=field-data`;
- `result_claim=read_only_appliance_public_state_collected`.

Esse claim significa apenas que a fotografia publica/sanitizada foi coletada.
Nao significa que `field-data` virou release de software, que o pacote OTA pode
carregar config/midia/cache, ou que H2/producao foram aprovados.

O self-test desse snapshot passa a rodar dentro do gate C18 offline. O binario
continua fora do payload OTA comum de `totem-core` enquanto o updater/base de
campo nao tiver allowlist compativel para novos binarios de diagnostico.
