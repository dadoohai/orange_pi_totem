# C5 config writer mock - local

Data: 2026-05-02

## Objetivo

Validar localmente a primeira base C5 de montagem e escrita simulada de config
minima do player, sem placa, sem SSH, sem rede real, sem secrets e sem escrita
em `/data`.

## Escopo mock

- Modo: local/mock.
- Saida: `/tmp/dadooh-c5-config-writer-mock`.
- Script: `scripts/board/totem_config_writer_mock.py`.
- Config gerada: candidata mock, nao ativa.
- Backend: nao acessado.
- NetworkManager: nao acessado.
- Player/launcher/renderer/`systemd`: nao alterados.
- Arquivos mock de `/tmp`: nao versionados.

## Comandos rodados

```sh
python3 scripts/board/totem_config_writer_mock.py --help
python3 scripts/board/totem_config_writer_mock.py --self-test
python3 scripts/board/totem_config_writer_mock.py --environment-id ENVIRONMENT_ID_MOCK --out-dir /tmp/dadooh-c5-config-writer-mock
find /tmp/dadooh-c5-config-writer-mock -maxdepth 1 -type f -printf '%f\n' | sort
stat -c '%a %n' /tmp/dadooh-c5-config-writer-mock /tmp/dadooh-c5-config-writer-mock/*
```

Observacao: a listagem de arquivos foi registrada apos a geracao do diretorio
mock. Uma tentativa inicial paralela foi descartada por corrida local antes da
criacao do diretorio.

## Resultado local

Self-test:

```text
self-test: ok
```

Arquivos gerados em `/tmp/dadooh-c5-config-writer-mock`:

```text
config.candidate.mock.json
summary.txt
writer-status.json
```

Permissoes:

```text
700 /tmp/dadooh-c5-config-writer-mock
600 /tmp/dadooh-c5-config-writer-mock/config.candidate.mock.json
600 /tmp/dadooh-c5-config-writer-mock/summary.txt
600 /tmp/dadooh-c5-config-writer-mock/writer-status.json
```

## Entradas mock

- `environment_id`: `ENVIRONMENT_ID_MOCK`
- `api_key`: `API_KEY_MOCK_NOT_FOR_PRODUCTION`
- `api_url`: `https://api.example.invalid/search`
- `station_id`: `STATION_ID_MOCK`

## Resumo da config mock

A config candidata contem apenas placeholders e shape minimo esperado para C6:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`;
- `cache_dir`;
- `state_dir`;
- `status_file`;
- `ipc_path`;
- `runtime_dir`;
- `strict_paths_enabled`;
- `mpv_query_uses_fresh_ipc`;
- `mpv_vo`;
- `mpv_gpu_context`;
- `mpv_ao`;
- `low_resource_mode`.

Os paths de appliance dentro do JSON sao strings de formato futuro. O script C5
nao criou, leu ou escreveu esses paths.

## Confirmacoes operacionais

- Nada foi escrito em `/data`.
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

## Criterios de privacidade

Nao foram usados ou publicados:

- `api_key` real;
- `api_url` privada;
- `environment_id` real;
- `station_id` real;
- SSID, senha, IP, hostname, MAC, BSSID, gateway ou DNS real;
- payload de backend;
- path privado;
- token, header, cookie ou secret.

Os artefatos mock gerados em `/tmp` nao foram adicionados ao Git. Esta
evidencia versiona apenas o README sanitizado.

## Conclusao

C5 local foi aprovado como writer mock: self-test ok, config candidata mock
gerada em `/tmp`, schema minimo validado, permissoes restritivas observadas e
nenhum acesso ou escrita real de config executado.

## Bloqueios antes de C6

- Definir origem real da `api_key` fora da UI.
- Definir validacao completa da config real.
- Definir ownership e permissoes de `/data/config/config.json`.
- Definir rollback para ultima config valida.
- Definir tratamento de queda de energia durante escrita real.
- Definir quando o launcher podera iniciar o player apos config real valida.
- Revisar que nenhum placeholder C5 sera copiado para producao.
