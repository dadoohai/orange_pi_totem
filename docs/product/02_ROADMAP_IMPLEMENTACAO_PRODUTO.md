# Roadmap de implementacao produto/UX

Status: proposta incremental. Nao implementa mudancas.

Data: 2026-04-30

Este roadmap separa a evolucao de produto/UX da homologacao `v0.1-rc1`. A RC1
continua focada em reproduzir a base tecnica validada em outra placa/cartao. As
fases abaixo devem ser implementadas em passos pequenos, sempre mantendo o
player atual recuperavel.

## Fase A - status/splash local minimo

Objetivo:

- mostrar Dadooh e estado atual;
- esconder terminal/logs do operador;
- continuar sem Chromium, desktop ou compositor;
- ainda sem onboarding;
- nao quebrar o player.

Arquivos provaveis:

- `scripts/board/kiosky_service_launcher.sh`;
- `scripts/board/kiosky-player.service`;
- novo componente `totem-status-splash`;
- assets locais em `/opt/totem/assets`;
- contrato de status em `/tmp` e `/data/state`.

Validacao minima:

- boot com HDMI conectado mostra splash/status antes do player;
- player entra em `playing` como hoje;
- boot sem HDMI continua em `display_missing` sem iniciar app/MPV;
- reconectar HDMI inicia app automaticamente;
- `systemctl --failed=0`;
- sem escrita em `/opt/totem/kiosky-player`.

Riscos:

- disputa pelo DRM/KMS entre splash e MPV;
- splash atrasar ou bloquear o player;
- status mostrar dados privados.

Criterios de aceite:

- identidade Dadooh visivel nos estados nao-player;
- terminal/logs nao aparecem como UX normal;
- metricas do player permanecem iguais as rodadas aprovadas;
- status local sanitizado.

Criterio de rollback:

- desabilitar o servico/componente de splash e voltar ao launcher atual que
  inicia apenas o player quando ha HDMI.

## Fase B - manutencao local basica

Objetivo:

- reiniciar player;
- reiniciar placa;
- baixar diagnostico;
- ver estado agregado;
- executar reset leve.

Arquivos provaveis:

- novo servico `totem-maintenance`;
- nova unit `totem-maintenance.service`;
- wrapper de diagnostico sanitizado baseado em `collect_diag.sh`;
- endpoint local restrito;
- arquivos de estado em `/data/state/totem`.

Validacao minima:

- interface local mostra estado do launcher, player, rede, disco e versoes;
- reiniciar player para e sobe `kiosky-player.service`;
- baixar diagnostico nao inclui secrets, URLs privadas, IDs privados, payloads
  privados ou paths reais de midia;
- reset leve preserva config essencial e limpa apenas estados/cache definidos.

Riscos:

- comandos amplos virarem shell remoto;
- diagnostico vazar dados privados;
- reset leve apagar midia/config necessaria para recovery.

Criterios de aceite:

- operador consegue executar manutencao sem terminal;
- todas as acoes sao limitadas e auditaveis;
- diagnostico e sanitizado por padrao.

Criterio de rollback:

- parar/desabilitar `totem-maintenance.service`; manter `kiosky-player.service`
  operando.

## Fase C - Wi-Fi/setup

Objetivo:

- criar hotspot Dadooh Setup;
- exibir QR code;
- permitir configuracao via celular;
- salvar Wi-Fi;
- testar conexao.

Arquivos provaveis:

- novo servico `totem-setup`;
- perfis NetworkManager dedicados;
- scripts/wrappers de NetworkManager;
- status de setup em `/data/state/totem`;
- pagina local de setup.

Validacao minima:

- sem rede/config, hotspot sobe com nome previsivel e nao sensivel;
- celular acessa portal local via QR code;
- operador seleciona rede, informa senha e testa conexao;
- senha errada mostra erro recuperavel;
- reboot preserva conexao salva;
- Ethernet, se presente, nao e derrubada indevidamente.

Riscos:

- hotspot interferir em redes salvas;
- senha Wi-Fi aparecer em logs/status;
- captive portal falhar em celulares especificos;
- NetworkManager entrar em estado ambiguo entre AP e cliente.

Criterios de aceite:

- configuracao Wi-Fi completa sem terminal;
- nenhum segredo aparece em docs, logs compartilhaveis ou diagnostico
  sanitizado;
- queda e retorno de internet ficam legiveis para operador.

Criterio de rollback:

- remover/desabilitar perfis de hotspot/setup e voltar a conexoes
  NetworkManager provisionadas manualmente.

## Fase D - ativacao de ambiente

Objetivo:

- ativar por codigo;
- evitar digitacao manual de `api_key`;
- backend troca codigo por config;
- salvar config em `/data/config`.

Arquivos provaveis:

- endpoint/pagina de ativacao no `totem-setup`;
- writer atomico de `/data/config/config.json`;
- schema publico sem secrets;
- estado de ativacao em `/data/state/totem`;
- integracao backend para troca de codigo.

Validacao minima:

- sem config, tela mostra codigo/QR e estado claro;
- codigo valido baixa config e grava com permissao restrita;
- codigo invalido/expirado mostra erro recuperavel;
- player inicia depois da config valida;
- nenhum segredo e impresso.

Riscos:

- backend indisponivel bloquear ativacao;
- config parcial quebrar boot;
- permissao fraca em `/data/config/config.json`;
- operador digitar dados errados se houver fallback manual.

Criterios de aceite:

- operador nao manipula `api_key`;
- config e validada antes de substituir a anterior;
- rollback local preserva ultima config valida.

Criterio de rollback:

- restaurar ultima config valida de `/data/config` e desabilitar ativacao por
  codigo ate corrigir backend/setup.

## Fase E - rotacao/resolucao

Objetivo:

- suportar rotacao 0/90/180/270;
- oferecer teste visual;
- salvar preferencia;
- reiniciar player quando necessario.

Arquivos provaveis:

- pagina de manutencao/setup;
- config em `/data/config/config.json`;
- status/splash para teste visual;
- possivel config separada `/data/config/display.json`.

Validacao minima:

- operador escolhe 0, 90, 180 ou 270;
- teste visual confirma orientacao;
- valor persiste apos reboot;
- MPV aplica `--video-rotate` ou propriedade equivalente;
- erro de valor invalido cai para padrao seguro.

Riscos:

- rotacao quebrar layout do splash/status;
- resolucao/tela especifica exigir ajuste fora do MPV;
- reinicio do player durante reproducao confundir operador.

Criterios de aceite:

- rotacao muda sem terminal;
- estado final e claro para operador;
- player volta a `playing`.

Criterio de rollback:

- voltar `rotation_deg=0` ou ultima config valida e reiniciar player.

## Fase F - monitoramento/telemetria

Objetivo:

- reportar estado online;
- uptime;
- temperatura;
- disco;
- versao app;
- versao imagem;
- ultimo erro;
- `display_missing`.

Arquivos provaveis:

- agregador de status do appliance;
- contrato de payload de telemetria;
- spool opcional em `/data/spool/totem`;
- extensao do diagnostico sanitizado;
- config de telemetria sem token hardcoded.

Validacao minima:

- payload nao contem secrets, URLs privadas ou paths reais de midia;
- sem internet, telemetria falha sem afetar player;
- retorno da internet retoma envio;
- `display_missing`, disco cheio, temperatura alta e ultimo erro aparecem no
  estado agregado.

Riscos:

- vazamento de dados privados;
- telemetria gerar escrita excessiva;
- token de telemetria mal provisionado;
- backend interpretar estados de forma diferente do totem.

Criterios de aceite:

- dashboard/backend consegue distinguir online, offline, sem HDMI, sem config e
  erro de player;
- falha de telemetria nao reinicia player.

Criterio de rollback:

- desligar telemetria do appliance por config e manter status local/diagnostico.

## Fase G - update/rollback

Objetivo:

- armazenar releases em `/opt/totem/releases`;
- usar symlink ativo;
- permitir rollback.

Arquivos provaveis:

- `/opt/totem/releases/<versao>`;
- `/opt/totem/current`;
- unit apontando para symlink ativo;
- comando de update controlado;
- manifesto de release;
- estado de rollback em `/data/state/totem`.

Validacao minima:

- instalar nova release sem alterar `/data/config`;
- healthcheck pos-update passa antes de confirmar;
- rollback volta a release anterior;
- falha no boot retorna para release anterior ou entra em manutencao.

Riscos:

- symlink quebrado deixar player fora;
- update parcial em queda de energia;
- incompatibilidade entre config antiga e app novo;
- falta de espaco em `/opt` ou `/data`.

Criterios de aceite:

- update e rollback funcionam sem terminal;
- versao app/imagem aparecem no status;
- corte de energia durante update nao corrompe release ativa.

Criterio de rollback:

- apontar symlink ativo para release anterior validada e reiniciar servico.

## Fase H - root read-only/corte seco

Objetivo:

- ativar root read-only depois de logs, cache e config estabilizados;
- validar corte seco em condicoes controladas.

Arquivos provaveis:

- overlay/customizacao da imagem;
- ajustes de `/var/log`, `/tmp` e `/data`;
- units de montagem;
- documentacao de teste de corte seco;
- politicas de log/cache.

Validacao minima:

- boot normal com root protegido;
- player grava somente em `/data` e `/tmp`;
- diagnostico confirma ausencia de escrita inesperada em root;
- ciclos de desligamento abrupto nao causam erro EXT4, remount read-only ou
  perda de config;
- factory reset continua funcionando.

Riscos:

- caminho mutavel esquecido em root;
- diagnostico/logs insuficientes para suporte;
- reset/update incompatibilizar com root read-only;
- teste de corte seco antes da hora mascarar causa de falha.

Criterios de aceite:

- sistema volta a operar apos cortes repetidos;
- `/data` contem todo estado mutavel necessario;
- rollback/update/reset continuam testados.

Criterio de rollback:

- voltar imagem para root gravavel de bancada e corrigir paths mutaveis antes de
  repetir corte seco.
