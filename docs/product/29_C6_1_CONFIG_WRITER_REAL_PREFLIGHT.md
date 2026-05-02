# C6.1-preflight - checklist antes do writer real

Status: checklist documental. Nao implementa writer real e nao executa escrita
real.

Data: 2026-05-02

## Objetivo

C6.1-preflight prepara a implementacao e a execucao futura do writer real de
config, sem escrever config real ainda.

Objetivos:

- transformar o plano C6.0 em checklist operacional e tecnico;
- separar decisoes humanas de implementacao e execucao;
- proteger `api_key`, config real, backup, rollback e launcher;
- impedir que uma config parcial, mock ou nao aprovada seja tratada como ativa;
- manter a ativacao do player bloqueada ate config valida e estado permitido.

C6.1-preflight nao escreve em `/data`, nao le `/data/config/config.json`, nao
implementa writer real, nao toca na placa, nao inicia player, nao altera
launcher, renderer, `systemd`, NetworkManager ou `kiosky-player` e nao usa
secrets reais.

## Diferenca entre C6.0, C6.1-preflight, C6.2 e C6.3

### C6.0 - plano

- Define o plano de escrita real.
- Lista pre-condicoes, backup, rollback, queda de energia e criterio de inicio
  do player.
- Nao implementa script de writer real.
- Nao executa escrita real.

### C6.1-preflight - checklist e decisoes

- Consolida as decisoes obrigatorias antes de qualquer writer real.
- Define checklist de execucao, pontos de abortar e politica de secrets.
- Recomenda estrategia de entrada de dados reais sem executa-la.
- Nao le nem escreve config real.

### C6.2 - implementacao futura do writer real

- Implementa o writer real em tarefa separada.
- Ainda deve ser preferencialmente testavel com destino seguro em `/tmp`.
- Deve reutilizar o contrato C5.1 e bloquear placeholders em `--real-dry-run`.
- Nao deve executar a primeira escrita real em placa no mesmo passo sem nova
  aprovacao humana.

### C6.3 - execucao futura em placa de desenvolvimento

- Executa o writer real aprovado em placa de desenvolvimento autorizada.
- Pode escrever `/data/config/config.json`, somente depois de aprovacao humana
  e checklist completo.
- Deve produzir evidencia sanitizada.
- Deve preservar config anterior, backup e rollback conforme decisao aprovada.

## Decisoes humanas obrigatorias antes de C6.2/C6.3

C6.2 ou C6.3 nao devem comecar enquanto qualquer item abaixo estiver pendente:

- [ ] origem da `api_key` aprovada;
- [ ] `api_url` real aprovada;
- [ ] `environment_id` real aprovado;
- [ ] `station_id` real aprovado ou dispensado explicitamente;
- [ ] responsavel por fornecer dados reais definido;
- [ ] canal para dados reais chegarem ao writer sem aparecer em chat, log ou
      evidencia aprovado;
- [ ] owner esperado definido;
- [ ] group esperado definido;
- [ ] mode esperado definido;
- [ ] decisao se `/data/config` ja existe ou sera criado de forma controlada;
- [ ] formato e local de backup aprovados;
- [ ] procedimento de rollback aprovado;
- [ ] existencia ou ausencia de config anterior confirmada por operador
      autorizado no momento de C6.3, sem publicar conteudo;
- [ ] decisao se o player deve iniciar automaticamente apos a escrita;
- [ ] decisao de como evitar inicio prematuro do player durante a escrita;
- [ ] placa de desenvolvimento autorizada;
- [ ] modelo de evidencia sanitizada aprovado.

Se uma dessas decisoes exigir divulgar valor real em chat, README, diff, log,
status, issue ou PR, a fase deve abortar.

## Politica de secrets para C6

Regras obrigatorias:

- `api_key` nao aparece em comando, chat, README, diff, log, summary,
  `validation-status` ou evidencia;
- `api_url` real nao aparece em evidencia publica, salvo decisao explicita e
  registrada antes da execucao;
- `environment_id` real nao aparece em evidencia publica;
- `station_id` real nao aparece em evidencia publica;
- backup nao e versionado;
- config real nao e versionada;
- output bruto de config real, backup, backend ou ferramenta operacional nao e
  publicado;
- se qualquer secret aparecer, abortar e tratar como incidente.

O validador e o writer futuro devem registrar apenas estados agregados, como
`api_key_present=true/false`, `placeholder_detected=true/false`, validacao
passou/falhou e permissoes observadas, sem imprimir valores sensiveis.

## Estrategia de entrada de dados reais

Alternativas aceitas para avaliacao:

- arquivo local privado temporario fora do Git, com permissao restrita e ciclo
  de vida definido;
- variavel de ambiente fornecida localmente no momento da execucao;
- input humano local fora do Codex e fora de transcript compartilhavel;
- mecanismo futuro de ativacao, como troca segura por backend.

Recomendacao para C6.3: usar arquivo local privado temporario fora do Git,
criado e preenchido por humano autorizado fora do chat, com permissao restrita,
consumido pelo writer real e removido ou preservado conforme politica aprovada.

Essa recomendacao nao executa nada em C6.1-preflight. Antes de C6.3, a equipe
deve decidir como o arquivo sera criado, quem tera acesso, como sera removido,
e como impedir que seu conteudo apareca em logs ou evidencia.

## Preflight tecnico antes de escrita real

Checklist tecnico minimo antes de qualquer escrita em `/data/config/config.json`:

- [ ] rodar writer mock C5 em `/tmp`;
- [ ] rodar validador C5.1 em `--allow-mock` sobre a candidata mock;
- [ ] montar candidata real em local seguro, privado, fora do Git e sem
      publicar valores;
- [ ] rodar validador C5.1 em `--real-dry-run` sobre a candidata real;
- [ ] confirmar que placeholders foram bloqueados ou estao ausentes;
- [ ] confirmar `api_key_present=true` sem imprimir valor;
- [ ] confirmar permissions, ownership e grupo esperados para diretorio,
      arquivo temporario, config ativa e backup;
- [ ] confirmar plano de backup e rollback;
- [ ] confirmar que launcher nao iniciara player ate estado permitido;
- [ ] confirmar que a evidencia esperada nao exige publicar segredo.

Se o `--real-dry-run` falhar, a escrita real nao deve acontecer. Se a falha
exigir expor segredo para diagnostico, abortar e tratar como incidente ou
processo privado fora da evidencia publica.

## Plano para evitar inicio prematuro do player

C6.3 precisa de decisao explicita sobre como manter o player bloqueado durante
montagem, validacao, backup, rename atomico e revalidacao.

Opcoes a decidir antes de C6.3:

- executar com o servico parado, se isso for aprovado para a placa de
  desenvolvimento;
- usar config path temporario que nunca seja tratado como config ativa;
- exigir que o launcher valide JSON, contrato, placeholders, paths,
  `api_key_present` e legibilidade antes de iniciar;
- manter renderer/setup ativo enquanto config nao for ativa e valida;
- executar C6.3 com override temporario ou outro bloqueio operacional aprovado,
  se necessario.

Nao ha alteracao de `systemd` neste documento. A decisao obrigatoria e se C6.3
deve ocorrer com servico parado, com bloqueio temporario do launcher, ou com
outro controle equivalente. Sem essa decisao, C6.3 aborta.

## Evidencia C6.3 esperada

A evidencia futura de C6.3 deve ser um README sanitizado contendo apenas:

- objetivo;
- placa: desenvolvimento;
- confirmacao de ausencia de valores reais publicados;
- `real-dry-run`: passou/falhou;
- backup criado: sim/nao/nao aplicavel;
- config escrita: sim/nao;
- permissoes observadas, sem publicar conteudo sensivel;
- rollback: nao necessario/executado/falhou;
- player iniciado: sim/nao, somente se permitido;
- nenhum secret publicado;
- conclusao.

O README de C6.3 nao deve conter `api_key`, `api_url` real, `environment_id`
real, `station_id` real, SSID, senha, IP, hostname, MAC, BSSID, gateway, DNS,
payload, output bruto de config, conteudo de backup ou paths privados.

## Criterios de abortar

Abortar antes de qualquer escrita real se qualquer item abaixo ocorrer:

- `api_key` nao disponivel;
- `api_url` nao aprovada;
- dados reais precisariam passar pelo chat;
- validador falha;
- permissions incertas;
- backup falha;
- rollback incerto;
- servico poderia iniciar player prematuramente;
- evidencia exigiria publicar segredo;
- placa errada;
- humano nao aprova;
- candidato contem placeholder em modo real;
- owner, group ou mode esperados nao foram decididos;
- existencia de config anterior muda a estrategia e nao ha aprovacao humana;
- origem de dados reais nao tem canal local seguro.

Ao abortar:

- nao escrever config real;
- nao iniciar player;
- nao publicar config, backup ou valores reais;
- preservar estado anterior;
- registrar apenas evidencia sanitizada, se for seguro registrar.

## Proxima etapa

Depois de C6.1-preflight, a proxima etapa pode ser C6.2 implementacao do writer
real ou uma revisao humana especifica da origem da `api_key` e do canal local
de dados reais. C6.3 so deve ser aberta depois de C6.2 aprovado e depois de
todos os itens humanos obrigatorios estarem resolvidos.
