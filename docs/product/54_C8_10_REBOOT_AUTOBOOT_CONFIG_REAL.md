# C8.10 - reboot/autoboot controlado com config real

Status: executado em desenvolvimento. Nao e producao.

Data: 2026-05-03

## 1. Objetivo

C8.10 validou que, apos reboot controlado, a placa de desenvolvimento sobe
sozinha com a config real escrita pelo fluxo C8 e retorna para
`player_running` sem intervencao manual.

A etapa nao alterou config, nao rodou writer, nao usou valores privados, nao
alterou rede/Wi-Fi, nao alterou o repo do player e nao liberou producao.

## 2. Pre-check antes do reboot

Antes do reboot, foi feita inspecao read-only com evidencia sanitizada:

- `kiosky-player.service` estava `enabled`;
- servico estava `active/running`;
- status publico estava `player_running`;
- playback estava `playing`;
- `mpv_running=true`;
- `NRestarts=0`;
- renderer nao estava ativo junto com player;
- config foi verificada apenas por metadados, sem ler conteudo.

Nao houve blockers no pre-check.

## 3. Reboot controlado

O reboot foi executado somente apos autorizacao humana explicita.

Foi usado reboot controlado por sistema, nao corte seco. A porta SSH caiu e
voltou, confirmando que a placa reiniciou e ficou acessivel novamente.

## 4. Resultado pos-boot

Observer curto pos-boot:

- SSH voltou;
- `kiosky-player.service` ficou `enabled`;
- servico ficou `active/running`;
- `NRestarts=0`;
- estado publico final: `player_running`;
- estado publico da config: `valid`;
- estado publico do player: `running`;
- playback: `playing`;
- `mpv_running=true`;
- processos por categoria:
  - `kiosk.py`: `1`;
  - MPV do player: `1`;
  - script renderer: `0`;
  - MPV do renderer: `0`.

## 5. Validacao visual humana

A validacao visual humana confirmou:

- midia visivel na tela apos reboot;
- nao apareceu tela de setup/status/erro depois do boot;
- a exibicao foi direto para as midias;
- terminal do Linux apareceu apenas durante desligamento/inicializacao do
  reboot, o que fica fora do player e nao bloqueia C8.10.

## 6. Evidencia sanitizada

Artefatos na placa:

```text
/tmp/dadooh-c8-10-autoboot/pre-reboot-status.json
/tmp/dadooh-c8-10-autoboot/pre-reboot-summary.txt
/tmp/dadooh-c8-10-autoboot/post-reboot-status.json
/tmp/dadooh-c8-10-autoboot/post-reboot-summary.txt
```

Permissoes:

- diretorio `0700`;
- arquivos `0600`.

Os artefatos registram apenas categorias, booleans, contadores e estados
publicos allowlisted.

## 7. Privacidade

C8.10 nao publicou:

- conteudo de `/data/config/config.json`;
- conteudo de backup;
- `api_url`;
- `api_key`;
- `environment_id` real;
- payload;
- logs brutos;
- linhas de comando brutas de processos;
- valores privados.

## 8. Guardrails

Guardrails confirmados:

- `config_content_read=false`;
- `backup_content_read=false`;
- `writer_called=false`;
- `private_values_read=false`;
- `network_changed=false`;
- `nmcli_called=false`;
- `upgrade_called=false`;
- `player_repo_touched=false`;
- `power_cut=false`;
- `production_released=false`;
- `raw_logs_copied=false`;
- `raw_process_cmdline_copied=false`.

## 9. Criterios de sucesso

Criterios atendidos:

- SSH voltou apos reboot;
- servico subiu automaticamente;
- servico ficou `active/running`;
- estado publico chegou a `player_running`;
- playback ficou `playing`;
- MPV do player ficou ativo;
- renderer ficou inativo junto com player;
- `NRestarts=0` no observer curto;
- midia apareceu visualmente na tela;
- evidencia sanitizada nao contem config, valores privados ou payload;
- producao continua bloqueada.

## 10. Riscos remanescentes

- Reboot/autoboot em placa de desenvolvimento nao substitui segunda
  placa/cartao.
- Ainda faltam observacoes mais longas.
- Ainda falta teste de rede oscilando/API indisponivel/cache/offline.
- Ainda falta criterio operacional de rollback real em falha futura.
- Producao continua bloqueada.

## 11. Proximos passos

Observacao ampliada de 30-60 minutos com config real e autoboot comprovado
pertence a fila de homologacao paralela, nao a uma nova etapa C8.11 de
desenvolvimento. Essa validacao continua obrigatoria antes de producao, mas nao
deve bloquear a sequencia incremental de produto/setup.

Proximo passo de desenvolvimento:

- C9.0 - acesso temporario ao setup pela rede local existente, sem Wi-Fi real,
  sem hotspot, sem portal definitivo, sem alterar config real e sem transformar
  o servidor em servico permanente.
