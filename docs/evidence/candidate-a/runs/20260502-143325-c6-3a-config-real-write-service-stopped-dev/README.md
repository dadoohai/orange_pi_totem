# C6.3A config real write - abortado no self-test do writer

Data: 2026-05-02

## Objetivo

Executar C6.3A: primeira escrita real de `/data/config/config.json` na placa de
desenvolvimento, com `kiosky-player.service` parado, backup restrito,
validacao antes/depois e evidencia sanitizada.

## Resultado

Execucao abortada na Fase 1 porque o self-test do writer falhou na placa de
desenvolvimento. A falha ocorreu antes de parar o servico e antes de qualquer
escrita real.

Nenhuma escrita real foi executada.

## Escopo

- Placa alvo: desenvolvimento, sem publicar IP ou hostname.
- Placa de homologacao: nao usada.
- SSH: usado somente para a placa de desenvolvimento.
- HDMI: informado como desconectado; o player nao seria iniciado nesta rodada.
- `/data`: nao escrito.
- `/data/config/config.json`: nao lido e nao escrito.
- Candidata real: conteudo nao lido.
- Token real: nao lido.
- Servico: nao parado, nao iniciado e nao reiniciado por esta tarefa.
- Player: nao iniciado por esta tarefa.

## Comandos locais rodados

Leitura local de documentos e scripts:

```sh
sed -n '1,280p' docs/product/32_C6_3_EXECUCAO_CONFIG_REAL_SERVICO_PARADO.md
sed -n '1,260p' docs/product/33_C6_2_2_WRITER_REAL_MODE_GUARDRAILS.md
sed -n '1,260p' docs/product/31_C6_3_CONFIG_REAL_PREFLIGHT_PLACA.md
sed -n '1,220p' docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md
sed -n '1,260p' docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md
sed -n '1,320p' docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md
sed -n '1,220p' docs/DECISIONS/ADR-0010-api-token-provisioning.md
sed -n '1,260p' scripts/board/totem_config_contract_validate.py
sed -n '1,620p' scripts/board/totem_config_writer_real.py
```

Checagens locais de acesso:

```sh
command -v sshpass || true
python3 - <<'PY'
# verificou se modulos Python de SSH estavam disponiveis localmente
PY
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=5 <dev-board> 'printf ok'
```

O alvo real nao e publicado nesta evidencia.

## Fase 0 - candidata real privada

Confirmacoes sem ler conteudo:

```text
candidate_path_under_tmp: true
candidate_exists: true
candidate_regular: true
candidate_mode: 600
candidate_owner_category: root
candidate_group_category: root
candidate_not_under_data: true
candidate_not_under_opt: true
candidate_not_under_home: true
candidate_inside_repo: false
```

Nao foram executados `cat`, `head`, `tail`, `jq`, `sed` ou `grep` no conteudo
da candidata.

## Fase 1 - scripts e self-tests

Scripts copiados para `/tmp` na placa:

```sh
scp scripts/board/totem_config_contract_validate.py scripts/board/totem_config_writer_real.py <dev-board>:/tmp/
```

Self-tests:

```sh
cd /tmp
python3 /tmp/totem_config_contract_validate.py --self-test
python3 /tmp/totem_config_writer_real.py --self-test
```

Resultado agregado:

```text
contract_validator_self_test: ok
writer_self_test: failed
```

Como o self-test do writer falhou, a execucao abortou antes de parar o servico
e antes de executar o writer real.

## Estado read-only do servico apos abortar

Consulta read-only, sem `journalctl`:

```text
service_is_active: active
service_active_state: active
service_sub_state: running
```

O servico nao foi parado por esta tarefa.

## Fases nao executadas

| Fase | Resultado |
| --- | --- |
| Fase 2 - preflight final read-only | nao executada |
| Fase 3 - parar servico | nao executada |
| Fase 4 - `real-dry-run` da candidata real | nao executada |
| Fase 5 - writer real | nao executada |
| Fase 6 - pos-validacao | nao executada |
| Fase 7 - rollback | nao necessario |

## Estado agregado

| Item | Resultado |
| --- | --- |
| servico parado antes da escrita | nao |
| `real-dry-run` passou | nao executado |
| backup criado | nao |
| escrita real executada | nao |
| permissoes observadas | candidata: mode `600`; config real nao verificada nesta tentativa |
| leitura por `totem` | nao verificada nesta tentativa |
| gravacao por `totem` | nao verificada nesta tentativa |
| rollback | nao necessario |
| servico final | active/running; nao alterado por esta tarefa |
| player iniciado | nao por esta tarefa |
| nenhum secret publicado | sim |

## Confirmacoes de privacidade

- Conteudo da candidata real nao foi lido.
- Conteudo da config ativa real nao foi lido.
- Conteudo de backup nao foi lido.
- `api_key`/token nao foi publicado.
- `api_url` real nao foi publicada.
- `environment_id` real nao foi publicado.
- `station_id` real nao foi publicado.
- IP, hostname, MAC, BSSID, gateway, DNS, SSID, senha e payload nao foram
  publicados nesta evidencia.
- Nenhum output bruto com secrets foi versionado.

## Confirmacoes operacionais

- Nada foi escrito em `/data`.
- `/data/config/config.json` nao foi lido.
- `/data/config/config.json` nao foi escrito.
- `/data/config` nao foi criado.
- Config real nao foi alterada.
- Backup real nao foi criado.
- `kiosky-player.service` nao foi parado.
- `kiosky-player.service` nao foi iniciado.
- `kiosky-player.service` nao foi reiniciado.
- Launcher nao foi alterado.
- Renderer nao foi alterado.
- Unit `systemd` nao foi alterada permanentemente.
- `kiosky-player` nao foi alterado.
- NetworkManager nao foi alterado.
- `nmcli` nao foi executado.
- `journalctl` nao foi executado.
- Backend/internet nao foram testados.
- Nenhum pacote foi instalado.

## Conclusao

C6.3A foi abortada por gate de seguranca na Fase 1. A primeira escrita real em
`/data/config/config.json` continua pendente.

## Proximos passos

- Corrigir a falha do self-test do writer na placa ou criar diagnostico
  sanitizado especifico para a falha.
- Repetir C6.3A desde a Fase 0.
- Nao reutilizar esta tentativa como evidencia de escrita real.
- Manter a regra de nao iniciar o servico ao final da proxima tentativa, salvo
  nova autorizacao humana explicita.
