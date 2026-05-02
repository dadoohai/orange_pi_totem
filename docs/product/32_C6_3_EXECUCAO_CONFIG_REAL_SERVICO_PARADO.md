# C6.3.0 - plano de execucao real com servico parado

Status: plano documental. Nao executa escrita real.

Data: 2026-05-02

## 1. Objetivo

C6.3.0 planeja a primeira escrita real de `/data/config/config.json`, sem
executa-la nesta fase.

Objetivos:

- planejar primeira escrita real de `/data/config/config.json`;
- executar a C6.3A futura com `kiosky-player.service` parado ou bloqueado;
- preservar backup e rollback;
- validar pos-escrita;
- so iniciar player se decisao humana permitir.

C6.3.0 nao usa SSH, nao toca placa, nao executa `systemctl`, nao para servico,
nao escreve em `/data`, nao le conteudo de `/data/config/config.json`, nao usa
token real e nao altera launcher, renderer, `systemd`, NetworkManager ou
`kiosky-player`.

## 2. Por que servico parado

O C6.3-preflight read-only na placa de desenvolvimento confirmou que:

- `kiosky-player.service` esta `enabled` e `active/running`;
- o servico roda como `User=totem` e `Group=totem`;
- o launcher usa `/data/config/config.json` como config default;
- quando a config default e considerada valida, o launcher chama
  `run_app_once`.

Escrever uma config valida com o servico ativo pode iniciar o player antes de
completar revalidacao, evidencia e rollback. C6.3A deve impedir esse inicio
prematuro mantendo o servico parado ou usando bloqueio operacional equivalente
aprovado antes da escrita real em C6.3A.

## 3. Escopo de C6.3A futura

Inclui:

- parar `kiosky-player.service`;
- confirmar estado `inactive`;
- validar candidata real;
- criar backup da config atual;
- executar escrita atomica;
- aplicar permissoes `root:totem` `0640`;
- revalidar apos a escrita;
- decidir se o servico sera iniciado ou permanecera parado;
- executar rollback, se necessario;
- produzir evidencia sanitizada.

Fora de escopo:

- alterar launcher;
- alterar unit `systemd` permanentemente;
- alterar `kiosky-player`;
- testar backend;
- testar Wi-Fi;
- producao;
- placa de homologacao.

## 4. Pre-condicoes obrigatorias

Checklist antes de abrir a execucao real C6.3A:

- [ ] placa de desenvolvimento confirmada;
- [ ] acesso fisico disponivel;
- [ ] servico pode ser parado;
- [ ] candidato real preparado fora do Codex;
- [ ] token/`api_key` fora do Codex;
- [ ] `api_url` aprovada sem publicar valor;
- [ ] `environment_id` aprovado sem publicar valor;
- [ ] `station_id` aprovado ou dispensado;
- [ ] `real-dry-run` passa;
- [ ] backup aprovado;
- [ ] rollback aprovado;
- [ ] permissao `root:totem` `0640` aprovada;
- [ ] evidencia sanitizada aprovada.

Se qualquer item exigir publicar `api_key`, token, `api_url` real,
`environment_id` real, `station_id` real, payload, backup ou conteudo de config,
C6.3A deve abortar.

## 5. Sequencia planejada para C6.3A

Esta sequencia descreve passos futuros. Nada abaixo foi executado em C6.3.0.

### A. Preflight final

- copiar scripts para `/tmp`;
- validar writer e validator;
- confirmar que `kiosky-player.service` esta `active/running`;
- confirmar que `/data/config/config.json` existe sem ler conteudo.

### B. Parar servico

- executar `systemctl stop kiosky-player.service`;
- confirmar que o servico ficou `inactive`;
- se o servico nao parar, abortar sem escrever config real.

### C. Backup

- criar backup restrito da config atual;
- nao publicar conteudo do backup;
- registrar apenas `backup_criado=sim/nao`.

### D. Candidata real

- manter candidata real em arquivo privado local fora do Git, Codex e
  evidencia;
- validar candidata com `real-dry-run`;
- nao publicar valores reais.

### E. Escrita

- writer real escreve `/data/config/config.json`;
- escrita deve ser atomica, com temporario no mesmo diretorio;
- owner/group/mode devem seguir decisao aprovada;
- aplicar `fsync` de arquivo e diretorio.

### F. Pos-validacao

- revalidar config ativa;
- confirmar legivel por `totem`;
- confirmar nao gravavel por `totem`;
- confirmar placeholders ausentes;
- nao imprimir secrets.

### G. Decisao de servico

- opcao 1: manter servico parado e encerrar;
- opcao 2: iniciar servico controladamente e observar;
- opcao 3: executar rollback e voltar ao estado anterior.

O player so deve iniciar se houver aprovacao humana explicita para essa etapa.

### H. Evidencia

- criar README sanitizado da execucao;
- nao incluir candidata, config ativa, backup, tokens, URLs reais, IDs reais,
  payloads ou output bruto sensivel.

## 6. Rollback real

Rollback real deve ser usado se:

- a revalidacao pos-escrita falhar;
- permissao, owner ou grupo ficarem diferentes do aprovado;
- `totem` nao conseguir ler a config ativa;
- `totem` conseguir escrever a config ativa;
- placeholders forem detectados;
- a decisao humana pedir retorno ao estado anterior;
- houver incerteza sobre evidencia, secrets ou inicio do player.

Procedimento planejado:

1. manter `kiosky-player.service` parado;
2. restaurar o backup aprovado para `/data/config/config.json`;
3. aplicar owner/group/mode aprovados ao arquivo restaurado;
4. fazer `fsync` de arquivo e diretorio quando aplicavel;
5. revalidar a config restaurada sem imprimir conteudo;
6. confirmar que o servico permanece parado;
7. registrar em evidencia apenas estado agregado do rollback.

Se o backup nao existir, estiver invalido ou o rollback ficar incerto, C6.3A deve
abortar com o servico parado e registrar falha sanitizada sem iniciar player.

## 7. Evidencia sanitizada esperada

O README da C6.3A deve conter:

- objetivo;
- placa desenvolvimento;
- servico parado: `sim/nao`;
- `real-dry-run` passou;
- backup criado: `sim/nao`;
- escrita real: `sim/nao`;
- permissoes observadas;
- leitura por `totem`: `true/false`;
- gravacao por `totem`: `true/false`;
- rollback: `nao necessario/executado/falhou`;
- servico final: `parado/iniciado`;
- player iniciado: `sim/nao`;
- nenhum secret publicado;
- conclusao.

Proibido incluir:

- conteudo da config;
- `api_key`;
- `api_url` real;
- `environment_id` real;
- `station_id` real;
- backup;
- output bruto com secrets;
- journal/logs com valores privados.

## 8. Criterios de abortar

Abortar se:

- servico nao para;
- candidato real nao esta pronto;
- dados reais precisariam passar pelo Codex;
- `real-dry-run` falha;
- backup falha;
- permissoes nao podem ser aplicadas;
- owner/group esperado nao existe;
- rollback esta incerto;
- evidencia exigiria segredo;
- humano nao aprova iniciar servico.

Ao abortar:

- nao escrever config real se a falha ocorreu antes da escrita;
- manter ou retornar o servico para o estado seguro aprovado;
- nao iniciar player;
- nao publicar config, candidata, backup ou valores reais;
- registrar apenas evidencia sanitizada quando isso for seguro.

## 9. Decisoes humanas antes da execucao

Decisoes pendentes antes de executar C6.3A real:

- executar C6.3A com servico parado: `sim/nao`;
- ao final, manter servico parado ou iniciar;
- se iniciar, qual observer minimo;
- quem fornece candidata real;
- onde candidata real privada ficara temporariamente;
- quem remove candidata real temporaria;
- rollback automatico ou manual.

Recomendacao: executar C6.3A com `kiosky-player.service` parado, manter o player
parado ate a evidencia pos-escrita ser aprovada e so iniciar o servico em etapa
controlada separada, se houver decisao humana explicita.
