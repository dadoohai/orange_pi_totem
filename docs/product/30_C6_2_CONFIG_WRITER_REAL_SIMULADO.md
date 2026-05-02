# C6.2 - writer real simulado em /tmp

Status: implementacao local/simulada. Nao executa escrita real em `/data`.

Data: 2026-05-02

## Objetivo

C6.2 implementa o primeiro writer real reutilizavel, ainda em modo seguro e
simulado.

Objetivos:

- implementar writer real reutilizavel;
- testar validacao, backup, escrita atomica e rollback;
- executar somente em `/tmp`;
- preparar C6.3;
- nao escrever em `/data`.

C6.2 nao toca placa, nao usa token real, nao cria `/data/config`, nao escreve
`/data/config/config.json` e nao altera launcher, renderer, `systemd`,
NetworkManager ou `kiosky-player`.

## Diferenca entre C6.2 e C6.3

### C6.2

- Implementacao do writer real em modo simulado.
- Execucao local somente em `/tmp`.
- Candidata de teste sintetica e nao-secret.
- Sem placa.
- Sem token real.
- Sem `/data`.

### C6.3

- Execucao futura na placa de desenvolvimento.
- Podera escrever `/data/config/config.json` somente depois de aprovacao humana
  e checklist completo.
- Deve receber dados reais por canal local privado, fora do Codex, Git,
  README, chat e evidencia publica.
- Deve validar owner, group, mode, backup e rollback no alvo real.

## Escopo de C6.2

Inclui:

- ler uma candidata privada/local de teste;
- validar contrato com C5.1;
- bloquear placeholders;
- escrever config ativa simulada em `/tmp`;
- criar backup simulado se config anterior existir;
- rollback simulado;
- permissoes restritivas;
- evidencia sanitizada.

Fora de escopo:

- `/data` real;
- placa;
- token real;
- backend;
- launcher/player;
- `systemd`;
- queda de energia real.

## Modelo de seguranca

Regras do writer C6.2:

- writer nao imprime `api_key`/token;
- writer nao copia candidata para evidencia;
- writer registra apenas `api_key_present` e `placeholder_detected`;
- writer so aceita destino sob `/tmp` nesta fase;
- writer recusa qualquer destino fora de `/tmp`;
- writer recusa candidata em `/data` ou `/opt`;
- writer usa validador C5.1 em `real-dry-run` antes de ativar config.

O status e o summary sao sanitizados. Eles nao contem valor de `api_key`, nao
contem payload bruto da candidata e nao contem conteudo de backup.

## Escrita atomica simulada

Fluxo implementado em C6.2:

1. Validar argumentos e paths permitidos.
2. Carregar a candidata local.
3. Rodar validacao equivalente ao contrato C5.1 em `real-dry-run`.
4. Abortar antes de qualquer escrita no destino se a validacao falhar.
5. Preparar o diretorio de destino simulado sob `/tmp`.
6. Se houver config ativa simulada anterior, criar backup simulado.
7. Escrever arquivo temporario no mesmo diretorio do destino.
8. Aplicar permissao restritiva ao temporario.
9. Fazer `fsync` do arquivo temporario.
10. Renomear atomicamente o temporario para a config ativa simulada.
11. Fazer `fsync` do diretorio.
12. Revalidar a config ativa simulada.
13. Fazer rollback se a validacao pos-escrita falhar.
14. Gerar `writer-status.json` e `summary.txt` sanitizados.

Em C6.2, a config ativa simulada usa mode `0600`. A alternativa `0640` fica
para C6.3, depois de owner/group reais serem definidos e validados na placa.
`chown` real nao e aplicado em C6.2 porque nao ha owner/group alvo definido
para o ambiente simulado.

## Backup/rollback simulado

Regras:

- backup fica em `/tmp`;
- backup tem permissao `0600`;
- conteudo do backup nunca entra na evidencia;
- rollback restaura backup para config ativa simulada;
- se backup nao existir, rollback falha de forma segura e sanitizada.

Em falha critica pos-escrita sem backup, o writer remove a config ativa
simulada invalida quando possivel e registra apenas estado agregado.

## Criterios de aceite

- self-test ok;
- destino fora de `/tmp` falha;
- candidata mock C5 falha em modo real;
- candidata sintetica nao-secret passa;
- escrita atomica gera config ativa simulada;
- backup e criado quando config anterior existe;
- rollback simulado funciona;
- `api_key`/token nao aparece em summary/status/evidencia;
- nada em `/data`.

## Bloqueios antes de C6.3

- dados reais por canal local privado;
- owner/group/mode reais definidos;
- `/data/config` validado na placa;
- decisao sobre servico/launcher;
- rollback real aprovado;
- evidencia sanitizada aprovada.
