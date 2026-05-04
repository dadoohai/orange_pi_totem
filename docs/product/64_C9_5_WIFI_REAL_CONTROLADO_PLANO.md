# C9.5 - Wi-Fi real controlado com NetworkManager adapter estreito

Status: implementado somente `--read-only` e `--plan`. `--apply` real continua
bloqueado e retorna erro claro em C9.5.

Data: 2026-05-04

## Objetivo

Preparar o proximo corte para configurar Wi-Fi real de forma controlada,
preservando Ethernet e mantendo diagnostico/evidencia sanitizados. C9.5 mede
estado agregado e gera plano; nao aplica rede real.

C9.5 nao implementa hotspot, portal, login, backend, writer, config real,
factory reset, reboot ou producao.

## Implementado

- `scripts/board/totem_wifi_nm_adapter.py`;
- `scripts/remote/run_c9_5_wifi_readonly_plan.sh`;
- artefatos sanitizados em `/tmp/dadooh-c9-5-wifi-readonly`;
- diretorios `0700` e arquivos `0600`;
- self-test com fixtures contendo valores fake sensiveis para provar que a
  saida publica nao copia valores brutos;
- bloqueio de comandos modificadores e `--apply` com `apply disabled in C9.5`.

Modos do adapter:

```text
--self-test
--read-only
--plan
--apply
```

`--apply` existe apenas como bloqueio defensivo. Ele nao recebe credenciais,
nao chama `nmcli` e nao altera rede.

## O que `--read-only` mede

Saida publica permitida, sempre agregada:

- NetworkManager disponivel: `true/false/unknown`;
- `nmcli` disponivel: `true/false`;
- dispositivo Wi-Fi presente: `true/false/unknown`;
- Ethernet ativa: `true/false/unknown`;
- Wi-Fi ativo: `true/false/unknown`;
- rota default presente: `true/false/unknown`, sem gateway;
- DNS configurado: `true/false/unknown`, sem servidor;
- conectividade: `not_checked`.

Nao ha chamada externa de conectividade por padrao.

## O que `--plan` prepara

O plano descreve sem executar:

- preservar Ethernet se ativa;
- criar perfil Wi-Fi dedicado do produto em rodada futura;
- nunca apagar conexao antiga antes de sucesso;
- testar nova conexao com timeout;
- rollback para estado anterior se falhar;
- nao logar credenciais;
- coletar evidencia sanitizada;
- exigir confirmacao humana explicita antes de qualquer apply;
- manter writer, config real, player e MPV fora do fluxo de rede;
- nao rebootar.

Valores privados ficam como:

```text
target_network: redacted
credentials_source: not_collected_in_c9_5
apply_enabled: false
```

## Dados proibidos

Status, summary, runner e evidencia nao devem publicar valores reais de:

- nome de rede;
- senha;
- IP;
- MAC/BSSID;
- gateway;
- DNS;
- hostname;
- nome real de conexao NetworkManager;
- logs brutos;
- cmdline sensivel.

## Validacao

Local:

```bash
bash -n scripts/remote/run_c9_5_wifi_readonly_plan.sh
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --read-only
python3 scripts/board/totem_wifi_nm_adapter.py --plan
python3 scripts/board/totem_wifi_nm_adapter.py --apply
```

Remoto:

```bash
scripts/remote/run_c9_5_wifi_readonly_plan.sh root@192.168.18.115 --prepare-only
scripts/remote/run_c9_5_wifi_readonly_plan.sh root@192.168.18.115 --read-only
scripts/remote/run_c9_5_wifi_readonly_plan.sh root@192.168.18.115 --plan
```

Resultado esperado:

- self-tests passam;
- `--read-only` e `--plan` geram artefatos sanitizados em `/tmp`;
- `--apply` falha com `apply disabled in C9.5`;
- nenhum comando modificador de rede e chamado;
- `/data/config/config.json`, writer, player, MPV, hotspot, portal e reboot
  continuam fora de escopo.

## Proximo passo

C9.6 deve implementar apply real controlado em bancada, somente com
confirmacao humana explicita, credencial fornecida por canal temporario seguro,
Ethernet preservada, perfil dedicado, timeout, teste de conexao e rollback.
