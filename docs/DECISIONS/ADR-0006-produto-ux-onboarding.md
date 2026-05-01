# ADR-0006 - Produto/UX e onboarding do totem

## Status

Proposta.

## Contexto

A base tecnica do totem Orange Pi Zero 3 avancou para um runtime minimo com MPV
via DRM/KMS direto, sem desktop, Xorg, Wayland, compositor ou Chromium. O
`kiosky-player` ja foi validado manualmente com a configuracao candidata, e a
placa de desenvolvimento aprovou `systemd` start/stop, autoboot e a estrategia
de HDMI ausente/reconexao por launcher.

Essa base ainda nao e um produto operavel por pessoas nao tecnicas. O operador
nao deve depender de terminal para configurar Wi-Fi, ativar ambiente/unidade,
ajustar rotacao, entender falhas, reiniciar servicos, coletar diagnostico ou
executar reset.

A homologacao `v0.1-rc1` em segunda placa/cartao continua separada da evolucao
de produto/UX.

## Decisao

Construir a UX em camadas.

1. Comecar por status/splash local minimo com identidade Dadooh e estados
   legiveis.
2. Manter setup e manutencao separados do player.
3. Usar setup por celular/hotspot para primeiro boot, Wi-Fi e ativacao.
4. Nao transformar o player no configurador principal.
5. Continuar sem Chromium, desktop ou compositor na primeira fase de produto.
6. Concentrar estado mutavel em `/data` e `/tmp`.
7. Evitar secrets em logs, status compartilhavel, docs e diagnosticos.

O launcher deve orquestrar estados locais e decidir quando iniciar player,
status/splash, setup ou manutencao. O `kiosky-player` deve continuar focado em
playlist, cache, MPV, watchdog e status proprio.

## Consequencias

- A primeira entrega visual sera simples, mas recuperavel e rastreavel.
- O risco de quebrar a reproducao aprovada diminui, porque setup/manutencao
  ficam fora do loop principal do player.
- Sera necessario definir contratos de status entre launcher, player, splash,
  setup, manutencao e telemetria.
- O fluxo de ativacao deve exigir backend ou endpoint de provisionamento para
  trocar codigo por config segura.
- A ausencia de Chromium reduz superficie de ataque e consumo, mas exige UI
  local mais simples e testada em celular.
- Factory reset e diagnostico precisam de desenho cuidadoso para nao apagar
  evidencias nem vazar dados privados.

## Alternativas consideradas

### Chromium local

Rodar uma UI local completa em Chromium facilitaria telas ricas, mas adiciona
desktop/compositor ou stack grafica extra, consumo maior e uma superficie de
falha que ainda nao foi validada na base atual. Fica fora da primeira fase.

### Configurar por terminal

E rapido para bancada, mas nao atende operador nao tecnico, nao escala em campo
e aumenta risco de publicar ou digitar secrets incorretamente.

### App player monolitico

Adicionar Wi-Fi, ativacao, manutencao e reset dentro do `kiosky-player` reduziria
numero de processos, mas misturaria responsabilidades e aumentaria o risco de
regressao na reproducao 24/7.

### Portal remoto apenas

Um portal remoto ajuda monitoramento, mas nao resolve primeiro boot sem internet,
troca de Wi-Fi local, HDMI ausente, config ausente ou manutencao em ambiente
isolado.

## Proximos passos

1. Definir contrato de status agregado sem dados privados.
2. Implementar status/splash Dadooh minimo e validar que nao disputa DRM/KMS com
   o player.
3. Criar manutencao local basica com comandos limitados.
4. Projetar hotspot/setup por celular com NetworkManager.
5. Definir ativacao por codigo e escrita atomica de config em `/data/config`.
