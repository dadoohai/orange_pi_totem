# C5 - config writer mock

Status: base mock local. Nao implementa escrita real de config.

Data: 2026-05-02

## Objetivo

C5 cria a primeira base de validacao e escrita simulada de uma configuracao
minima do player. O objetivo e:

- validar o fluxo de montagem de config minima;
- validar o formato de `environment_id`;
- simular `api_key` fora da UI;
- escrever apenas artefatos mock em `/tmp`;
- preparar C6 config real;
- nao alterar config real.

C5 nao libera producao e nao substitui C6. A fase existe para provar formato,
guardrails e evidencia antes de tocar em `/data/config/config.json`.

## Diferenca entre C5 e C6

### C5 - mock

- Usa somente `/tmp`.
- Usa placeholders.
- Nao usa secrets.
- Nao acessa backend.
- Nao escreve em `/data`.
- Nao altera config ativa.
- Nao altera launcher, renderer, `systemd` ou `kiosky-player`.

### C6 - futuro writer real

- Podera escrever `/data/config/config.json`.
- Devera validar permissao, ownership e paths reais.
- Devera usar escrita atomica.
- Devera preservar ultima config valida quando existir.
- Devera ter rollback documentado.
- Devera validar a config real completa antes de iniciar o player.

## Entradas permitidas em C5

C5 aceita somente entradas mock ou placeholders:

- `environment_id` mock;
- `api_key` mock placeholder;
- `api_url` mock invalida ou placeholder;
- `station_id` mock opcional;
- paths mock alinhados com appliance, mas sem acessar `/data`.

Mesmo quando a config candidata contem strings como `/data/media/kiosky-player`,
esses valores sao apenas forma futura da config. C5 nao cria, le ou escreve
esses paths.

## Entradas proibidas

C5 nao pode receber, gravar, imprimir em evidencia ou tratar como dado valido:

- `api_key` real;
- `api_url` privada;
- `environment_id` real;
- `station_id` real;
- qualquer secret;
- qualquer path real privado;
- qualquer payload de backend.

## Validacao de environment_id

C5 usa a regra provisoria definida em C2, sem validacao backend:

- aplicar trim;
- rejeitar valor vazio;
- minimo de 3 caracteres;
- maximo de 128 caracteres;
- caracteres permitidos: letras ASCII, numeros, `_`, `-`, `.`, `:`;
- sem espacos internos;
- sem validacao backend nesta fase.

Tambem sao recusados valores com aparencia sensivel ou operacional indevida,
incluindo URL, `api_key`, token, secret, password, senha, `/`, `/data/`,
`/opt/`, `/home/` ou caracteres fora da allowlist.

## Escrita mock

O writer C5 deve:

- escrever somente em `/tmp`;
- criar arquivo candidato mock;
- criar relatorio/status mock;
- usar escrita atomica mesmo no mock;
- recusar `--out-dir` fora de `/tmp`;
- gerar diretorio com permissao `700`;
- gerar arquivos com permissao `600`;
- nao escrever `/data`;
- nao criar `/data`;
- nao ler config real;
- nao chamar rede, `nmcli`, `systemctl` ou MPV.

Arquivos esperados:

- `config.candidate.mock.json`;
- `writer-status.json`;
- `summary.txt`.

## Campos minimos esperados

A config real futura provavelmente precisara conter estes campos minimos:

- `api_url`;
- `api_key`;
- `environment_id`;
- `cache_dir`;
- `state_dir`;
- `status_file`;
- `ipc_path`;
- `runtime_dir`;
- `strict_paths_enabled`;
- flags MPV candidatas da RC1 quando aplicavel:
  - `mpv_query_uses_fresh_ipc`;
  - `mpv_vo`;
  - `mpv_gpu_context`;
  - `mpv_ao`;
  - `low_resource_mode`.

Em C5 todos os valores devem ser mock ou placeholders. O placeholder aprovado
para `api_key` e `API_KEY_MOCK_NOT_FOR_PRODUCTION`; a `api_url` mock pode usar
dominio `.invalid`.

## Criterios de aceite

- `--self-test` ok.
- Config mock gerada em `/tmp`.
- Schema minimo validado.
- `environment_id` invalido falha.
- `--out-dir` fora de `/tmp` falha.
- Nenhum secret real.
- Nada em `/data`.
- Config real nao alterada.
- Launcher, renderer, `systemd` e `kiosky-player` nao alterados.
- `git diff --check` limpo.

## Criterios de bloqueio

- Qualquer escrita em `/data`.
- Qualquer secret real.
- Qualquer `api_url` privada.
- Qualquer `environment_id` real.
- Qualquer alteracao no player, launcher, renderer ou `systemd`.
- Qualquer alteracao em NetworkManager.
- Qualquer config parcial tratada como real.
- Qualquer evidencia com payload de backend ou dado privado.

## Como C5 prepara C6

C5 deixa pronto o contrato minimo para C6 sem executar escrita real:

- formato local de `environment_id`;
- shape inicial da config candidata;
- escrita atomica;
- permissoes restritivas;
- recusa de diretorio fora de `/tmp`;
- status/summary sanitizados;
- evidencia local sem secrets.

Antes de C6 ainda e necessario decidir a origem real da `api_key`, a validacao
real completa, ownership/permissoes de `/data/config/config.json`, rollback e
criterios de inicio do player apos config valida.
