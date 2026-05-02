# C5.1 config contract validator - local

Data: 2026-05-02

## Objetivo

Validar localmente C5.1: contrato minimo da config candidata e validador
dry-run, sem placa, sem SSH, sem rede real, sem secrets reais, sem leitura de
config real e sem escrita em `/data`.

## Escopo

- Modo: local/dry-run.
- Writer C5 usado apenas para gerar candidata mock em `/tmp`.
- Validador C5.1 usado apenas sobre candidata mock em `/tmp`.
- Config real: nao lida, nao escrita e nao alterada.
- Backend: nao acessado.
- NetworkManager: nao acessado.
- Player/launcher/renderer/`systemd`: nao alterados.
- Artefatos JSON de `/tmp`: nao versionados.

## Comandos rodados

```sh
python3 scripts/board/totem_config_writer_mock.py --environment-id ENVIRONMENT_ID_MOCK --out-dir /tmp/dadooh-c5-config-writer-mock
python3 scripts/board/totem_config_contract_validate.py --help
python3 scripts/board/totem_config_contract_validate.py --self-test
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c5-config-writer-mock/config.candidate.mock.json --allow-mock --out-dir /tmp/dadooh-c5-config-contract-allow-mock
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c5-config-writer-mock/config.candidate.mock.json --real-dry-run --out-dir /tmp/dadooh-c5-config-contract-real-dry-run
find /tmp/dadooh-c5-config-contract-allow-mock -maxdepth 1 -type f -printf '%f\n' | sort
stat -c '%a %n' /tmp/dadooh-c5-config-contract-allow-mock /tmp/dadooh-c5-config-contract-allow-mock/*
```

Inspecoes sanitizadas adicionais:

```sh
sed -n '1,120p' /tmp/dadooh-c5-config-contract-allow-mock/summary.txt
sed -n '1,160p' /tmp/dadooh-c5-config-contract-real-dry-run/summary.txt
sed -n '1,220p' /tmp/dadooh-c5-config-contract-real-dry-run/validation-status.json
if rg -q '<api_key-placeholder-value>' /tmp/dadooh-c5-config-contract-allow-mock /tmp/dadooh-c5-config-contract-real-dry-run; then echo 'validator-output-api-key-value-scan: failed'; exit 1; else echo 'validator-output-api-key-value-scan: ok'; fi
```

Na ultima inspecao, o padrao real usado localmente foi o placeholder mock
conhecido. O valor nao e repetido nesta evidencia.

## Resultado allow-mock

Comando:

```sh
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c5-config-writer-mock/config.candidate.mock.json --allow-mock --out-dir /tmp/dadooh-c5-config-contract-allow-mock
```

Resultado sanitizado:

```text
validation: passed
```

Resumo do `summary.txt`:

```text
mode: allow-mock
valid: true
missing_fields_count: 0
invalid_fields_count: 0
placeholder_findings_count: 4
api_key_present: true
api_key_value_written: false
candidate_config_copied: false
real_config_read: false
data_written: false
network_access: false
systemctl_called: false
nmcli_called: false
mpv_called: false
```

## Resultado real-dry-run

Comando:

```sh
python3 scripts/board/totem_config_contract_validate.py --candidate /tmp/dadooh-c5-config-writer-mock/config.candidate.mock.json --real-dry-run --out-dir /tmp/dadooh-c5-config-contract-real-dry-run
```

Resultado esperado:

```text
exit code: 2
validation: failed
```

Resumo do `summary.txt`:

```text
mode: real-dry-run
valid: false
missing_fields_count: 0
invalid_fields_count: 5
placeholder_findings_count: 4
api_key_present: true
api_key_value_written: false
candidate_config_copied: false
real_config_read: false
data_written: false
network_access: false
systemctl_called: false
nmcli_called: false
mpv_called: false
```

Motivos sanitizados no `validation-status.json`:

- `api_key`: placeholder bloqueado em `real-dry-run`;
- `api_url`: URL mock conhecida bloqueada em `real-dry-run`;
- `api_url`: dominio `.invalid` bloqueado em `real-dry-run`;
- `environment_id`: identificador mock conhecido bloqueado em
  `real-dry-run`;
- `station_id`: identificador mock conhecido bloqueado em `real-dry-run`.

## Arquivos gerados em /tmp

Arquivos em `/tmp/dadooh-c5-config-contract-allow-mock`:

```text
summary.txt
validation-status.json
```

Permissoes:

```text
700 /tmp/dadooh-c5-config-contract-allow-mock
600 /tmp/dadooh-c5-config-contract-allow-mock/summary.txt
600 /tmp/dadooh-c5-config-contract-allow-mock/validation-status.json
```

O validador tambem gerou os mesmos nomes de arquivos no diretorio
`/tmp/dadooh-c5-config-contract-real-dry-run`, sem copiar a config candidata.

## Privacidade

Confirmacoes:

- O valor de `api_key` nao foi impresso pelo validador.
- O valor de `api_key` nao foi salvo em `summary.txt` ou
  `validation-status.json`.
- O validador registrou apenas `api_key_present=true` e
  `api_key_placeholder_detected=true/false`.
- A config candidata nao foi copiada para o output do validador.
- Nenhum JSON gerado em `/tmp` foi versionado.
- Nenhum secret real foi usado.
- Nenhuma `api_url` privada foi usada ou publicada.
- Nenhum `environment_id` real foi usado ou publicado.
- Nenhum `station_id` real foi usado ou publicado.
- Nenhum SSID, senha Wi-Fi, IP, hostname, MAC, BSSID, gateway, DNS real,
  payload ou path privado foi usado ou publicado.

Scan sanitizado:

```text
validator-output-api-key-value-scan: ok
```

## Confirmacoes operacionais

- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi lido.
- `/data/config/config.json` nao foi escrito.
- Config real nao foi lida nem alterada.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- `systemd` nao foi alterado.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- Nenhum comando de Wi-Fi, hotspot, portal, MPV ou backend foi executado.
- Nenhum pacote foi instalado.

## Conclusao

C5.1 local foi aprovado como contrato e validador dry-run:

- config mock C5 passou em `--allow-mock`;
- config mock C5 falhou em `--real-dry-run`;
- a falha `real-dry-run` bloqueou placeholders;
- relatorios foram gerados somente em `/tmp`;
- permissoes observadas foram `700` para diretorio e `600` para arquivos;
- valor de `api_key` nao foi impresso nem salvo pelo validador;
- nenhuma config real foi lida, escrita ou alterada.

## Bloqueios antes de C6

- Definir origem real da `api_key`.
- Definir ownership e permissoes de `/data/config/config.json`.
- Definir backup/rollback para ultima config valida.
- Definir teste de queda de energia durante escrita real.
- Definir criterio para o launcher iniciar o player.
- Planejar C6.0 antes de qualquer escrita em `/data`.
- Executar C6.1 somente em placa de desenvolvimento, com revisao humana.
