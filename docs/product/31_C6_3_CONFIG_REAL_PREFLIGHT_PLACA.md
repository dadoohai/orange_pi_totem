# C6.3-preflight - config real na placa

Status: preflight read-only concluido na placa de desenvolvimento. Nao executa
escrita real.

Data: 2026-05-02

## Objetivo

C6.3-preflight inspeciona condicoes reais na placa de desenvolvimento antes da
primeira escrita em `/data/config/config.json`.

Objetivos:

- confirmar usuario/grupo relevantes;
- confirmar existencia e permissoes de `/data/config` sem ler conteudo de
  config real;
- confirmar estado do servico sem alterar `systemd`;
- revisar a logica versionada do launcher;
- documentar risco de inicio prematuro do player;
- definir criterios para abrir C6.3 execucao real.

C6.3-preflight nao escreve config real, nao usa token real, nao le conteudo de
config real, nao inicia player, nao altera servico e nao altera launcher,
renderer, `systemd`, `kiosky-player` ou NetworkManager.

## Escopo read-only

Inclui:

- comandos read-only via SSH na placa de desenvolvimento;
- `id`/`getent` para existencia de usuario/grupo;
- `stat`/`test` para existencia, tipo e permissao de paths conhecidos;
- `runuser ... test -r/-w` para checar legibilidade/escrita pelo usuario
  `totem`, sem abrir ou imprimir conteudo;
- `systemctl is-enabled`, `systemctl is-active` e `systemctl show` com campos
  seguros;
- revisao local da versao do launcher no Git.

Fora de escopo:

- `cat`, `head`, `tail`, `jq`, `grep` ou leitura do conteudo da config real;
- escrita em `/data`;
- criacao de `/data/config`;
- alteracao de config real;
- `systemctl stop/start/restart/enable/disable`;
- `journalctl`;
- NetworkManager, `nmcli`, Wi-Fi, hotspot ou portal;
- player ou MPV;
- token/API key real.

## Resultado sanitizado da inspecao

### Usuario e grupos

Resultado agregado na placa de desenvolvimento:

| Item | Resultado |
| --- | --- |
| usuario `totem` existe | `true` |
| grupo `totem` existe | `true` |
| grupo `audio` existe | `true` |
| grupo `video` existe | `true` |
| grupo `render` existe | `true` |
| `totem` pertence a `totem` | `true` |
| `totem` pertence a `audio` | `true` |
| `totem` pertence a `video` | `true` |
| `totem` pertence a `render` | `true` |

UID/GID e arquivos completos de `/etc/passwd` ou `/etc/group` nao foram
publicados.

### `/data/config`

Resultado agregado, sem ler conteudo de config:

| Path | Existe | Tipo | Mode | Owner/group categoria |
| --- | --- | --- | --- | --- |
| `/data` | `true` | `dir` | `755` | `root_root` |
| `/data/config` | `true` | `dir` | `750` | `totem_totem` |
| `/data/config/config.json` | `true` | `file` | `640` | `root_totem` |

Checks adicionais:

| Check | Resultado |
| --- | --- |
| config legivel por `totem` | `true` |
| config gravavel por `totem` | `false` |

O conteudo de `/data/config/config.json` nao foi lido, copiado ou publicado.
`api_url`, `api_key`, token, `environment_id` e `station_id` reais nao foram
vistos por esta tarefa.

### Servico

Resultado read-only do `kiosky-player.service`:

| Campo | Resultado |
| --- | --- |
| `is-enabled` | `enabled` |
| `is-active` | `active` |
| `ActiveState` | `active` |
| `SubState` | `running` |
| `User` | `totem` |
| `Group` | `totem` |
| `FragmentPath` | `/etc/systemd/system/kiosky-player.service` |

Nenhum comando `systemctl stop/start/restart/enable/disable` foi executado.
`journalctl` nao foi executado.

## Launcher e validacao de config

Revisao da versao versionada em `scripts/board/kiosky_service_launcher.sh`:

- o path default da config e `/data/config/config.json`;
- o app e iniciado com `kiosk.py --config "$CONFIG_PATH"`;
- `config_valid` exige que a config exista e seja legivel;
- `config_valid` le JSON e exige objeto JSON;
- `config_valid` exige strings nao vazias para:
  - `api_url`;
  - `api_key`;
  - `environment_id`;
  - `cache_dir`;
  - `state_dir`;
  - `status_file`;
  - `ipc_path`;
- quando ha display conectado e `config_valid` passa,
  `handle_connected_display` chama `run_app_once`;
- quando a config esta ausente ou invalida, o launcher publica
  `config_missing`, inicia renderer de status quando aplicavel e nao chama o
  app principal.

Observacao: a validacao do launcher e mais estreita que o contrato C5.1/C6. O
writer C6 deve continuar usando o contrato C5.1 `real-dry-run` antes de
qualquer escrita real.

## Risco de inicio prematuro do player

O servico esta `enabled` e `active/running` na placa. Como o launcher monitora
o path default `/data/config/config.json`, uma escrita real que deixe uma config
valida enquanto o servico estiver ativo pode permitir que o launcher chame
`run_app_once` automaticamente.

Riscos:

- player iniciar antes da evidencia ser coletada;
- player iniciar antes da revisao de rollback;
- renderer parar e o app assumir a tela durante a escrita;
- falha de config so aparecer apos o servico reagir.

## Decisao recomendada para C6.3

Recomendacao: C6.3 deve ocorrer com o servico parado durante a escrita real, ou
com outro bloqueio operacional equivalente aprovado antes da execucao.

O controle escolhido deve ser definido e aprovado antes de C6.3. Sem esse
controle, C6.3 deve abortar.

Opcoes aceitaveis para decisao humana:

- parar temporariamente `kiosky-player.service` durante validacao, backup,
  escrita atomica, fsync, revalidacao e evidencia;
- usar bloqueio/override aprovado que impeça o launcher de observar a config
  ativa durante a escrita;
- executar em janela controlada com rollback pronto e criterio explicito para
  religar o servico.

Esta tarefa nao executou nenhuma dessas opcoes; apenas documentou a
necessidade.

## Criterios para C6.3 execucao

C6.3 so deve iniciar quando todos os itens abaixo estiverem resolvidos:

- aprovacao humana explicita para escrita real em `/data/config/config.json`;
- canal local privado para dados reais, sem Codex/Git/evidencia;
- candidata real criada fora do chat e fora do Git;
- validador C5.1 `real-dry-run` limpo sobre candidata real;
- `api_key_present=true` sem imprimir valor;
- placeholders ausentes;
- owner/group/mode finais aprovados;
- decisao se `/data/config` existente sera preservado como esta;
- backup real aprovado, com local e retencao definidos;
- rollback real aprovado;
- servico parado ou bloqueio equivalente aprovado;
- evidencia sanitizada aprovada.

## Criterios de abortar

Abortar C6.3 se qualquer item ocorrer:

- necessidade de publicar token, `api_key`, `api_url` real, IDs reais ou
  payload;
- conteudo da config real precisar ser lido pelo Codex;
- servico ativo sem bloqueio aprovado;
- owner/group/mode incertos;
- backup/rollback nao aprovados;
- candidato real falhar em `real-dry-run`;
- candidata real estiver em `/data` ou local indevido;
- evidencia depender de output bruto;
- placa de desenvolvimento nao for confirmada;
- qualquer escrita fora do plano aprovado.

## Evidencia esperada

A evidencia C6.3 deve conter apenas dados sanitizados:

- placa: desenvolvimento, sem IP/hostname;
- confirmacao de servico parado ou bloqueio aplicado;
- resultado `real-dry-run`;
- `api_key_present=true/false`;
- `placeholder_detected=true/false`;
- config anterior existia: sim/nao;
- backup criado: sim/nao;
- config escrita: sim/nao;
- mode/owner/group observados;
- rollback: nao necessario/executado/falhou;
- player iniciado: somente se aprovado;
- nenhum valor real publicado.

Nao deve conter conteudo de config, backup, token, URL privada, IDs reais,
journal, logs brutos, SSID, senha, IP, hostname, MAC, BSSID, gateway, DNS ou
payload.

## Pendencias antes de escrever config real

- Definir canal local privado dos dados reais.
- Definir responsavel humano por criar a candidata real.
- Definir owner/group/mode finais.
- Definir se o diretorio `/data/config` atual sera usado sem mudanca.
- Aprovar procedimento de backup e rollback.
- Aprovar controle do servico durante C6.3.
- Aprovar modelo de evidencia sanitizada.
