# 194 - C20 Wizard E2E RC Method

## Objetivo

Consolidar o C20 como um RC de fluxo completo do wizard por `totem-core`, sem
transformar cada ajuste visual em uma entrega de produto isolada.

O alvo desta etapa e: o operador abre a configuracao, entende cada tela, navega
sem ambiguidade, ve bloqueios corretos, revisa o estado, sai/conclui sem quebrar
o player e deixa rollback pronto.

## Direcao Central

- C20.x sao incrementos validados para acumulo.
- O marco de produto e o **C20 Wizard E2E RC**.
- O RC deve provar a jornada completa, nao apenas telas bonitas.
- Qualidade inclui velocidade: bloquear so quando houver risco real para uso,
  seguranca, privacidade, rollback, player ou escopo.

## Frentes Que Andam Juntas

1. Jornada real: F10/settings, Tela, Conexao, Ambiente, Revisao, Concluir,
   cancelar/sair e retorno ao player.
2. Navegacao e foco: setas, Enter, Esc, menu superior, conteudo e estados
   bloqueados com foco visivel.
3. Copy e hierarquia: uma tarefa principal por tela, texto curto e sem painel
   tecnico.
4. Revisao e conclusao: resumo publico, bloqueio quando faltar algo obrigatorio
   e acao principal inequivoca.
5. Operacao da placa: player ativo depois, settings encerrado, sem service
   `failed`, sem lock/request residual.
6. Escopo OTA: somente `totem-core`; sem player-runtime, MPV, display/kernel,
   Wi-Fi real persistente, config real, timezone/NTP/RTC ou updater.
7. Evidencia: self-test, replay quando houver fluxo, galeria, captura real
   quando o claim depender da placa, gate OTA, apply e rollback.

## Pipeline De Claims

Cada rodada declara o claim antes de implementar:

- visual: galeria/preview ajuda; captura real decide quando a placa importa;
- fluxo/teclado: replay e, para claim real, navegacao na placa;
- pacote: manifest, payload hash e gate OTA;
- operacional: player volta, settings limpa, current/previous coerentes;
- privacidade: nenhuma senha, token, API URL, IP privado, SSID sensivel ou
  config real em UI/evidencia publica.

SVG gerado e evidencia auxiliar. Captura preta, antiga ou sem vinculo com o
pacote nao aprova claim visual.

## Blockers

Bloqueia a rodada:

- self-test, replay relevante ou gate OTA vermelho;
- F10/settings trava ou mostra terminal indevido;
- `Esc`, cancelar ou concluir nao restauram o player;
- `totem-open-settings.service` fica `failed`;
- lock/request residual apos sair;
- revisao permite candidata parcial quando esta pendente/bloqueada;
- foco/rodape/copy induz acao errada;
- vazamento de segredo ou dado privado;
- escrita real fora do escopo declarado;
- current/previous ou rollback incoerentes;
- captura decisiva ausente, preta ou nao vinculada ao pacote aplicado.

## Nao-Blockers

Nao bloqueia, vira backlog:

- microcopy melhoravel mas compreensivel;
- ajuste fino de cor, espacamento ou polimento sem afetar leitura/acao;
- sugestao de redesign amplo fora da vertical;
- ausencia de recurso explicitamente fora de escopo, como ajuste de hora,
  Wi-Fi real persistente ou NTP;
- cobertura de caso exotico que nao representa uso real do operador.

## Cadencia PDCA

1. Plan: declarar claim, escopo, non-claims e criterios de pronto.
2. Do: implementar somente o necessario em `totem-core`.
3. Check: self-test, replay se houver fluxo, galeria, inspeccao visual e placa
   quando o claim for real.
4. Act: aceitar para acumulo, corrigir ou reverter. Registrar evidencia curta.

Auditorias independentes entram quando houver mudanca de navegacao, risco de
escopo, RC consolidado ou divergencia real. Nao sao obrigatorias para microcopy.

## C20 Wizard E2E RC - Definicao De Pronto

- Um pacote RC consolidado de `totem-core` existe e passa gate OTA.
- A placa aplica o RC e mantem rollback para a versao anterior.
- Roteiro E2E real passa na placa:
  - F10 abre settings;
  - navegacao percorre Tela, Conexao, Ambiente e Revisao;
  - Revisao bloqueia incompleto;
  - fluxo valido chega a Concluir ou cancela de forma clara;
  - player volta ativo;
  - settings fica inativo;
  - sem lock/request residual;
  - sem dados privados expostos.
- Replay offline cobre os cenarios principais conhecidos.
- Galeria visual cobre todas as telas principais.
- Capturas reais existem para estados criticos.
- O plano registra claramente que isso nao e stable/producao por inferencia e
  nao valida Wi-Fi/config real se essa escrita continuar fora de escopo.

## Proximo Passo

Executar uma auditoria E2E do wizard atual em C20.8, classificar achados por
blocker/non-blocker/backlog e entao gerar o proximo pacote somente com os
ajustes que movem o RC.

