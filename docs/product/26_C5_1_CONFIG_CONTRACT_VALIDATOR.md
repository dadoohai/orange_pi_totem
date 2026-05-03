# C5.1 - contrato de config minima e validador dry-run

Status: contrato e validador local. Nao implementa escrita real de config.

Data: 2026-05-02

## Objetivo

C5.1 define o contrato minimo da config candidata e cria um validador dry-run
para preparar C6 com mais seguranca.

Objetivos:

- definir contrato minimo da config candidata;
- validar config candidata em dry-run;
- preparar C6;
- impedir que placeholder C5 vire config real;
- nao escrever em `/data`.

C5.1 nao e C6. C5.1 nao escreve `/data/config/config.json`, nao le config real,
nao inicia o player, nao altera estado operacional, nao usa secrets reais e nao
substitui a validacao em placa de desenvolvimento que ainda sera necessaria em
C6.

## Diferenca entre C5, C5.1 e C6

### C5 - writer mock

- Gera `config.candidate.mock.json` em `/tmp`.
- Usa placeholders.
- Nao escreve `/data`.
- Nao le config real.
- Nao altera launcher, renderer, `systemd`, NetworkManager ou
  `kiosky-player`.
- Prepara C6, mas nao substitui C6.

### C5.1 - contrato e dry-run

- Valida uma config candidata em dry-run.
- Escreve apenas `validation-status.json` e `summary.txt` em `/tmp`.
- Nao copia a config candidata para o output.
- Nao cria paths de appliance.
- Nao le `/data/config/config.json`.
- Em `--allow-mock`, aceita placeholders C5 para validar shape.
- Em `--real-dry-run`, bloqueia placeholders antes de C6.

### C6 - writer real futuro

- Podera escrever `/data/config/config.json`.
- Devera validar ownership, permissoes, backup, rollback e queda de energia.
- Devera usar escrita atomica.
- Devera preservar ultima config valida quando existir.
- Devera iniciar o player somente depois de config real valida.

## Campos obrigatorios

A config candidata minima deve conter:

- `api_url`;
- `api_key`;
- `environment_id`;
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

Campo opcional/futuro:

- `station_id`.

`station_id` nao e requisito bloqueante da config minima nesta etapa. Quando
presente, ele deve seguir a allowlist de identificadores para nao carregar URL,
path ou segredo por engano. Quando ausente, vazio ou mock, nao bloqueia
`real-dry-run`. O uso esperado fica ligado a telemetria/inventario futuro, nao
ao playback minimo.

## Regras de paths

Para perfil appliance:

- `cache_dir` deve estar sob `/data/media`;
- `state_dir` deve estar sob `/data/state`;
- `status_file` deve estar sob `/tmp`;
- `ipc_path` deve estar sob `/tmp`;
- `runtime_dir` deve estar sob `/tmp`;
- `log_file`, se existir, deve estar vazio ou sob `/data/logs`;
- `mpv_log_file`, se existir, deve estar vazio, sob `/tmp` ou sob
  `/data/logs`.

C5.1 so valida strings. C5.1 nao cria esses paths, nao testa permissao real
desses paths e nao escreve em `/data`.

## Regras de placeholders

### Modo mock

Em modo `--allow-mock`, placeholders sao permitidos. Esse modo existe para
validar se a config mock C5 tem o shape minimo esperado, sem tratar os valores
como producao.

### Modo real-dry-run

Em modo `--real-dry-run`, o validador deve bloquear:

- `API_KEY_MOCK_NOT_FOR_PRODUCTION`;
- `https://api.example.invalid/search`;
- `ENVIRONMENT_ID_MOCK`;
- dominios `.invalid`;
- valores vazios;
- `api_key` com rotulo de mock, test, example ou placeholder;
- `environment_id` que pareca URL, path ou secret;
- `station_id` que pareca URL, path ou secret, quando o campo opcional estiver
  presente.

O modo `--real-dry-run` ainda nao prova que a `api_key` e correta, que o
backend aceita a config ou que o ambiente existe. Ele apenas bloqueia sinais
obvios de mock/placeholder antes de C6.

## Regras de environment_id

C5.1 reutiliza a regra C5, sem validacao backend:

- aplicar trim;
- nao vazio;
- minimo de 3 caracteres;
- maximo de 128 caracteres;
- caracteres permitidos: letras ASCII, numeros, `_`, `-`, `.`, `:`;
- sem espacos internos;
- sem validacao backend.

Tambem devem ser bloqueados valores que parecam URL, path, token, secret,
password, senha ou `api_key`.

## Regras de api_key

C5.1 nao valida segredo real por conteudo sensivel. O validador deve:

- exigir string nao vazia em `--real-dry-run`;
- bloquear placeholders conhecidos;
- nao imprimir o valor;
- nunca salvar `api_key` em `summary.txt`;
- registrar apenas `present: true/false` e
  `placeholder_detected: true/false`.

O operador continua sem digitar `api_key` na UI. A origem real da `api_key`
segue pendente antes de C6.

## Saidas

O validador C5.1 gera, por padrao, em
`/tmp/dadooh-c5-config-contract-validate`:

- `validation-status.json`;
- `summary.txt`.

Regras de saida:

- diretorio com permissao `700`;
- arquivos com permissao `600`;
- `--out-dir` fora de `/tmp` falha;
- nunca copiar config candidata para o Git;
- nunca copiar config candidata para o output do validador;
- nunca imprimir secrets;
- nunca salvar valor de `api_key` em `summary.txt`;
- status registra apenas campos agregados, campos ausentes, campos invalidos,
  achados de placeholder, achados de path, presenca de `api_key`, flags de
  privacidade, estado de `environment_id` e estado opcional de `station_id`.

## Criterios de aceite

- Config mock C5 passa em modo `--allow-mock`.
- Config mock C5 falha em modo `--real-dry-run`.
- `--out-dir` fora de `/tmp` falha.
- Config com campo ausente falha.
- Path invalido falha.
- `api_key` placeholder falha em `--real-dry-run`.
- Nenhum secret e impresso.
- Nada em `/data`.

## Bloqueios antes de C6

Antes de C6 ainda precisam ser decididos ou validados:

- origem real da `api_key`;
- ownership/permissao de `/data/config/config.json`;
- backup/rollback;
- queda de energia durante escrita;
- criterio para o launcher iniciar player;
- teste em placa de desenvolvimento.

## Criterios de rollback

Rollback de C5.1 e documental/local:

- remover `scripts/board/totem_config_contract_validate.py` se a abordagem for
  rejeitada;
- remover este documento se o contrato for substituido;
- apagar apenas artefatos temporarios em `/tmp`;
- nao executar acao em `/data`, NetworkManager, launcher, renderer, `systemd`
  ou `kiosky-player`.
