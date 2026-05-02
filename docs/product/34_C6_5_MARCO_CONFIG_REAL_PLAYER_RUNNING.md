# C6.5 - marco config real + player_running

Status: marco de desenvolvimento. Nao e homologacao e nao libera producao.

Data: 2026-05-02

## 1. Objetivo

C6.5 consolida o marco de desenvolvimento C6 depois da escrita real de config
e do start controlado do servico na placa de desenvolvimento.

Objetivos:

- consolidar o marco de desenvolvimento C6;
- registrar que a config real foi escrita, o servico foi iniciado e o estado
  publico chegou a `player_running`;
- separar desenvolvimento, homologacao e producao.

Este documento nao reescreve as etapas anteriores. C5, C5.1, C6.0, C6.1,
C6.2, C6.2.1, C6.2.2, C6.3-preflight, C6.3A e C6.4 permanecem como historico
e evidencia nos seus documentos proprios.

## 2. Linha do tempo curta

- C5 criou o writer mock em `/tmp`, sem secrets e sem alterar config real.
- C5.1 criou o contrato minimo e o validador dry-run, com
  `--real-dry-run` bloqueando placeholders.
- ADR-0010 definiu token/API como credencial de runtime do totem, com
  provisionamento local privado em desenvolvimento.
- C6.2 implementou o writer real em modo simulado, ainda somente em `/tmp`.
- C6.2.1 executou smoke do writer na placa de desenvolvimento, ainda em
  `/tmp` e sem tocar `/data`.
- C6.2.2 adicionou guardrails para modo real: flags explicitas, destino real
  exato, backup-dir restrito e candidata privada sob `/tmp`.
- C6.3-preflight fez inspecao read-only na placa, sem ler a config real, e
  identificou que a escrita deveria ocorrer com o servico parado ou bloqueado.
- C6.3A executou a escrita real com `kiosky-player.service` parado.
- C6.4 iniciou o servico controladamente com a config real e observou smoke
  curto ate `player_running`.

Evidencias principais:

- [C6.3A - config real com servico parado](../evidence/candidate-a/runs/20260502-153430-c6-3a-config-real-write-service-stopped-dev/README.md)
- [C6.4 - start controlado com config real](../evidence/candidate-a/runs/20260502-155523-c6-4-service-start-config-real-dev/README.md)

## 3. O que foi provado

- Config real escrita em `/data/config/config.json`.
- Backup criado.
- Permissoes observadas da config ativa: `root:totem` `0640`.
- Usuario `totem` consegue ler e nao consegue gravar a config.
- `real-dry-run` passou antes da escrita real.
- Servico iniciado controladamente em C6.4.
- Launcher aceitou a config real.
- Estado publico chegou a `player_running`.
- Playback ficou em `playing`.
- MPV ficou ativo.
- `kiosk.py` ficou ativo.
- `NRestarts=0` no observer curto de 120s.
- Renderer junto com player nao foi observado na checagem final.
- Evidencia foi registrada sem secrets, sem conteudo da config real, sem
  `api_key`, sem `api_url` real, sem IDs reais e sem payload.

## 4. O que NAO foi provado

- Estabilidade por 30-60 minutos.
- Estabilidade por varias horas.
- Reboot/autoboot com config real.
- Comportamento com API indisponivel.
- Comportamento com rede oscilando.
- Cache/offline em longa duracao.
- Segunda placa/cartao.
- Root read-only.
- Corte seco.
- Rollback real acionado por falha.
- Producao/campo.

## 5. Decisao

- Nao executar observer prolongado agora como parte desta consolidacao.
- Mover testes longos para fila de homologacao paralela.
- Considerar C6.4 como smoke curto aprovado em desenvolvimento.
- Manter producao bloqueada.

C6.4 prova que o caminho config real + start controlado + `player_running`
funcionou em desenvolvimento por uma janela curta. Isso nao substitui
homologacao, teste prolongado, segunda placa/cartao, reboot/autoboot, root
read-only, corte seco ou validacao de campo.

## 6. Estado atual

- O servico foi mantido rodando ao final de C6.4.
- A config real esta ativa na placa de desenvolvimento.
- Esse estado vale para desenvolvimento, nao producao.
- A homologacao `v0.1-rc1` continua frente separada.

## 7. Proximos caminhos possiveis

Opcoes possiveis, sem decisao automatica:

- C7 status/diagnostico de config real e appliance.
- C8 rollback/parada controlada.
- UX/setup/onboarding.
- `player_error`.
- Integracao writer/onboarding.
- Update/rollback.
- Fila de homologacao.

A escolha da proxima frente deve preservar a separacao entre desenvolvimento
incremental, homologacao `v0.1-rc1` e producao futura.

## 8. Criterios de nao regressao

- Config real nao entra no Git.
- Evidencias nao contem `api_key`, `api_url`, IDs reais, payloads privados ou
  secrets.
- Renderer nao roda junto com player.
- Servico nao entra em restart loop.
- Player nao inicia com config invalida.
- Testes longos devem ser tratados como homologacao separada.
