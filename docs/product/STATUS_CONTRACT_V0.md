# Status contract v0

Status: contrato publico proposto para Fase A. Nao implementa mudancas.

Data: 2026-05-01

## Objetivo

Definir um JSON sanitizado para representar o estado agregado do appliance. O
contrato e publico por padrao: pode ser usado por status/splash, manutencao
local futura, diagnostico sanitizado e telemetria futura.

Este contrato nao e um dump dos arquivos internos do launcher ou do player. Um
agregador deve ler as fontes locais, reduzir os dados e publicar apenas campos
seguros.

## Regras de seguranca

O JSON v0 nunca deve conter:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`;
- URLs privadas;
- payloads privados;
- paths reais de midia;
- nomes privados de arquivos, campanhas, ambientes ou unidades;
- SSID;
- senha ou material derivado de senha;
- IP publico;
- tokens, headers ou cookies.

Campos livres como `public_message`, `action_hint` e `device_label` devem ser
montados a partir de textos publicos controlados. Eles nao devem receber texto
bruto de excecoes, respostas de API, paths ou config.

## Documento JSON

Campos obrigatorios:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `schema_version` | string | Versao do contrato. Valor v0: `totem-status.v0`. |
| `updated_at` | string | Timestamp RFC 3339. UTC preferencial; offset local aceito na transicao. |
| `state` | string | Estado publico agregado. |
| `display_connected` | boolean ou null | `true`, `false` ou `null` quando desconhecido. |
| `network_state` | string | Estado publico de rede. |
| `config_state` | string | Estado publico de configuracao. |
| `player_state` | string | Estado publico do player. |
| `service_state` | string | Estado publico do servico/launcher. |
| `error_code` | string ou null | Codigo estavel e sanitizado. |
| `public_message` | string | Mensagem curta para operador. |
| `action_hint` | string | Dica curta e nao sensivel. |
| `version` | object | Versoes publicas, sem secrets. |

Campos opcionais:

| Campo | Tipo | Descricao |
| --- | --- | --- |
| `device_label` | string | Rotulo publico do dispositivo, se configurado sem segredo. |

## Estados

`state` pode assumir os valores iniciais:

- `booting`;
- `display_missing`;
- `config_missing`;
- `starting_player`;
- `player_running`;
- `player_error`;
- `maintenance_placeholder`.

`network_state` pode assumir:

- `unknown`;
- `offline`;
- `limited`;
- `online`;
- `setup_pending`.

Na Fase A, `unknown` e aceitavel quando a camada visual ainda nao mede rede.

`config_state` pode assumir:

- `unknown`;
- `missing`;
- `invalid`;
- `valid`.

`player_state` pode assumir:

- `not_started`;
- `starting`;
- `running`;
- `error`;
- `stopped`.

`service_state` pode assumir:

- `unknown`;
- `inactive`;
- `activating`;
- `active`;
- `failed`.

`error_code` deve ser `null` quando nao ha erro publico. Codigos iniciais:

- `DISPLAY_MISSING`;
- `CONFIG_MISSING`;
- `CONFIG_INVALID`;
- `PLAYER_EXITED`;
- `PLAYER_STATUS_STALE`;
- `SERVICE_FAILED`;
- `UNKNOWN_ERROR`.

## Version info

O objeto `version` deve conter apenas identificadores publicos de software ou
imagem. Valores desconhecidos devem usar `null` ou `"unknown"`.

Exemplo:

```json
{
  "image": "unknown",
  "launcher": "foundation-v0.1",
  "player": "unknown",
  "contract": "totem-status.v0"
}
```

Nao incluir branch privada, path local, URL de origem, token de update, hash de
payload privado ou identificador de ambiente.

## Exemplos

### display_missing

```json
{
  "schema_version": "totem-status.v0",
  "updated_at": "2026-05-01T12:00:00Z",
  "state": "display_missing",
  "display_connected": false,
  "network_state": "unknown",
  "config_state": "unknown",
  "player_state": "not_started",
  "service_state": "active",
  "error_code": "DISPLAY_MISSING",
  "public_message": "Tela nao detectada",
  "action_hint": "Verifique o cabo HDMI e a energia da tela.",
  "device_label": "Totem Dadooh",
  "version": {
    "image": "unknown",
    "launcher": "foundation-v0.1",
    "player": "unknown",
    "contract": "totem-status.v0"
  }
}
```

### config_missing

```json
{
  "schema_version": "totem-status.v0",
  "updated_at": "2026-05-01T12:01:00Z",
  "state": "config_missing",
  "display_connected": true,
  "network_state": "unknown",
  "config_state": "missing",
  "player_state": "not_started",
  "service_state": "active",
  "error_code": "CONFIG_MISSING",
  "public_message": "Configuracao pendente",
  "action_hint": "Acione a manutencao autorizada para concluir a ativacao.",
  "device_label": "Totem Dadooh",
  "version": {
    "image": "unknown",
    "launcher": "foundation-v0.1",
    "player": "unknown",
    "contract": "totem-status.v0"
  }
}
```

### starting_player

```json
{
  "schema_version": "totem-status.v0",
  "updated_at": "2026-05-01T12:02:00Z",
  "state": "starting_player",
  "display_connected": true,
  "network_state": "unknown",
  "config_state": "valid",
  "player_state": "starting",
  "service_state": "active",
  "error_code": null,
  "public_message": "Iniciando exibicao",
  "action_hint": "Aguarde alguns instantes.",
  "device_label": "Totem Dadooh",
  "version": {
    "image": "unknown",
    "launcher": "foundation-v0.1",
    "player": "unknown",
    "contract": "totem-status.v0"
  }
}
```

### player_running

```json
{
  "schema_version": "totem-status.v0",
  "updated_at": "2026-05-01T12:03:00Z",
  "state": "player_running",
  "display_connected": true,
  "network_state": "unknown",
  "config_state": "valid",
  "player_state": "running",
  "service_state": "active",
  "error_code": null,
  "public_message": "Exibicao em andamento",
  "action_hint": "Nenhuma acao necessaria.",
  "device_label": "Totem Dadooh",
  "version": {
    "image": "unknown",
    "launcher": "foundation-v0.1",
    "player": "unknown",
    "contract": "totem-status.v0"
  }
}
```

### player_error

```json
{
  "schema_version": "totem-status.v0",
  "updated_at": "2026-05-01T12:04:00Z",
  "state": "player_error",
  "display_connected": true,
  "network_state": "unknown",
  "config_state": "valid",
  "player_state": "error",
  "service_state": "active",
  "error_code": "PLAYER_EXITED",
  "public_message": "Exibicao temporariamente indisponivel",
  "action_hint": "O sistema tentara reiniciar automaticamente.",
  "device_label": "Totem Dadooh",
  "version": {
    "image": "unknown",
    "launcher": "foundation-v0.1",
    "player": "unknown",
    "contract": "totem-status.v0"
  }
}
```
