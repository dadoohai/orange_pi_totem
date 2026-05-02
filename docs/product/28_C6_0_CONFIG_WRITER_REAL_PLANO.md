# C6.0 - plano de escrita real da config

Status: planejamento. Nao executa escrita real.

Data: 2026-05-02

## Objetivo

C6.0 planeja a primeira escrita real de `/data/config/config.json`, sem
executa-la nesta fase.

Objetivos:

- planejar a primeira escrita real de `/data/config/config.json`;
- definir pre-condicoes, validacao, backup, rollback, permissoes e criterios de
  inicio do player;
- nao executar escrita real nesta fase.

C6.0 nao escreve em `/data`, nao le `/data/config/config.json`, nao toca na
placa, nao altera config real, nao inicia player, nao altera launcher,
renderer, `systemd`, NetworkManager ou `kiosky-player`, nao usa secrets reais e
nao substitui a execucao controlada futura C6.1.

## Diferenca entre C5, C5.1, C6.0 e C6.1

### C5 - writer mock

- Gera config mock em `/tmp`.
- Usa placeholders.
- Nao escreve `/data`.
- Nao le config real.
- Prepara shape inicial da config candidata.

### C5.1 - contrato e dry-run

- Valida contrato/dry-run em `/tmp`.
- Aceita placeholders apenas em `--allow-mock`.
- Bloqueia placeholders em `--real-dry-run`.
- Nao copia config candidata para output.
- Nao le ou escreve config real.

### C6.0 - plano de escrita real

- Define como a escrita real devera acontecer.
- Define bloqueios, permissoes, backup, rollback, queda de energia e criterios
  para iniciar player.
- Nao executa escrita real.
- Nao implementa script de writer real.

### C6.1 - execucao futura controlada

- Rodada futura na placa de desenvolvimento.
- Pode escrever `/data/config/config.json` somente depois de aprovacao humana.
- Deve usar candidato validado em `--real-dry-run`.
- Deve produzir evidencia sanitizada e rollback testado.

Nota posterior: apos C6.1-preflight, a sequencia foi refinada para
C6.1-preflight documental, C6.2 implementacao futura do writer real e C6.3
execucao futura em placa de desenvolvimento. Com ADR-0010, C6.1/C6.2/C6.3
podem avancar usando token provisionado localmente em canal privado, sem
publicar valores reais. Producao futura deve migrar para emissao, revogacao e
rotacao de token pelo backend.

## Bloqueios obrigatorios antes de C6.1

C6.1 nao deve iniciar enquanto qualquer item abaixo estiver pendente:

- origem real da `api_key`;
- `api_url` real aprovada;
- `environment_id` real aprovado;
- `station_id` real, se aplicavel;
- validacao `--real-dry-run` limpa;
- `/data/config` existente ou criacao controlada planejada;
- ownership esperado definido;
- permissoes esperadas definidas;
- backup de config anterior, se existir;
- rollback definido;
- queda de energia considerada;
- launcher/player nao devem iniciar ate config estar validada;
- evidencia sanitizada revisada.

Tambem bloqueia C6.1 qualquer necessidade de publicar valor real de `api_url`,
`api_key`, `environment_id`, `station_id`, payload, path privado ou outro
secret.

## Origem da api_key

ADR-0010 define a decisao proposta para destravar C6: manter o modelo API +
token e tratar `api_key`/token como credencial de runtime do totem, nao como
token de usuario humano. Para C6.1-preflight, C6.2 e C6.3, a origem inicial
aceita e provisionamento local privado da config real, fora do Git, fora do
Codex e fora de README/evidencia.

Alternativas historicas avaliadas em C6.0:

- variavel de ambiente;
- arquivo provisionado separado;
- config privada fornecida por humano;
- mecanismo futuro de ativacao.

Regras:

- operador nao digita `api_key` na UI;
- operador nao ve `api_key` em tela publica;
- evidencia nao publica valor de `api_key`;
- backup nao deve ser publicado;
- writer real deve bloquear salvamento se a origem aprovada da `api_key` nao
  estiver disponivel;
- se a origem for arquivo provisionado separado ou candidata privada local,
  ownership, permissoes e ciclo de vida desse arquivo precisam de plano proprio
  antes de C6.3;
- producao futura deve migrar para emissao, revogacao e rotacao de token por
  backend, preferencialmente por dispositivo/station e com escopo minimo.

## Regras para api_url

Regras propostas para a `api_url` real:

- deve usar `https`, salvo excecao de bancada aprovada;
- dominio deve ser aprovado;
- nao pode ser `.invalid`;
- nao pode ser placeholder;
- nao publicar valor real em evidencia;
- validacao backend fica fora de C6.0, salvo decisao futura.

C6.0 nao decide endpoint real e nao faz chamada de rede. C6.1 deve registrar
apenas que a URL foi aprovada e validada por politica, sem publicar o valor.

## Regras de arquivo real

Destino proposto:

```text
/data/config/config.json
```

Permissoes propostas:

- owner `root:totem` ou decisao equivalente;
- mode `0640`, se compativel com launcher/player;
- diretorio `/data/config` com permissao restrita.

Essas escolhas devem ser validadas na placa antes da execucao C6.1. C6.0 nao
verifica ownership real, nao le a config real e nao cria o diretorio.

Perguntas a responder antes de C6.1:

- o launcher/player roda como usuario ou grupo capaz de ler mode `0640`?
- o grupo esperado existe na imagem alvo?
- a escrita sera executada como root, servico controlado ou outro usuario
  autorizado?
- a criacao de `/data/config`, se necessaria, faz parte de C6.1 ou de
  provisionamento anterior?
- que permissao do diretorio impede leitura indevida sem bloquear o player?

## Escrita atomica real

Plano de escrita atomica para C6.1:

1. Montar a config candidata em memoria ou em arquivo temporario seguro.
2. Validar JSON.
3. Validar contrato com o validador C5.1 em modo `--real-dry-run`.
4. Confirmar que placeholders estao bloqueados.
5. Confirmar que `api_key` esta presente sem imprimir valor.
6. Confirmar paths do contrato.
7. Escrever arquivo temporario no mesmo diretorio de destino.
8. Aplicar owner/permissao planejados ao temporario.
9. Fazer `fsync` do arquivo temporario.
10. Preservar backup da config anterior, se existir.
11. Renomear atomicamente o temporario para config ativa.
12. Fazer `fsync` do diretorio.
13. Revalidar a config ativa sem imprimir conteudo sensivel.
14. Publicar somente estado sanitizado.

Regras:

- o arquivo temporario deve ficar no mesmo filesystem do destino;
- o nome temporario nao deve ser tratado como config ativa;
- config ativa so muda no rename atomico;
- nenhuma saida deve imprimir `api_key`, URL privada, IDs reais ou payload;
- se qualquer validacao falhar antes do rename, a config ativa anterior deve
  permanecer intacta.

## Backup e rollback

Plano:

- se config anterior existir, copiar para backup com timestamp ou sufixo `.bak`
  antes de substituir;
- backup deve preservar ownership/permissoes restritas;
- backup nao deve ser publicado;
- evidencia deve registrar apenas se backup existia ou nao existia;
- evidencia deve registrar apenas se backup foi criado com sucesso ou nao;
- rollback deve restaurar a ultima config valida;
- rollback deve revalidar JSON e contrato antes de considerar recuperado;
- se rollback falhar, estado publico deve permanecer em `config_missing` ou
  `setup_error`, sem iniciar player.

Pontos a decidir:

- formato exato do nome de backup;
- quantidade de backups retidos;
- se backup fica no mesmo diretorio ou em diretorio restrito dedicado;
- quem pode executar rollback;
- como remover backups antigos sem expor conteudo.

## Queda de energia

C6.1 deve considerar queda de energia em cada ponto abaixo:

### Durante escrita temporaria

Comportamento esperado:

- config ativa anterior permanece intacta;
- temporario incompleto e ignorado no boot seguinte;
- estado deve voltar para `config_missing` ou `setup_error` se nao houver config
  ativa valida;
- evidencia futura deve registrar apenas que temporario foi limpo ou ignorado.

### Antes do rename

Comportamento esperado:

- config ativa anterior permanece vigente;
- temporario completo, mas nao ativo, nao deve iniciar player;
- boot deve validar somente config ativa.

### Depois do rename

Comportamento esperado:

- config ativa nova deve ser JSON valido e contrato valido;
- se a nova config falhar na revalidacao de boot, rollback deve restaurar a
  ultima config valida quando existir;
- se nao houver backup valido, voltar para `config_missing` ou `setup_error`.

### Durante backup

Comportamento esperado:

- se backup falhar antes do rename, abortar escrita;
- se backup ficar parcial, nao tratar como rollback valido;
- backup parcial deve ser detectavel por nome temporario ou validacao;
- evidencia nao deve publicar conteudo do backup.

### Deteccao no boot

O boot/launcher futuro deve detectar:

- JSON ausente;
- JSON invalido;
- contrato minimo invalido;
- placeholders;
- permissao ilegivel para usuario/grupo esperado;
- temporario remanescente;
- backup parcial;
- config ativa nova invalida.

Resultado esperado:

- nao iniciar player com config parcial;
- publicar erro publico seguro;
- manter renderer/setup quando aplicavel;
- voltar para `config_missing` ou `setup_error`.

## Criterio para iniciar player

O launcher so deve iniciar player se todos os criterios abaixo forem
verdadeiros:

- config existe;
- JSON e valido;
- contrato minimo e valido;
- `api_key` esta presente;
- paths sao validos;
- placeholders estao bloqueados;
- permissoes sao legiveis para usuario/grupo esperado;
- renderer/setup esta parado antes do player;
- nenhuma validacao critica falhou;
- nenhum segredo foi publicado durante a validacao.

Se qualquer criterio falhar:

- player nao inicia;
- estado publico deve ser `config_missing` ou `setup_error`, conforme contrato
  futuro;
- config ativa anterior deve ser preservada ou restaurada quando existir;
- evidencia deve ser sanitizada.

## Evidencia esperada para C6.1

C6.1 deve produzir README sanitizado com:

- objetivo;
- placa: desenvolvimento;
- sem valores reais;
- validacao `--real-dry-run`;
- backup/rollback;
- permissoes;
- C3 opcional se necessario;
- nada de secrets;
- conclusao.

O README nao deve conter:

- valor real de `api_url`;
- valor de `api_key`;
- `environment_id` real;
- `station_id` real;
- payload;
- output bruto da config;
- conteudo de backup;
- SSID, senha Wi-Fi, IP, hostname, MAC, BSSID, gateway ou DNS real.

Campos permitidos em evidencia:

- `real-dry-run`: passou/falhou;
- `api_key_present`: `true/false`;
- `placeholder_detected`: `true/false`;
- backup: existia/nao existia/criado/restaurado;
- permissoes: modo esperado observado, sem publicar owner se isso expuser dado
  sensivel;
- player: iniciado/bloqueado, sem logs privados;
- rollback: executado/nao necessario/falhou.

## Criterios de abortar

Abortar C6.1 antes de qualquer escrita real se qualquer item ocorrer:

- `api_key` indisponivel;
- `api_url` nao aprovada;
- permissoes incertas;
- backup falha;
- validador falha;
- risco de publicar secret;
- launcher poderia iniciar player prematuramente;
- humano nao aprova;
- candidato contem placeholder;
- candidato exige publicar valor real em chat, README, issue ou PR;
- rollback nao foi revisado;
- comportamento de queda de energia nao foi aceito;
- placa de desenvolvimento nao foi confirmada.

Ao abortar:

- nao escrever config real;
- nao iniciar player;
- preservar config anterior;
- registrar apenas evidencia sanitizada;
- manter C6.1 pendente.

## Fora de escopo de C6.0

C6.0 nao inclui:

- script de writer real;
- leitura de `/data/config/config.json`;
- escrita em `/data`;
- execucao em placa;
- validacao backend;
- Wi-Fi, NetworkManager, hotspot ou portal;
- alteracao de launcher, renderer, `systemd` ou `kiosky-player`;
- teste de reboot;
- teste de queda de energia real.

## Proximo passo recomendado

O proximo passo deve ser um prompt C6.1-preflight documental ou uma revisao
humana deste plano. Somente depois disso deve existir tarefa separada para
implementar writer real e, ainda depois, tarefa separada para executar em placa
de desenvolvimento.
