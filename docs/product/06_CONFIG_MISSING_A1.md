# Config Missing A1.3

Status: proposta implementada para validacao local e placa de desenvolvimento.

Data: 2026-05-01

## Objetivo

Adicionar uma barreira segura no launcher para detectar configuracao ausente ou
invalida antes de iniciar o `kiosky-player`.

A meta da A1.3 e produzir estado publico `config_missing` para operador e
manutencao futura, sem depender de terminal, sem renderer visual, sem iniciar
MPV extra e sem expor secrets.

## Comportamento esperado

Quando o display esta conectado:

1. O launcher valida a config.
2. Se a config for valida, segue o fluxo atual: `starting`, app, `running` e
   refresh periodico do agregador.
3. Se a config estiver ausente ou invalida:
   - grava status bruto `config_missing`;
   - chama o agregador;
   - gera `/tmp/dadooh-status/status.json`;
   - gera `/tmp/dadooh-status/status.svg`;
   - nao inicia `kiosk.py`;
   - nao inicia MPV;
   - mantem o servico `active`;
   - aguarda `KIOSKY_CONFIG_RETRY_SEC` e tenta novamente.

Quando o display esta ausente, o fluxo continua sendo `display_missing`. A1.3
nao muda essa prioridade.

## Entradas

- `KIOSKY_CONFIG_PATH`: caminho da config. Padrao:
  `/data/config/config.json`.
- `KIOSKY_CONFIG_RETRY_SEC`: intervalo de nova tentativa. Padrao: 5 segundos.
- Status bruto do launcher, escrito em `/data/state/kiosky-player` ou fallback
  em `/tmp`.
- Status do player em `/tmp/kiosky-status.json`, quando existir.

## Saidas

Status agregado publico esperado:

```json
{
  "state": "config_missing",
  "display_connected": true,
  "config_state": "missing",
  "player_state": "not_started",
  "service_state": "active",
  "error_code": "CONFIG_MISSING"
}
```

O JSON real contem tambem `schema_version`, `updated_at`, mensagens publicas e
versoes sanitizadas conforme `STATUS_CONTRACT_V0.md`.

## Validacao

A validacao do launcher e minima e nao imprime conteudo da config:

- arquivo existe;
- arquivo e legivel;
- JSON e valido;
- raiz do JSON e objeto;
- campos essenciais estao presentes e nao vazios.

Os valores de config nunca devem ser exibidos em stdout, journal, README ou
status publico. Em especial, nao publicar `api_url`, `api_key`,
`environment_id`, `station_id`, URLs, paths de midia ou payloads privados.

## Validacao local

O smoke local deve cobrir:

- config inexistente via `KIOSKY_CONFIG_PATH`;
- agregado final `config_missing`;
- app fake nao chamado;
- `/tmp` rejeitado como out-dir do agregador;
- subdiretorio de `/tmp` aceito;
- agregador ausente/lento nao derruba o fluxo;
- refresh periodico A1.2.1 ainda funciona quando app fake esta vivo.

## Validacao em placa

Na placa de desenvolvimento, a validacao deve usar override temporario de
`KIOSKY_CONFIG_PATH` para um caminho inexistente. A config real nao deve ser
removida, editada ou impressa.

Resultado esperado:

- servico `active`;
- estado publico `config_missing`;
- `kiosk.py=0`;
- `mpv=0`;
- `systemctl --failed=0`;
- `status.json` e `status.svg` gerados;
- sanitizacao OK.

Depois do teste, remover o override temporario e reiniciar o servico para
retornar ao fluxo normal.

## Proximos passos

A1.3 prepara o caminho para onboarding/manutencao futuro. Essa etapa futura
podera escrever uma config valida em `/data` por uma UX local controlada, com
validacao atomica e sem expor secrets ao operador.
