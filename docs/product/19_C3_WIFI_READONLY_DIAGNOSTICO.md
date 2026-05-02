# C3 - diagnostico Wi-Fi read-only

Status: base inicial em implementacao/preparada. Nao altera rede.

Data: 2026-05-02

## Objetivo

C3 cria a primeira base local de diagnostico sanitizado de rede/Wi-Fi para
preparar as fases futuras de onboarding. O diagnostico e apenas leitura: ele
observa estado agregado, gera arquivos publicos sanitizados em `/tmp` e nao
executa nenhuma acao que altere NetworkManager, Wi-Fi, Ethernet, config real,
launcher, renderer, `systemd` ou `kiosky-player`.

C3 existe para responder perguntas basicas antes de C4:

- existe dispositivo Wi-Fi observado?
- o dispositivo Wi-Fi parece habilitado/gerenciavel?
- ha alguma associacao/conexao Wi-Fi observada, sem publicar SSID?
- ha IP local, sem publicar endereco?
- ha rota default, sem publicar gateway?
- DNS, internet e backend devem ser tratados com cuidado e podem ficar como
  `not_checked` quando exigirem trafego externo ou expuserem dados sensiveis.

## Diferenca entre C2, C3 e C4

### C2 - mock visual

C2 e um preview estatico/mock do fluxo de configuracao. Ele nao le estado real
de rede, nao chama `nmcli`, nao mede conectividade, nao salva config e nao
representa uma ferramenta operacional de campo.

### C3 - diagnostico read-only

C3 observa sinais locais de rede com comandos allowlisted e publica somente
estados agregados. Ele pode indicar que ha Wi-Fi observado, conexao aparente,
IP local e rota default, mas nao tenta senha, nao conecta, nao desconecta, nao
cria hotspot e nao prova internet/backend.

### C4 - Wi-Fi real controlado em bancada

C4 sera a primeira fase que podera alterar Wi-Fi, somente em bancada, com
Ethernet preservada, plano humano, snapshots antes/depois e rollback
documentado. C4 deve nascer dos limites provados em C3, nao reutilizar C3 como
ferramenta mutavel.

## O que C3 pode medir

C3 pode medir apenas sinais locais agregados:

| Nivel | Saida publica permitida | Observacao |
| --- | --- | --- |
| Wi-Fi device presente | `wifi_device_count` numerico. | Nao publicar nome da interface. |
| Wi-Fi device habilitado | `wifi_device_count > 0` e estado agregado, quando observavel. | Sem `rfkill` nesta base inicial. |
| Wi-Fi associado/conectado | `wifi_connected=true/false/unknown`. | Nao publicar SSID, BSSID ou nome de conexao. |
| IP local presente | `has_local_ip=true/false/unknown`. | Nao publicar endereco, mascara ou interface. |
| Rota default presente | `has_default_route=true/false/unknown`. | Nao publicar gateway, interface ou rota completa. |
| DNS configurado | `dns_state=not_checked` ou `unknown`. | Nao publicar dominio, search domain ou servidor. |
| Internet/backend | `internet_state=not_checked` e `backend_state=not_checked`. | Trafego externo fica para decisao futura. |

## O que C3 nao pode fazer

C3 nao pode:

- configurar Wi-Fi;
- testar senha;
- conectar ou desconectar rede;
- criar hotspot;
- criar portal;
- alterar perfis NetworkManager;
- gravar config real;
- escrever em `/data`;
- escrever `/data/config/config.json`;
- iniciar player;
- mexer em launcher, renderer operacional, `systemd` ou `kiosky-player`;
- executar ping, abrir socket externo ou chamar backend;
- publicar saida bruta de comandos de rede.

## Dados permitidos

Os artefatos C3 podem conter somente:

- `schema_version`;
- data de geracao;
- disponibilidade agregada de ferramentas (`nmcli`, `ip`, `iw`);
- NetworkManager observado como `true`, `false` ou `unknown`;
- Ethernet conectada como `true`, `false` ou `unknown`;
- contagem de dispositivos Wi-Fi;
- Wi-Fi conectado como `true`, `false` ou `unknown`;
- IP local presente como `true`, `false` ou `unknown`;
- rota default presente como `true`, `false` ou `unknown`;
- DNS/internet/backend como `not_checked` ou `unknown`;
- codigos publicos de aviso;
- objeto de privacidade indicando dados omitidos.

## Dados proibidos

Nenhum artefato, resumo, log, README ou evidencia C3 deve publicar:

- SSID real;
- senha Wi-Fi;
- BSSID;
- MAC address;
- IP real, publico ou local;
- gateway real;
- hostname;
- nome de conexao NetworkManager;
- dominio interno ou servidor DNS sensivel;
- rota completa;
- URL privada;
- `api_key`;
- token, header, cookie ou segredo;
- `environment_id` real;
- `station_id`;
- payload privado;
- path real de midia ou config privada;
- erro bruto longo de `nmcli`, `ip`, `iw` ou NetworkManager.

## Comandos permitidos

A primeira base C3 limita leitura a estes comandos, quando existirem:

```sh
nmcli -t -f DEVICE,TYPE,STATE device status
nmcli -t -f NAME,TYPE,DEVICE connection show --active
ip -brief addr show
ip route show default
iw dev
```

Mesmo quando esses comandos retornarem dados privados, a publicacao deve
descartar a saida bruta e gravar apenas estados agregados.

## Comandos proibidos

C3 nao pode executar comandos mutaveis ou equivalentes, incluindo:

```sh
nmcli connection up
nmcli connection down
nmcli connection modify
nmcli connection delete
nmcli device wifi connect
nmcli device disconnect
rfkill block
rfkill unblock
ip route add
ip route delete
ip addr add
ip addr delete
systemctl start
systemctl stop
systemctl restart
systemctl enable
systemctl disable
```

Tambem ficam proibidos ping, curl, wget, chamadas HTTP, socket externo, hotspot,
portal local, `apt`, escrita em `/data` e qualquer acao operacional fora da
allowlist.

## Criterios de aceite

- Documento C3 criado e revisado.
- Script read-only novo criado, sem alterar scripts brutos existentes.
- Script usa apenas Python 3 standard library.
- Script escreve somente em diretorio dedicado sob `/tmp`.
- Diretorio de saida fica com permissao `700`.
- `status.json` e `summary.txt` ficam com permissao `600`.
- `--out-dir` fora de `/tmp` e recusado.
- Comandos executaveis sao validados por allowlist fechada.
- Comandos mutaveis sao bloqueados por validacao interna.
- Ausencia de `nmcli`, `ip` ou `iw` vira `unavailable`/`unknown`, sem falha
  destrutiva.
- Nenhum SSID, IP, MAC, hostname, gateway ou nome de conexao e publicado.
- `--self-test` cobre sanitizacao, recusa de saida fora de `/tmp` e bloqueio de
  comandos proibidos.
- `git diff --check` limpo.

## Criterios de rollback

Rollback de C3 deve ser simples:

- remover o script novo `scripts/board/totem_wifi_readonly_snapshot.py`;
- remover este documento se a abordagem for rejeitada;
- apagar apenas artefatos temporarios sob `/tmp/dadooh-c3-wifi-readonly`;
- nao executar comandos de NetworkManager para desfazer nada, porque C3 nao
  deve ter alterado rede;
- nao tocar em `/data`, launcher, renderer, `systemd` ou `kiosky-player`.

## Como C3 prepara C4

C3 prepara C4 ao separar sinais observaveis de acoes mutaveis. Antes de
alterar Wi-Fi em bancada, C4 devera usar a mesma linguagem publica para:

- Wi-Fi device presente;
- Wi-Fi conectado ou nao;
- IP local presente ou ausente;
- rota default presente ou ausente;
- DNS/internet/backend como etapas separadas;
- erros publicos sem dados brutos.

C4 tambem deve herdar de C3 a regra de nao publicar evidencias brutas com SSID,
IP, nome de conexao ou hostname.

## Como preservar Ethernet/bancada

C3 preserva Ethernet porque:

- nao executa `nmcli connection down`;
- nao executa `nmcli device disconnect`;
- nao altera perfis;
- nao mexe em radio Wi-Fi;
- nao cria hotspot;
- nao chama `rfkill`;
- nao muda rota, IP ou DNS;
- nao reinicia NetworkManager;
- nao altera launcher ou servicos.

Se Ethernet estiver presente, o diagnostico pode publicar apenas
`ethernet_connected=true`, sem interface, IP, gateway ou hostname.

## Como evitar vazamento

Regras obrigatorias:

- nunca gravar saida bruta de `nmcli`, `ip` ou `iw`;
- publicar somente campos allowlisted;
- transformar erros em codigos publicos curtos;
- truncar e sanitizar qualquer texto auxiliar antes de uso interno;
- manter artefatos com permissao restrita;
- usar placeholders em docs e evidencias;
- revisar `status.json` e `summary.txt` antes de compartilhar;
- nunca copiar SSID, IP, gateway, hostname, nome de conexao, URL ou segredo para
  README, issue, PR ou chat.
