# C18 Production Auto-Pull Spec

Estado inicial: 2026-07-05.

Esta spec orienta a proxima fase C18: transformar a homologacao validada em uma
linha de producao pragmatica com auto-pull como padrao. Ela nao substitui
`docs/UPDATE_CONTRACT.md`; ela define a ordem de execucao para entregar valor
sem regressao.

Direcao macro e marcos da fase atual: `docs/C18_MACRO_STEERING.md`.

Atualizacao de direcao em 2026-07-12: o C23 exact-target foi fechado, e o
proximo slice de player esta em
`docs/product/198_C24_PLAYER_SOURCE_AND_SCALE_DECISION.md`. O controle assinado
no device foi promovido para permitir C24+ sem regravacao; grupos, dashboard e
telemetria continuam roadmap. Essa direcao exige uma nova imagem uma vez e nao
promete que placas prod8 consumam o novo controle sem reflash ou bootstrap
assistido validado. A implementacao foi adiada por prioridade de produto e so
retorna pelos gatilhos registrados na decisao 198.

Quando documentos antigos disserem que auto-pull esta fora de escopo, esta spec
registra a nova decisao operacional. O contrato de seguranca continua valido:
escopos, allowlists, hashes, health, rollback e bloqueios de componente so mudam
por implementacao explicita e testada.

## Missao

Entregar placas C18 capazes de operar em cliente e receber atualizacoes remotas
automaticas com validacao local, rollback e escopo controlado.

Decisao de negocio atual: o cliente quer escala rapida e aceita o risco de uma
primeira producao sem infraestrutura completa de grupos, dashboard ou telemetria
de frota. A engenharia deve respeitar essa decisao sem abrir caminho inseguro
que quebre placa ou confunda homologacao com update automatico.

## Premissas

1. Nunca regredir o que ja foi provado.
2. Velocidade tambem e qualidade quando uma vertical pode avancar sem afetar as
   outras.
3. Toda mudanca precisa ter teste ou evidencia proporcional ao risco.
4. `kiosky-player` legado nao volta como rota de release C18.
5. `totem-core`, `player-runtime`, `media-system` e `field-data` continuam
   separados.
6. Lab harness nao e caminho de producao.
7. Auto-pull so pode aplicar pacote que passe por policy, manifest, hash,
   health e rollback.
8. Falta de policy, evidencia, hash, health, rollback ou canal correto bloqueia
   a entrega. Nao vira warning.
9. Excecao de negocio vale apenas para o alvo e o hash aprovados. Nao vira
   precedente automatico para a proxima release.
10. Publicar no GitHub nao conta como adocao em placa. Timer aplicando e
    rollbackando em hardware conta.

## Regra De Avanco

Uma vertical pode avancar sozinha quando:

- nao muda contrato de outra vertical;
- nao reduz gate existente;
- mantem rollback;
- registra evidencia curta;
- deixa claro o que ainda nao esta provado.

Uma falha bloqueia a vertical afetada, nao o programa inteiro, salvo se tocar
baseline de boot, player, updater, imagem ou rollback.

## Verticais

### V1 - Imagem De Producao

Valor: novas placas saem prontas para cliente, sem depender de um primeiro OTA
para ter o player correto.

Spec minima:

- imagem C18 com marcador de producao, sem `not_for_production`;
- `final_image=true`, tag/SHA/marker/repo commit proprios;
- base congelada: sem `apt upgrade`, `armbian-upgrade` ou troca de
  kernel/DTB/U-Boot/MPV nesta vertical;
- `player-runtime 9bebaf1` como baseline inicial aprovado da imagem, sem
  confundir isso com adocao runtime em `/data/player-runtime/current`;
- `totem-core` atual embutido ou imediatamente atualizavel;
- policy de producao instalada;
- update timer instalado conforme V2;
- sem secrets reais dentro da imagem;
- runbook curto de gravacao, boot e validacao.

Testes/evidencias:

- build reproducivel com SHA da imagem;
- boot na placa;
- player ativo com HW decode;
- status de `current`/`previous` coerente;
- policy presente;
- timer no estado esperado;
- gate global C18 verde apos registro.
- smoke de bancada por placa ou por amostra definida: microSD, serial/lote,
  SHA gravado, boot, config e playback. Checklist completo de fabrica/lote fica
  em V4.

Fora desta vertical:

- update de MPV/kernel;
- A/B de imagem;
- telemetria de frota;
- auto-pull de `player-runtime` publico.
- upgrade de pacotes do SO.

### V2 - Auto-Pull `totem-core`

Valor: wizard, splash, status, UX operacional e scripts Dadooh passam a ser
atualizaveis remotamente sem operador.

Spec minima:

- timer habilitado na imagem de producao;
- service continua chamando explicitamente `--component totem-core`;
- policy de producao permite somente `totem-core` nesta etapa:
  `device_channel=stable`, `allow_prerelease=false`,
  `allowed_components=["totem-core"]`, `allow_downgrade=false`;
- canal escolhido e documentado;
- release repetida deve ser no-op seguro;
- apply com health e rollback continua obrigatorio.
- release selecionada precisa ser compatível com policy/canal e observavel por
  dry-run; uma release mais nova fora do escopo deve ser ignorada ou bloqueada.
- se a release selecionada ja for o `current` pelo par `version` +
  `payload_sha256`, o updater deve sair `0/already_current` sem baixar, extrair
  ou mexer em symlinks.

Testes/evidencias:

- teste offline de policy/service/timer;
- release gate do pacote;
- dry-run selecionando a release esperada;
- timer real na placa puxando release;
- rollback real;
- player permanece saudavel depois do update;
- teste negativo para pacote fora da allowlist.
- boot com timer habilitado e release ja aplicada: deve ser no-op. Se nao houver
  prova fisica especifica do timer repetido, manter como hardening operacional,
  pois o contrato ja e coberto pelo updater/gates.
- evidencia M2 propria para timer real, separada da evidencia M1 manual.
- coleta/gate do marco: `scripts/board/c18_totem_core_production_timer_collect.py`
  e `scripts/qa/c18_totem_core_production_timer_evidence_gate.py`, com coleta
  pos-timer e coleta pos-rollback.

Fora desta vertical:

- player-runtime;
- launcher do player;
- systemd units fora do update agent;
- MPV, midia, config real e cache.

### V3 - Ponte Publica `player-runtime`

Valor: mudancas futuras no comportamento do player tambem entram no fluxo OTA,
sem voltar ao repo/caminho legado.

Status: vertical ativa agora. A decisao de negocio em 2026-07-05 e liberar
auto-pull de `player-runtime` como capacidade de producao pragmatica, aceitando
rollout simples/global e adiando grupos, dashboard e telemetria. A execucao
tecnica continua estreita: alvo exato, hashes, health real, rollback e
fail-closed para qualquer coisa fora da autorizacao.

Spec minima:

- caminho publico separado do harness lab;
- release alvo pinada por versao/tag/source_commit/payload SHA/release-gate
  SHA;
- policy ou autorizacao componente-especifica no device; nao colocar a producao
  inteira em `homologation` so para consumir o carrier atual;
- health real antes de adotar;
- marker `.release_verified.json` obrigatorio;
- rollback para previous ou imagem;
- quarentena de candidato ruim;
- freeze publico so abre por regra explicita e rastreavel;
- nenhum `latest` amplo para player sem ponteiro/decisao verificavel;
- aplicar novo target exige pacote, hash, gate e claim proprios; evidencia
  historica nao fecha target novo.
- checks hoje existentes no harness lab precisam existir no caminho publico:
  allowlist `kiosk.py`, bloqueio de midia/config/cache/systemd/MPV/kernel,
  marker gerado no device e verify-then-promote;
- timer proprio ou execucao explicitamente componenteada com lock global, para
  nao concorrer com `totem-core`.

Testes/evidencias:

- release gate `player-runtime`;
- testes de freeze continuam cobrindo caminho nao autorizado;
- apply publico permitido somente para alvo autorizado;
- candidato ruim nao vira current;
- rollback real;
- deep-health na placa;
- power-loss/gates existentes nao rebaixados.
- dry-run publico por alvo exato, sem mutacao;
- apply publico sem env lab;
- reapply/no-op seguro;
- timer real aplicando em placa antes de escala.

Fora desta vertical:

- mudar MPV/ffmpeg/kernel;
- publicar direto pelo `kiosky-player`;
- auto-pull por grupos sofisticados;
- stable manifest falso para contornar freeze.
- `latest` amplo que possa pegar um `player-runtime` futuro sem nova evidencia.

### V4 - Operacao De Producao Simples

Valor: permitir escala agora com risco conhecido e resposta operacional minima.

Spec minima:

- inventario manual de placa, imagem, core, runtime, cliente/local;
- rollback owner;
- janela de suporte para release;
- procedimento de emergencia para desabilitar timer ou publicar fix-forward;
- criterio simples de parar rollout;
- registro de decisao de negocio aceitando rollout simples/global.

Testes/evidencias:

- checklist de fabrica;
- placa nova provisionada do zero;
- uma rodada de auto-pull real;
- captura de estado antes/depois;
- gate global verde.

Fora desta vertical:

- dashboard;
- grupos/canary automatizados;
- kill switch server-side completo;
- monitoramento remoto continuo.

### V5 - Roadmap De Robustez

Valor: reduzir risco de frota depois da primeira entrega.

Itens:

- rollout por grupos;
- allowlist consumida no device;
- assinatura/trust anchor consumidos pelo updater;
- ponteiro stable assinado;
- telemetria minima de sucesso/falha;
- kill switch;
- soak limpo sem excecao para futuras versoes;
- A/B ou solucao propria para imagem/media-system.

Esses itens nao devem bloquear V1 e V2 se a decisao de negocio for avancar com
risco aceito.

## PDCA Da Rodada

Plan:

- manter esta spec curta;
- escolher uma vertical por ciclo principal;
- abrir auditoria focada para a vertical, nao auditoria generica.

Do:

- implementar o menor slice que fecha valor;
- evitar refatoracao lateral;
- nao misturar player, core e imagem no mesmo patch sem necessidade.

Check:

- rodar gates existentes;
- adicionar teste quando o comportamento novo nao estiver coberto;
- testar na placa quando o risco envolver timer, boot, player ou rollback;
- abrir auditoria independente no fim do ciclo.

Act:

- registrar evidencia curta;
- atualizar esta spec somente se a regra operacional mudar;
- avancar outra vertical se a atual bloquear por detalhe que nao afeta as
  demais.

## Primeira Sequencia Recomendada

1. Feito: congelar esta spec como norte da rodada.
2. Feito: V2 com timer real para `totem-core`, no-op seguro e rollback.
3. Feito: V1 com imagem de producao, `player-runtime 9bebaf1` como baseline
   inicial aprovado e timer de `totem-core`.
4. Feito: placa gravada do zero e validada com auto-pull real do core.
5. Agora: executar V3 como proximo slice, porque o cliente quer atualizar player
   por auto-pull e aceita risco de negocio.
6. Em paralelo: registrar V4 minimo antes de entregar lote: inventario, rollback
   owner, emergencia e criterio de pausa.

## Caminho Minimo V3

1. Criar autorizacao de producao para o alvo exato `9bebaf1`, amarrando tag,
   version, source commit, payload SHA, manifest SHA, release gate, stable
   promotion, thaw decision e public activation.
2. Adicionar caminho publico no updater que aplica somente esse alvo autorizado,
   sem env lab e sem `latest` amplo.
3. Reusar o verify-then-promote existente: download, hash, extracao estreita,
   health real, marker, troca atomica de `current`, state e quarentena.
4. Abrir rollback publico apenas para estado governado/autorizado, preservando
   fallback de imagem e `previous`.
5. Criar timer ou service explicitamente componenteado para `player-runtime`,
   com lock/ordenacao para nao concorrer com `totem-core`.
6. Provar na placa: dry-run, apply automatico, deep-health, rollback, reapply
   no-op e negativos de alvo errado, hash errado, canal errado e ausencia de
   autorizacao.

## Definicao De Pronto Desta Spec

Esta spec esta pronta para orientar implementacao quando:

- as verticais forem aceitas como separadas;
- V1 e V2 forem reconhecidas como caminho minimo de producao;
- V3 for reconhecida como ponte necessaria para player auto-pull publico;
- os testes por vertical estiverem claros;
- nenhum requisito exigir perfeicao de roadmap para liberar a primeira entrega.
