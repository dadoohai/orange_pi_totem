# C8.9 - start controlado pos-escrita real

Status: executado em desenvolvimento. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.9 iniciou `kiosky-player.service` de forma controlada usando a config real
escrita em C8.8, sem alterar config, sem rodar writer e sem usar valores
privados.

O objetivo era observar se o sistema convergia para `player_running` com smoke
curto e evidencia sanitizada.

## 2. Escopo executado

Foi permitido e executado:

- verificar metadados da config ativa sem ler conteudo;
- verificar estado inicial do servico;
- iniciar `kiosky-player.service`;
- observar `systemd`, launcher, status publico e processos por categorias;
- observar convergencia para `player_running`;
- executar smoke curto de estabilidade;
- preservar evidencia sanitizada em `/tmp`.

Nao foi executado:

- alteracao de config;
- writer C6;
- leitura de `/data/config/config.json`;
- leitura ou copia de backups;
- uso de valores privados;
- alteracao de Wi-Fi/rede;
- alteracao do repo `kiosky-player`;
- chamada manual de MPV;
- liberacao de producao.

## 3. Resultado

Resultado sanitizado da placa:

- start controlado: passou;
- smoke curto: passou;
- duracao do smoke: 120 segundos;
- amostras: 25;
- servico final: `active/running`;
- `NRestarts`: `0`;
- estado publico final: `player_running`;
- estado publico da config: `valid`;
- estado publico do player: `running`;
- playback: `playing`;
- `mpv_running`: `true`;
- processos por categoria:
  - `kiosk.py`: `1`;
  - MPV do player: `1`;
  - script renderer: `0`;
  - MPV do renderer: `0`.

## 4. Evidencia sanitizada

Artefatos na placa:

```text
/tmp/dadooh-c8-9-start-controlled/start-status.json
/tmp/dadooh-c8-9-start-controlled/summary.txt
```

Permissoes observadas:

- diretorio: `0700`;
- arquivos: `0600`.

Os artefatos registram apenas categorias, booleans, contadores e estados
publicos allowlisted.

## 5. Privacidade

C8.9 nao publicou:

- conteudo de `/data/config/config.json`;
- conteudo de backup;
- `api_url`;
- `api_key`;
- `environment_id` real;
- payload;
- logs brutos;
- linhas de comando brutas de processos;
- valores privados.

## 6. Guardrails

Guardrails confirmados:

- `config_content_read=false`;
- `writer_called=false`;
- `network_changed=false`;
- `production_released=false`;
- `raw_logs_copied=false`;
- `raw_process_cmdline_copied=false`.

O servico ficou ativo ao final porque a etapa aprovada era start controlado
pos-escrita real. Isso ainda nao equivale a producao.

## 7. Criterios de sucesso

Criterios atendidos:

- servico iniciou;
- servico nao entrou em restart loop;
- launcher aceitou a config;
- renderer nao ficou ativo junto com player;
- `kiosk.py` iniciou;
- MPV iniciou;
- estado publico chegou a `player_running`;
- `NRestarts=0` no smoke curto;
- evidencia sanitizada nao inclui valores privados;
- producao continua bloqueada.

## 8. Riscos remanescentes

- Smoke curto nao substitui teste prolongado.
- Ainda falta reboot/autoboot com a config escrita pelo fluxo C8.
- Ainda falta validacao em segunda placa/cartao.
- Ainda falta criterio operacional de rollback em falhas apos start.
- Producao continua bloqueada.

## 9. Proximo passo

Proximo passo recomendado:

- C8.10 - observacao curta ampliada ou reboot/autoboot controlado com config
  real, mantendo evidencia sanitizada e producao bloqueada.
