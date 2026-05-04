# C9.0 - acesso temporario ao setup pela rede local existente

Status: executado em desenvolvimento. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C9.0 validou o setup C8 rodando temporariamente na Orange Pi e acessivel por
navegador na rede local de bancada existente.

O objetivo era validar a experiencia de operador fora do terminal, sem
implementar Wi-Fi real, hotspot, portal definitivo ou servico permanente.

## 2. Escopo executado

Foi permitido e executado:

- usar a rede local existente;
- copiar o servidor de setup para `/tmp`;
- rodar o setup temporariamente na placa;
- expor o setup em porta definida;
- permitir acesso humano pelo navegador;
- gerar candidata de teste apenas em `/tmp`;
- coletar evidencia sanitizada;
- encerrar o servidor ao final.

## 3. Fora de escopo

C9.0 nao:

- implementou Wi-Fi real;
- criou hotspot;
- criou portal definitivo;
- alterou NetworkManager;
- executou `nmcli`;
- alterou config real;
- rodou writer;
- tocou `/data/config/config.json`;
- tocou backups;
- parou ou iniciou `kiosky-player.service`;
- alterou player;
- alterou o repo `kiosky-player`;
- publicou IP, valores privados, payload ou logs brutos;
- liberou producao.

## 4. Execucao

Servidor temporario:

```text
/tmp/dadooh-c9-0/totem_setup_minimal_server.py
```

Out-dir da candidata:

```text
/tmp/dadooh-c9-0-setup-lan/
```

Porta usada:

```text
8780
```

A porta foi exposta temporariamente em todas as interfaces da placa para
acesso pela rede local de bancada. O IP da placa nao foi registrado na
evidencia.

## 5. Resultado

Resultado sanitizado:

- servidor temporario subiu;
- home do setup respondeu localmente;
- humano foi orientado a acessar pelo navegador;
- nenhum bloqueio de UI foi reportado;
- candidata de teste foi gerada;
- rotacao de teste: `portrait_left`;
- artefatos de candidata ficaram apenas em `/tmp`;
- `kiosky-player.service` permaneceu `active`;
- servidor temporario foi encerrado ao final;
- producao continua bloqueada.

## 6. Evidencia sanitizada

Artefatos na placa:

```text
/tmp/dadooh-c9-0/access-status.json
/tmp/dadooh-c9-0/summary.txt
/tmp/dadooh-c9-0-setup-lan/candidate-config.json
/tmp/dadooh-c9-0-setup-lan/status.json
/tmp/dadooh-c9-0-setup-lan/summary.txt
```

Permissoes:

- diretorios `0700`;
- arquivos `0600`.

Status e summary publicam apenas categorias, booleans e decisoes. A candidata
de teste permanece em `/tmp` e nao e tratada como config real.

## 7. Privacidade

C9.0 nao publicou:

- IP da placa;
- `api_url`;
- `api_key`;
- `environment_id` real;
- payload;
- logs brutos;
- SSID;
- hostname;
- gateway;
- dados de rede;
- conteudo de config real;
- conteudo de backup.

## 8. Guardrails

Guardrails confirmados:

- `config_real_changed=false`;
- `writer_called=false`;
- `data_config_touched=false`;
- `backups_touched=false`;
- `systemctl_state_change_called=false`;
- `player_service_changed=false`;
- `networkmanager_changed=false`;
- `nmcli_called=false`;
- `wifi_changed=false`;
- `hotspot_created=false`;
- `portal_created=false`;
- `player_repo_touched=false`;
- `private_values_used=false`;
- `production_released=false`;
- `server_permanent=false`;
- `server_closed=true`.

## 9. Criterios de aceite

Criterios atendidos:

- setup rodou temporariamente na placa;
- setup ficou acessivel por navegador na rede local de bancada;
- candidata foi gerada somente em `/tmp`;
- servidor foi encerrado ao final;
- servico do player permaneceu ativo;
- nenhuma config real foi alterada;
- NetworkManager/rede/Wi-Fi nao foram alterados;
- evidencia sanitizada nao contem valores privados, IP, payload ou logs brutos;
- producao continua bloqueada.

## 10. Limitacoes

- A validacao humana nao registrou uma revisao detalhada de copy/UX; apenas nao
  houve bloqueios reportados.
- O acesso temporario ainda nao e portal definitivo.
- O acesso por navegador externo e auxiliar. Ele nao substitui o setup local na
  propria tela HDMI do totem.
- Nao ha descoberta automatica, QR code, hotspot ou fluxo offline.
- Candidata gerada em C9.0 e mock/local e nao deve ser aplicada ao writer.

## 11. Proximo passo

Proximo passo recomendado:

- C9.1 - implementar setup local minimo na propria plaquinha, operavel pela
  tela HDMI com teclado USB, sem Chromium, desktop, compositor, Wi-Fi real,
  hotspot, writer ou config real.
