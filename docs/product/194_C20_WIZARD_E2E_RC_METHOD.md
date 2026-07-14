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

## Rodada C20.8 E2E - Resultado Inicial

Evidencia:
`docs/evidence/c20-e2e-rc/20260708T052100Z-c20-8-e2e-audit/`.

Resultado: a primeira rodada E2E fechou os guardrails principais do wizard na
placa.

Ficou provado:

- trigger F10 por evento de teclado abre settings;
- wizard abre em framebuffer real;
- navegacao chega em `Revisao`;
- revisao bloqueia incompleto e nao gera candidata parcial;
- `Enter` nao salva quando faltam conexao/ambiente;
- cancelamento retorna ao player;
- apos espera curta, settings fica inativo, sem lock/request e com guard verde;
- current/previous de `totem-core` permanecem coerentes.

Tambem ficou provado por scripted `candidate-only` que o fluxo valido pode gerar
candidata sem writer real, sem Wi-Fi real e sem backend.

Nao ficou provado nesta rodada: escrita real de Wi-Fi/config, publish remoto,
stable/producao, player-runtime, display/kernel/MPV, timezone/NTP/RTC ou imagem
final.

Achado nao-blocker: logo apos cancelar, a unit pode aparecer
transitoriamente como `activating`; o estado limpa apos espera curta.

## Proximo Passo

Usar a evidencia C20.8 como base do RC e escolher a proxima acao por valor:

1. se o objetivo for liberar pacote de UX, consolidar os scripts de QA e rodar
   gate/commit;
2. se o objetivo for RC completo de setup, decidir se o teste de escrita real
   de Wi-Fi/config entra agora ou se o criterio segue `candidate-only`;
3. se houver nova melhoria visual, entrar somente se mover clareza/uso real e
   repetir o ritual E2E sem regressao.

## Status Atual Do RC - 2026-07-14

O metodo foi aplicado ate o pacote C20.14. A jornada mutante real passou na
prod12 com QR, writer e retorno ao player; cancelamento preservou configuracao;
parada externa da unit ficou limitada e limpa; apply, rollback e reaplicacao
mantiveram current/previous coerentes. O reboot final terminou com um unico MPV,
hardware decode esperado e health verde.

Pacote final desta rodada:
`c20.14-settings-stop-hardening-20260714T034217Z-22bd473`.

Evidencia:
`docs/evidence/c20-totem-core-ota/20260714T042600Z-c20-14-settings-stop-hardening-board-e2e/`.

O RC esta fechado para entrar na prod13. Permanecem fora desta claim a promocao
`stable`, publicacao remota e o aceite da prod13 antes de build, auditoria e
flash controlado.
