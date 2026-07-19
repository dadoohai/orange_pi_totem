# 202 - C26 - Recuperacao local pelo usuario

Status: C26.5 provada ponta a ponta na placa `prod16` pelo updater governado, incluindo reset
online, reset offline com corte fisico, revogacao, nova ativacao,
rollback/reaplicacao, reinicio e desligamento reais. A auditoria final rejeitou
a `prod17`: uma instalacao limpa teria apenas `current`, sem `previous`, e por
isso ocultaria a restauracao. A proxima imagem deve sair com C26.5 como retorno
conhecido e uma C26 sucessora distinta como ativa.

Data: 2026-07-18

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

O motor e a experiencia sao viaveis em `totem-core`, junto de um endpoint
backend de autorrevogacao. A auditoria executavel, porem, confirmou uma corrida
no boot da `prod15`: os agentes OTA podiam disputar o lock antes de o firstboot
criar o guard. A C26A pode chegar invisivel por OTA, mas a C26B so pode ser
exposta depois de uma imagem sucessora incorporar a ordem systemd explicita.
Nao adicionar novo helper, sudoers/polkit nem permitir que `totem-core` altere
units por fora da imagem.

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

- descricao: `Desvincula e volta ao inicio.`
- titulo: `Restaurar para configuracao inicial?`
- aviso: `O vinculo, a configuracao, o conteudo baixado e o estado local serao
  apagados. Wi-Fi, orientacao da tela, software e atualizacoes serao mantidos.`
- botoes: `Cancelar` e `Restaurar`, com `Cancelar` selecionado inicialmente.

`Esc` ou `Voltar` retorna ao wizard ou a exibicao sem executar acao. Nenhuma
acao mutante recebe foco inicial e repeticao de tecla nao pode dispara-la duas
vezes.

Reiniciar e desligar usam confirmacao em duas fases. O shell grava `prepared`,
programa uma reconciliacao monotonicamente atrasada, pede a acao ao systemd e
somente depois da aceitacao grava `accepted`. O cleanup preserva a sessao
apenas para um `accepted` integro e recente. Se a acao aceita nao ocorrer, o
reconciliador forcara a restauracao do player e dos locks depois de 125
segundos. Se outra sessao ou o OTA estiver ativo nesse instante, ele repete a
cada 30 segundos e desarma somente depois de concluir a limpeza; marcador
preparado, invalido ou expirado segue o mesmo caminho seguro.
Timer e servico reconciliador usam `DefaultDependencies=no` para sobreviver a
uma transacao de shutdown iniciada mas nao concluida. O reconciliador so se
desarma quando o estado anterior nao exigia player ativo ou quando o player
esta comprovadamente ativo, em execucao e estavel por 300 segundos continuos,
o mesmo intervalo de `StartLimitIntervalSec` do servico. Aceitar
`start --no-block` ou uma amostra ativa nao basta: enquanto o servico estiver
inativo, reiniciar, falhar, emitir estado invalido ou o enable anterior nao
tiver sido restaurado, as tentativas continuam. O estado raro
ativo-porem-desabilitado e restaurado sem habilitar o servico.
Uma nova acao terminal so passa a valer depois de programar seu proprio
reconciliador e retirar os anteriores de forma limitada ao prefixo C26. Falha
ao listar ou parar uma unidade anterior cancela a nova acao; assim existe
sempre uma recuperacao valida e no maximo um reconciliador periodico, mesmo sob
repeticao indefinida de tentativas canceladas.

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
- a identidade de replay expira 90 dias depois da criacao; repetir a operacao
  nao estende esse prazo. A remocao fisica e oportunista na proxima operacao
  valida e limitada por lote; sem trafego, linhas antigas podem permanecer,
  mas nao ha novas linhas nem crescimento;
- token revogado com outro `operation_id` falha; payload diferente com o mesmo
  ID falha;
- uma ativacao antiga nunca pode revogar uma ativacao criada depois.
- hashes de token duplicados sao ambiguos e falham fechados, mesmo quando o
  cliente apresenta um ID;
- ativacoes antigas sem fingerprint persistido so podem revogar o proprio token
  quando apresentam seu `api_token_id` exato;
- `not_device_activation` nao grava uma operacao, pois nao ha mutacao para
  tornar idempotente; isso impede crescimento ilimitado por chaves legadas.

A migracao e cirurgica e separada do journal Drizzle historico. Ela aceita
somente schema-base compativel e alvo totalmente ausente ou exatamente
completo. Estado parcial, trigger inesperado, colisao global de indice,
constraint divergente ou tabela-base insuficiente falham sem tentar reparo.
Criacao e pos-validacao precisam pertencer a uma unica transacao atomica.

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
3. capturar a credencial em memoria e persistir primeiro `operation_id` e
   intent privado, com escrita atomica e `fsync`; este e o primeiro ponto em
   que o boot assume a retomada;
4. persistir a credencial pendente; se a energia cair antes disso, o boot
   recaptura a configuracao ainda intacta usando o mesmo intent;
5. gravar no journal a invalidacao do seed privado de homologacao, persistir um
   tombstone sem segredo e remover o seed com `unlink` e `fsync` antes de
   continuar;
6. bloquear primeiro a configuracao antiga, movendo `/data/config` para um
   destino inerte e recriando o diretorio vazio com ownership correto;
7. mover apenas os dominios allowlisted para limpeza e recriar seus diretorios;
8. tentar a autorrevogacao e, quando confirmada, apagar a credencial pendente;
9. abrir o wizard no inicio somente depois de concluir o desvinculo;
10. depois de uma nova configuracao valida, gravar `gc-pending.json`, liberar o
   onboarding e restaurar o player antes de apagar cache e midias antigas.

Depois que o intent existe, a configuracao antiga nunca volta a tocar. Se a
energia cair, o `totem-firstboot-gate.service` existente conclui os
moves/recreates e a sanitizacao limitada da configuracao antes do player. A
exclusao volumosa de cache, midias e estado operacional nunca ocorre no
finalize, no onboarding ou no firstboot: um oneshot de baixa prioridade apaga
somente o UUID registrado, depois que o player foi iniciado. O marcador
permanece ate `rmtree` e `fsync` terminarem; reboot ou retorno do player tenta
novamente. Outro reset fica bloqueado antes do novo intent, mantendo no maximo
um destino pendente.

O tombstone `homologation-seed-disabled.json` e privado, atomico, sincronizado e
permanece depois do GC. Ele registra apenas schema, instante e primeiro
`operation_id`; o writer valida forma, ownership e modo do seed, mas nunca le ou
copia seu conteudo para o intent, graveyard ou logs. Cortes antes/depois do
tombstone e do `unlink` retomam pelo mesmo journal. Seed reaparecido, tombstone
ausente/invalido falham fechados antes do finalize, onboarding ou nova escrita
de configuracao. Durante uma retomada ainda mutavel, policy antiga que selecione
o seed e removida e rebaixada para `candidate-only`; depois do tombstone, a
mesma selecao e recusada.

Antes de cada `rmtree`, o writer interpreta `/proc/self/mountinfo` e recusa o
graveyard se ele proprio ou qualquer descendente for mountpoint. Entrada
malformada ou ilegivel tambem falha fechada. Assim a remocao recursiva nao
atravessa um filesystem montado internamente; permanece apenas a corrida de um
ator privilegiado montar algo entre a verificacao e a chamada de remocao.

Enquanto intent ou revogacao estiver pendente, o motor mantem o guard confiavel
da sessao de settings. Em cada boot, o firstboot gate o recria imediatamente.
O updater da `prod15` ja recusa apply e rollback de `totem-core` quando esse
guard ou a sessao F10 esta ativo; portanto, depois do guard, auto-pull e
operacao manual apenas adiam. A imagem sucessora tambem bloqueia apply e
rollback enquanto `gc-pending.json` ou um graveyard nao vazio existir, para que
nenhuma versao sem esse protocolo entre durante a limpeza.

Na `prod15`, os agentes automaticos usam `OnBootSec` de 10 e 20 minutos, mas o
unit de firstboot nao declara `Before=` contra esses agentes. A condicao nao
fechou por analise do boot graph. A imagem sucessora deve embutir o unit com
ordem explicita antes de `totem-update-agent.service` e
`totem-player-runtime-update-agent.service`. Em runtime, C26B consulta o grafo
carregado e permanece escondida se qualquer uma dessas arestas estiver ausente.
Ela tambem exige que o unit esteja habilitado e tenha terminado com sucesso e
status zero, alem de um marcador `/run` ligado ao `boot_id` atual. O marcador
e gravado como ultima acao do firstboot e desaparece naturalmente no reboot.

O mesmo gate de Reiniciar, Desligar e Restaurar exige ainda o contrato fixo da
imagem `c26-product-reset-gc-static-v1`. O updater da imagem comprova que
`totem-product-reset-gc.service` e o arquivo root-owned, modo 0644 e hash exato
embutido; que o systemd o carregou do fragmento esperado como `static`, sem
`NeedDaemonReload`; e que `kiosky-player.service` possui `Wants=` para ele. O
pacote C26B declara esse feature em `requires.updater_features`, enquanto C26A
nao declara: updater antigo rejeita o feature desconhecido, updater novo rejeita
imagem antiga, unit ausente/divergente ou wiring incorreto. A mesma prova roda
na validacao do manifesto, no health sequencial de `totem-actions-v1` e ao
renderizar ou executar a acao.

Rede nao e requisito de boot. Se estiver offline, o totem preserva o Wi-Fi,
mostra `Restauracao pendente. Mantenha o totem conectado.` e continua tentando
o mesmo `operation_id`. O usuario pode revisar a rede, mas uma nova ativacao
fica bloqueada ate o servidor confirmar o desvinculo ou declarar explicitamente
que a chave era legada e nao representava uma ativacao do aparelho. Isso evita
dois donos ou dois estados ativos por causa de uma resposta perdida.

Resposta 2xx grande, malformada ou semanticamente divergente e resultado
remoto indeterminado, nunca rejeicao definitiva: o aparelho preserva a
transacao e repete o mesmo `operation_id`. Um HTTP rejeitado sem envelope
confirmador interrompe apenas a repeticao automatica; ele nao finaliza nem
restaura dados antigos. Segurar `F10` abre a superficie restrita de recuperacao,
mantem todas as demais acoes indisponiveis e permite revisar a rede e pedir uma
nova tentativa explicita. Erro de contrato persistente continua fail-closed e
exige correcao do backend ou suporte, pois nao existe alternativa local segura
que possa presumir o resultado remoto.

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
   operacao. Tambem exige o boot graph seguro carregado, portanto fica escondida
   na `prod15`.
4. **Imagem sucessora:** embutir e validar o firstboot unit ordenado antes dos
   dois agentes OTA, seu symlink de enable, a capacidade `product-reset-v1` e
   o oneshot de limpeza puxado pelo player sem prender `multi-user.target`;
   somente essa imagem habilita as acoes.
5. **Placa e OTA:** dry-run, apply de C26A e C26B, reset online, reset
   interrompido/offline, reboot, rollback para C26A e reaplicacao.

Apply ou rollback de `totem-core` fica indisponivel enquanto houver
intent/revogacao, marcador de limpeza ou graveyard nao vazio. O guard de
settings cobre a transacao com o usuario; o updater fixo da imagem cobre a
limpeza posterior. Isso impede que timer ou operador troque para codigo sem o
contrato no meio da operacao.

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
  permanecem bloqueados durante intent/revogacao e limpeza pendentes;
- boot graph e timestamps reais da imagem sucessora provam guard criado antes
  dos agentes de update; a `prod15` deve manter as acoes escondidas;
- manifesto e health de C26B recusam imagem sem o unit static exato e sem o
  `Wants=` do player; C26A permanece instalavel sem esse feature;
- cortes fisicos seletivos validam intent, config bloqueada e resposta de
  revogacao, sem campanha de horas;
- cada corte ao redor da remocao do seed termina com tombstone valido, seed
  ausente e nenhum valor secreto copiado; reintroducao bloqueia a retomada;
- mountpoint sintetico dentro do graveyard e recusado antes do `rmtree`;
- cache grande nao alonga o boot nem acumula destinos indefinidamente;
- wizard normal, player, timers, auto-pull, rollback e baseline `prod15` nao
  regridem;
- pacote passa self-tests, QA visual, apply, rollback e reaplicacao na placa.
- C26A e C26B nunca compartilham a mesma identidade: o pacote com acoes recebe
  sufixo `-actions`, reservado e recusado em pacotes sem acoes, evitando
  colisao de versao com payload diferente.

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

## Marco posterior - reinstalacao integral

Registrar como proximo nivel de recuperacao, nao como ideia descartada:

- criar uma nova imagem de referencia com ambiente de recovery independente
  ou raiz A/B;
- permitir que o usuario inicie `Reinstalar sistema` com confirmacao forte,
  sem depender do sistema principal estar saudavel;
- usar somente imagem assinada e verificada, com retorno seguro apos queda de
  energia ou falha de instalacao;
- declarar separadamente se dados/configuracao serao preservados ou apagados;
- validar na bancada por regravacoes, imagem boa, imagem defeituosa, corte de
  energia e retorno a um sistema inicializavel.

Este marco exige ao menos uma nova regravacao para instalar a arquitetura de
recovery. Depois disso, as reinstalacoes futuras poderao ser locais e guiadas,
sem Armbian Imager. Ele nao bloqueia a entrega anterior de M10.

## Estado executivo desta rodada

Concluido e versionado:

- backend de autorrevogacao exata promovido, com operacao idempotente,
  rastreabilidade e contratos legados preservados;
- motor local fail-closed, retomada persistente, limpeza limitada, guard OTA e
  acoes `Reiniciar`, `Desligar` e `Restaurar` dentro do unico fluxo `F10`;
- pacote final
  `c26.5-local-recovery-20260718-f1d0da9-actions`, preso ao commit
  `f1d0da92eff5f0aa94036b0ae5a8a85e632450dc` e ao payload
  `b8864cc913f6e7ca4562a0e3edfe9eb0ba55a6aef5019a47a0535397ba26f4df`;
- suite C26 local com 17 testes, self-test visual, testes backend e gate OTA
  completo verdes;
- na `prod16`, apply da C26.5, reset online, revogacao do token anterior,
  reativacao e health de playback passaram;
- reset sem internet foi interrompido por corte fisico depois da limpeza local.
  O boot retomou a mesma operacao, obteve recibo de revogacao, manteve a config
  antiga bloqueada e permitiu uma nova ativacao; o token anterior permaneceu
  recusado;
- rollback governado para C26.4 e reaplicacao da C26.5 preservaram config,
  policy stable, timer e player. As janelas repetidas terminaram sem restart,
  erro de midia ou perda de hardware decode;
- `Desligar` foi confirmado na interface, encerrou a placa e exigiu religamento
  fisico. `Reiniciar` foi confirmado na mesma interface, gerou novo boot e
  voltou automaticamente. Config, contexto e policy mantiveram hashes exatos;
- imagem `c18-hwdecode-prod-17-c26`, versao `c18.image-prod.17-c26`, construida
  do commit `bd119ba8fcb5721ce6a6275e1f23615c20022905`, com C26.5 exata embutida.
  A validacao offline, `e2fsck`, higiene de imagem e auditoria da identidade
  passaram. SHA256:
  `696bd671cfc819c51c8dcc977633d0a803fb2c986d09c3b21a2c6d099d27d00b`.

Achados da auditoria final:

- **nao gravar nem distribuir a `prod17`**: o estado embutido possui
  `previous=null`, enquanto a interface so libera `Restaurar` quando as duas
  versoes suportam `product-reset-v1`;
- o contrato geral aceitava algumas URLs de API que o cliente de revogacao
  recusava depois da limpeza local. A validacao deve ser unica e ocorrer antes
  do intent persistente e de qualquer remocao;
- a prova na `prod16` sustenta o funcionamento do motor C26, mas nao promove por
  inferencia uma imagem de fabrica.

Evidencias decisivas:

- `docs/evidence/c26-local-recovery/20260718T205350Z-c26-final-board-e2e/`;
- `docs/evidence/c26-local-recovery/20260718T204719Z-prod17-c26-build/`.

Pendente para declarar a nova baseline pronta:

- unificar e limitar URL, chave de API e credencial pendente antes do ponto
  destrutivo, incluindo a paridade writer, QR, contrato e wizard;
- gerar dois pacotes C26 distintos que ja preservem essa seguranca e uma imagem
  de identidade nova que use um como `previous` e o outro como `current`;
- fazer o gate offline reprovar imagem sem retorno integro e compativel;
- gravar somente essa nova imagem na bancada e provar boot, identidade,
  onboarding, playback, timer, `F10` fisico e as tres acoes;
- somente depois atualizar a referencia de distribuicao e promover o pacote.

Non-claim: a prova funcional atual e da `prod16` com C26.5 aplicada por pacote
local no updater governado. A `prod17` e um artefato rejeitado e nunca deve
substituir a baseline publica.

## Auditoria prod18

A `prod18` (`fbaf93d0438567f5312363415c9e6778c74ca1e8e9642c6e46f79f02b5ad0a4d`)
foi construida no commit `50f808e` com C26.7 atual e C26.5 anterior. A imagem,
os dois slots e os probes de adulteracao passaram, mas o artefato foi rejeitado
antes do flash:

- C26.5 aceita ao menos uma URL que o revogador recusa somente depois da
  limpeza local;
- C26.7 nao limita de forma composicional chave, hostname e tamanho final da
  credencial que o revogador le;
- voltar para C26.5, portanto, seria regressao semantica apesar do rollback
  mecanico estar correto.

Evidencia:
`docs/evidence/c26-local-recovery/20260718T230211Z-prod18-c26-build/`.

## Auditoria dos slots C26.8 a C26.12

C26.8, C26.9 e C26.10 foram iteracoes intermediarias e permanecem bloqueadas
pelo gate semantico atual por contratos incompletos de transporte e credencial.
C26.11 e C26.12 fecharam esses pontos, mas uma auditoria adversarial encontrou
duas regressoes novas:

- um resultado QR autorizado para um ambiente podia fornecer chave e identidade
  privadas depois que o usuario selecionasse manualmente outro ambiente;
- uma falha de armazenamento depois da troca atomica de `config.json` podia
  reportar erro e ainda deixar a configuracao candidata instalada.

As cinco versoes sao artefatos rejeitados e nenhuma foi gravada na placa. O
sucessor deve vincular credenciais QR ao ambiente selecionado, restaurar o
estado anterior depois de qualquer falha pos-troca e provar ambos os casos no
gate semantico do pacote. Somente dois slots sucessores aprovados podem compor a
nova imagem de referencia.

As correcoes foram congeladas em `6d95dd1`, e C26.13/C26.14 passaram o gate que
reprova C26.8 a C26.12. Uma auditoria posterior bloqueou a composicao antes do
build: se o backup desaparecesse antes da troca, uma falha preparatoria podia
apagar a configuracao antiga intacta. A mesma rodada exigiu tratar `SIGTERM`
durante a troca sem permitir que outro sinal interrompesse o rollback.

O sucessor valida o arquivo temporario exato, ja sincronizado e com ownership
final, antes do rename; decide rollback comparando o estado visivel com os bytes
e o inode anteriores; bloqueia temporariamente escrita do usuario do player no
diretorio de configuracao; e protege a recuperacao contra sinais repetidos.
Falhas trataveis e sinais capturaveis restauram o anterior. `SIGKILL` ou corte antes do `fsync` do
diretorio continuam tendo resultado de persistencia ambiguo, mas somente entre o
arquivo anterior e o candidato completo, previamente validado; o launcher ainda
falha fechado antes do playback. C26.13/C26.14 nao devem compor a imagem; dois
novos slots sucessores precisam passar o gate atualizado.
