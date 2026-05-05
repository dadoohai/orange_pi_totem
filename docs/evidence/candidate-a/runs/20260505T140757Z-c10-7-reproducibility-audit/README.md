# C10.7 Reproducibility Audit Evidence

Data: 2026-05-05

Runner:

```bash
scripts/remote/run_c10_7_reproducibility_audit.sh
```

Rodada sanitizada local:

```text
/tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z/
```

Artefatos gerados em `/tmp`:

- `board-audit.json`
- `repo-audit.json`
- `compare.json`
- `compare.md`
- `README.md`

Esses artefatos foram gerados por auditoria read-only na placa dev
`root@192.168.1.147`. A senha foi usada apenas no prompt SSH interativo e nao
foi gravada em comando, arquivo, doc, stdout persistente ou artefato.

## Guardrails

A rodada nao executou:

- `apt upgrade`, `apt full-upgrade`, `apt dist-upgrade` ou `armbian-upgrade`;
- instalacao de pacotes;
- reboot;
- writer real;
- alteracao de config;
- alteracao de Wi-Fi/NetworkManager;
- stop/start de player;
- alteracao de `kiosky-player`;
- read-only;
- corte seco;
- coleta de logs brutos.

Nao foram publicados:

- config real;
- `api_key`;
- `api_url` real;
- `environment_id`;
- `station_id`;
- SSID;
- senha;
- IP;
- MAC;
- DNS;
- gateway;
- hostname;
- logs brutos;
- backup;
- payloads;
- arquivos privados de candidata.

## Resultado

Conclusao da auditoria: a placa dev esta operacional e amplamente descrita por
scripts/docs, mas ainda nao e totalmente reproduzivel por script a partir do
repo.

Bloqueios principais antes da segunda placa/cartao:

- falta instalador idempotente C10.8;
- falta pin/manifest verificavel do `kiosky-player`;
- ha drift entre placa, HEAD e worktree local em scripts/units;
- `dadooh-visual-splash.service` esta instalado na placa, mas nao existe como
  unit standalone versionada;
- estados privados como Wi-Fi dedicado, config real, secrets, midias/cache e
  logs runtime nao devem entrar na imagem.

Resumo de classificacoes:

```text
OK_VERSIONADO: 8
FALTA_SCRIPT_INSTALACAO: 7
ESTADO_PRIVADO_NAO_IMAGEM: 4
ESTADO_TEMPORARIO: 2
NAO_DEVE_ENTRAR_IMAGEM: 2
POSSIVEL_DRIFT_PLACA: 2
```

Relatorio principal:

```text
docs/product/85_REPRODUTIBILIDADE_PLACA_PARA_IMAGEM.md
```

## Comandos Principais

```bash
scripts/remote/run_c10_7_reproducibility_audit.sh root@192.168.1.147 --summary --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
scripts/remote/run_c10_7_reproducibility_audit.sh --audit-repo --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
scripts/remote/run_c10_7_reproducibility_audit.sh --compare --out-dir /tmp/dadooh-c10-7-reproducibility-audit/20260505T140757Z
```
