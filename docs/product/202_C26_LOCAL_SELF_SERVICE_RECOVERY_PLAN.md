# 202 - C26 - Recuperacao local pelo usuario

Status: decisao refinada e aprovada para implementacao. Nao declara que os
novos controles ja existem.

Data: 2026-07-17

## Missao

Reduzir visitas tecnicas dando a uma pessoa nao tecnica poucos comandos locais
capazes de recuperar o totem ou devolve-lo ao inicio da configuracao. O fluxo
deve funcionar sem suporte remoto, ter baixo atrito cognitivo, sobreviver a
interrupcao e preservar a baseline `prod15`.

Prioridade: primeiro oferecer ancoras amplas e previsiveis. Diagnostico
granular e tratamento de casos especificos evoluem depois, a partir de falhas
reais.

## Decisao de produto

Ha tres niveis distintos de recuperacao:

1. **Recuperacao automatica:** retry, watchdog, restart, cache offline e
   rollback OTA continuam invisiveis para o usuario.
2. **Recuperacao local do produto:** `F10` oferece reiniciar, desligar e
   `Restaurar para configuracao inicial`. Esta ultima desvincula a ativacao
   atual, remove dados operacionais do cliente e volta ao onboarding.
3. **Recuperacao integral do sistema:** corrupcao de boot, kernel, rootfs ou
   armazenamento continua exigindo regravacao externa da imagem conhecida.

A imagem atual nao possui particao de recovery, raiz A/B, instalador local nem
uma segunda imagem completa. Portanto, a acao local e uma restauracao do
produto, nao uma reinstalacao do sistema operacional nem sanitizacao completa
para revenda.

Ela e viavel em `totem-core` sobre a `prod15`, junto de um endpoint backend de
autorrevogacao. Nao exige nova imagem nem novo unit systemd porque o wizard, a
sessao F10 e o firstboot gate existentes ja pertencem ao pacote permitido.
Toda a implementacao local deve permanecer nesses arquivos ja allowlisted;
adicionar novo binario/helper, unit, sudoers/polkit ou alterar o updater volta a
exigir nova imagem.

## Experiencia escolhida

Existe uma unica entrada: segurar `F10`.

`F10` continua abrindo diretamente o wizard atual. Um controle discreto no
cabecalho abre `Acoes do totem`, dentro da mesma navegacao por setas e Enter.
Nao havera home nova, `F12`, sexto passo, painel tecnico ou outro modelo mental.

As acoes sao:

| Acao | Resultado | Confirmacao |
| --- | --- | --- |
| `Reiniciar totem` | Reinicia a placa inteira e volta automaticamente. | Segunda tela, com foco inicial em cancelar. |
| `Desligar com seguranca` | Encerra o sistema e desliga a placa. | Segunda tela; avisa que e preciso retirar e reconectar a energia para ligar. |
| `Restaurar para configuracao inicial` | Desvincula a ativacao atual, limpa dados locais do produto e volta ao inicio do setup. | Segunda tela destrutiva, com foco inicial em cancelar. |

Nao existe a acao `Configurar novamente`: o proprio wizard aberto por `F10` ja
faz isso sem apagar a configuracao ativa antes da conclusao.

Copy da restauracao:

- descricao: `Desvincula este totem e volta ao inicio da configuracao.`
- titulo: `Restaurar para configuracao inicial?`
- aviso: `O vinculo, a configuracao, o conteudo baixado e o estado local serao
  apagados. Wi-Fi, orientacao da tela, software e atualizacoes serao mantidos.`
- botoes: `Cancelar` e `Restaurar`, com `Cancelar` selecionado inicialmente.

`Esc` ou `Voltar` retorna ao wizard ou a exibicao sem executar acao. Nenhuma
acao mutante recebe foco inicial e repeticao de tecla nao pode dispara-la duas
vezes.

## O que a restauracao resolve

- configuracao de ambiente errada, antiga ou incompleta;
- aparelho que precisa ser vinculado novamente;
- cache de midia ou estado local do player inconsistente;
- entrega do aparelho para outra configuracao operacional no mesmo local;
- retorno previsivel ao onboarding sem depender de SSH ou tecnico.

Ela nao corrige boot, kernel, rootfs, cartao/armazenamento, hardware, cabo, TV
ou falha no proprio wizard. Esses casos continuam no fluxo de regravacao da
imagem ou troca de hardware.

## Fronteira de dados

Apagar:

- configuracao ativa e backups em `/data/config`;
- credencial, ambiente e station atuais depois de registrada a revogacao;
- cache baixado em `/data/media/kiosky-player`;
- estado, spool e logs operacionais do player;
- `last-settings` e candidatos temporarios do wizard.

Preservar:

- Wi-Fi atual, para que a pessoa consiga reativar sem Ethernet ou tecnico;
- orientacao de tela, por ser propriedade fisica da instalacao;
- imagem, sistema, identidade da placa e acesso de suporte;
- canary local de validacao;
- `current`, `previous`, releases, estado, quarentena e markers de OTA;
- policy, timers, segredos de update e protecoes de rollback.

Nunca apagar `/data` inteiro. Esta restauracao tambem nao promete remover todo
vestigio historico do sistema para revenda: preservar Wi-Fi e suporte e uma
decisao operacional explicita.

## Desvinculo backend

Apagar somente arquivos locais deixaria a credencial atual valida no servidor.
A restauracao precisa de `POST /totem-auth/self-revocations` com estas regras:

- o aparelho cria um `operation_id` aleatorio uma unica vez e o persiste antes
  de alterar o estado local;
- a autoridade vem da `x-api-key` apresentada; IDs enviados pelo cliente sao
  apenas confirmacoes e nunca definem o alvo;
- para token com scope `totem-device`, o servidor deriva token, ativacao e
  identidade do aparelho e revoga somente o token apresentado e credenciais da
  mesma ativacao;
- uma chave legada/compartilhada nunca e revogada pelo aparelho; depois de
  autentica-la, o backend responde `not_device_activation` e a restauracao
  remove somente sua copia local, pois nao havia vinculo exclusivo do aparelho;
- a operacao e a revogacao sao gravadas na mesma transacao;
- repetir o mesmo token e `operation_id` devolve exatamente o resultado ja
  salvo, sem nova mutacao;
- token revogado com outro `operation_id` falha; payload diferente com o mesmo
  ID falha;
- uma ativacao antiga nunca pode revogar uma ativacao criada depois.

Nao usar revogacao ampla somente por fingerprint. Isso daria a uma credencial
antiga poder para interromper o novo dono. A restauracao remove tambem os
backups locais, mas nao afirma revogar credenciais historicas de outras
ativacoes que ja nao pertencem ao estado atual do aparelho.

## Transacao local e queda de energia

O ponto sem volta e um intent privado e sincronizado em
`/data/state/totem-appliance/product-reset/`, fora dos caminhos apagados.

Sequencia:

1. adquirir os locks existentes de settings e update e parar o player;
2. validar caminhos fixos, ownership e ausencia de symlinks inesperados;
3. persistir credencial pendente, `operation_id` e intent com permissoes
   privadas, escrita atomica e `fsync`;
4. bloquear primeiro a configuracao antiga, movendo `/data/config` para um
   destino inerte e recriando o diretorio vazio com ownership correto;
5. mover apenas os dominios allowlisted para limpeza e recriar seus diretorios;
6. tentar a autorrevogacao e, quando confirmada, apagar a credencial pendente;
7. abrir o wizard no inicio somente depois de concluir o desvinculo.

Depois que o intent existe, a configuracao antiga nunca volta a tocar. Se a
energia cair, o `totem-firstboot-gate.service` existente conclui apenas os
moves/recreates locais curtos antes do player. Exclusao volumosa ocorre fora do
caminho critico de boot, em um unico destino limitado para nao acumular lixo.

Enquanto intent ou revogacao estiver pendente, o motor mantem o guard confiavel
da sessao de settings. Em cada boot, o firstboot gate o recria imediatamente.
O updater da `prod15` ja recusa apply e rollback de `totem-core` quando esse
guard ou a sessao F10 esta ativo; portanto, depois do guard, auto-pull e
operacao manual apenas adiam sem exigir mudanca do updater ou da policy.

Na `prod15`, os agentes automaticos usam `OnBootSec` de 10 e 20 minutos, mas o
unit de firstboot nao declara `Before=` contra esses agentes. A release precisa
provar no boot graph e em placa que o guard sempre aparece antes da primeira
tentativa de update. Se essa condicao nao fechar, a acao nao e exposta ate uma
imagem futura adicionar a ordem systemd explicita.

Rede nao e requisito de boot. Se estiver offline, o totem preserva o Wi-Fi,
mostra `Restauracao pendente. Mantenha o totem conectado.` e continua tentando
o mesmo `operation_id`. O usuario pode revisar a rede, mas uma nova ativacao
fica bloqueada ate o servidor confirmar o desvinculo ou declarar explicitamente
que a chave era legada e nao representava uma ativacao do aparelho. Isso evita
dois donos ou dois estados ativos por causa de uma resposta perdida.

## Entrega incremental

1. **Backend isolado:** schema e endpoint idempotente, testes de replay,
   concorrencia, token revogado e ativacao posterior; candidata sem trafego,
   auditoria e smoke antes de promover.
2. **C26A - motor local invisivel:** intent, matriz de apagar/preservar,
   retomada no firstboot, bloqueio de nova ativacao e fault injection em cada
   fase, sem expor ainda a acao destrutiva.
3. **C26B - experiencia:** acao, confirmacao, estados online/offline e retorno
   ao onboarding; reboot e poweroff usam o mesmo shell pai protegido. A acao
   so aparece quando `current` e `previous` declaram suporte a
   `product-reset-v1`, deixando um rollback imediato ainda capaz de retomar a
   operacao.
4. **Placa e OTA:** dry-run, apply de C26A e C26B, reset online, reset
   interrompido/offline, reboot, rollback para C26A e reaplicacao.

Apply ou rollback de `totem-core` fica indisponivel enquanto houver
intent/revogacao pendente por meio do guard de settings que o updater atual ja
enforca. O guard so e removido depois da conclusao. Isso impede que timer ou
operador troque para codigo sem o contrato no meio da operacao sem criar uma
segunda politica de update.

O fallback antigo da imagem continua fora desse contrato. Se `current` e
`previous` forem ambos perdidos ou corrompidos, a config ja bloqueada nao volta
a tocar, mas o caso passa a ser recuperacao integral por regravacao. A funcao
nao deve prometer consertar corrupcao simultanea dos dois slots e do sistema.

Uma vertical pode avancar enquanto outra e auditada, mas nenhuma e promovida
com regressao conhecida. O deploy backend deve primeiro provar que a revisao
em producao corresponde ao source versionado, seguindo a disciplina adotada
depois do incidente C21.

## Validacao decisiva

- cancelar cada confirmacao nao altera estado;
- reset online revoga o token atual, limpa somente os dados declarados,
  preserva Wi-Fi/orientacao/OTA e volta ao onboarding;
- resposta perdida e retry usam o mesmo `operation_id` e uma unica mutacao;
- token antigo nao consegue iniciar nova operacao nem afetar nova ativacao;
- chave legada compartilhada tem resposta `not_device_activation`, nao e
  revogada e deixa de existir somente na placa restaurada;
- reset offline e cada interrupcao simulada deixam a config antiga bloqueada e
  retomam com seguranca;
- C26B so expoe a acao com C26A em `previous`; auto-pull, apply e rollback
  permanecem bloqueados durante intent/revogacao pendente;
- boot graph e timestamps reais provam guard criado antes dos agentes de update
  da `prod15`; falha nessa prova bloqueia entrega sem nova imagem;
- cortes fisicos seletivos validam intent, config bloqueada e resposta de
  revogacao, sem campanha de horas;
- cache grande nao alonga o boot nem acumula destinos indefinidamente;
- wizard normal, player, timers, auto-pull, rollback e baseline `prod15` nao
  regridem;
- pacote passa self-tests, QA visual, apply, rollback e reaplicacao na placa.

## Definicao de pronto

O marco fecha quando uma pessoa consegue, apenas por `F10`, reiniciar, desligar
ou restaurar o produto ao inicio da configuracao; quando a ativacao anterior
nao permanece utilizavel pelo aparelho; quando falha de rede, resposta perdida
ou corte de energia nao recupera dados antigos nem bloqueia o boot; e quando o
mesmo pacote passa QA visual, placa real e roundtrip OTA sem regressao da
`prod15`.

A reinstalacao integral do sistema permanece um procedimento separado de
regravacao. Recovery partition ou raiz A/B so entra em imagem futura se a
escala e os incidentes reais justificarem esse custo.
