# C9.5 - Wi-Fi real controlado com NetworkManager adapter estreito

Status: plano curto. Nao implementa apply real nesta etapa.

Data: 2026-05-04

## Objetivo

Preparar o proximo corte para configurar Wi-Fi real de forma controlada,
preservando Ethernet e mantendo diagnostico/evidencia sanitizados.

C9.5 nao implementa hotspot, portal, login, backend, writer, config real,
factory reset, reboot ou producao.

## Escopo

Criar um adapter estreito para NetworkManager com tres modos:

```text
--read-only
--plan
--apply
```

`--apply` deve exigir confirmacao humana textual explicita e deve ficar fora
da rodada inicial ate revisao do plano.

## Regras obrigatorias

- ler estado de rede apenas de forma agregada em `--read-only`;
- nao publicar SSID, senha, IP, MAC, gateway, DNS, BSSID, hostname ou nome de
  conexao NetworkManager;
- preservar Ethernet como canal de recuperacao;
- usar perfil Wi-Fi dedicado do produto;
- nao apagar conexao antiga antes de a nova funcionar;
- aplicar timeout curto e rollback;
- nao logar senha;
- nao passar senha por argumento de processo;
- nao escrever senha em evidencia;
- nunca chamar `nmcli connection up/down/delete/modify` sem confirmacao humana
  explicita no modo `--apply`;
- nao iniciar hotspot;
- nao criar portal;
- nao alterar `/data/config/config.json`;
- nao ler `/data/config/config.json`;
- nao chamar writer;
- nao reiniciar player como parte do Wi-Fi;
- nao rebootar.

## Estado read-only permitido

Saida publica permitida:

```text
network_device_present: true/false/unknown
ethernet_connected: true/false/unknown
wifi_device_present: true/false/unknown
wifi_connected: true/false/unknown
default_route_type: ethernet/wifi/unknown
connectivity: ok/unknown/not_checked
```

Saida proibida:

```text
SSID
senha
IP
MAC
gateway
DNS
BSSID
hostname
nome de conexao
cmdline bruta
logs brutos
```

## Plano de apply futuro

O modo `--apply` futuro deve:

- receber credencial por canal humano/local que nao passe por Codex/chat/log;
- criar ou atualizar somente o perfil dedicado do produto;
- testar conexao com timeout;
- preservar Ethernet ativa;
- se falhar, reverter para o estado anterior sem apagar perfis existentes;
- gerar evidencia sanitizada em `/tmp`;
- terminar com diagnostico read-only final;
- exigir confirmacao humana textual antes de qualquer comando modificador.

## Evidencia esperada

Somente artefatos sanitizados sob `/tmp`, com:

- modo executado;
- comandos permitidos por categoria, sem cmdline sensivel;
- estado agregado antes/depois;
- timeout/rollback executado ou nao;
- Ethernet preservada;
- senha publicada: false;
- SSID publicado: false;
- IP/MAC/DNS publicados: false;
- config real lida/escrita: false;
- writer chamado: false.

## Gates antes de implementar

- revisar comandos exatos do adapter;
- revisar forma segura de entrada da senha fora do Codex;
- definir nome do perfil dedicado do produto;
- definir rollback e timeout;
- validar `--read-only` em placa antes de qualquer `--apply`;
- confirmar que C9.4.1 permanece recuperavel com player final ativo.

## Proximo passo

Implementar apenas `--read-only` e `--plan` primeiro. `--apply` real fica para
rodada separada com autorizacao humana explicita.
