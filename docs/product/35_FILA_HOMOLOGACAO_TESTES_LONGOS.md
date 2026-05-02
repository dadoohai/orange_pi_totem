# Fila de homologacao - testes longos

Status: fila de homologacao. Nao executa testes e nao libera producao.

Data: 2026-05-02

## 1. Objetivo

Este documento separa testes longos de desenvolvimento incremental. Ele existe
para garantir que os testes longos nao sejam esquecidos e para deixar claro que
producao continua bloqueada.

C6.4 passou como smoke curto de desenvolvimento. Essa evidencia nao substitui
homologacao, segunda placa/cartao, observacao prolongada, reboot/autoboot,
root read-only, corte seco ou validacao de campo.

## 2. Lista de testes longos/futuros

| Teste | Objetivo | Pre-condicao | Evidencia esperada | Risco | Obrigatorio antes de producao |
| --- | --- | --- | --- | --- | --- |
| Observer 30-60 min com config real | Validar estabilidade curta alem do smoke C6.4. | Config real ativa, servico controlado, politica de evidencia sanitizada aprovada. | README sanitizado com duracao, estado final, `NRestarts`, player/MPV, erros publicos e ausencia de secrets. | Tratar 120s como estabilidade suficiente. | Sim |
| Observer varias horas | Detectar vazamento de memoria, travamento, drift de playback, falhas de polling/cache e acumulacao de logs. | Observer 30-60 min aprovado ou decisao documentada de pular direto para longa duracao. | Evidencia sanitizada com amostras periodicas, estado final, restarts, playback e filtros criticos. | Falhas que so aparecem apos horas irem para campo. | Sim |
| Reboot/autoboot com config real | Validar que o appliance sobe sozinho com config real e chega a `player_running`. | Config real valida, servico habilitado, roteiro de reboot aprovado em homologacao. | Evidencia sanitizada de boot, estado publico, player, MPV, `NRestarts` e filtros criticos. | Smoke manual mascarar falha de autoboot. | Sim |
| Queda/retorno de rede | Verificar se perda e retorno de rede nao travam player nem vazam dados sensiveis. | Contrato de estados de rede aprovado e evidencia sem SSID/IP/URL real. | Estado antes/durante/depois, player/cache, recuperacao e ausencia de output bruto sensivel. | Rede instavel derrubar player ou gerar loop. | Sim |
| API indisponivel | Validar falha de backend sem expor URL/payload e sem quebrar reproducao local quando houver cache. | Politica de privacidade para backend aprovada, sem publicar endpoint real. | Estado publico seguro, retry/erro agregado, player/cache e ausencia de payload/log bruto. | Dependencia de backend bloquear exibicao. | Sim |
| Cache/offline | Validar reproducao com conteudo local quando rede/API nao estao disponiveis. | Midias/cache ja provisionados e criterios de evidencia sem paths privados. | Playback, playlist agregada, erros publicos e comportamento de recuperacao. | Campo sem internet ficar sem exibicao apesar de cache. | Sim |
| Segunda placa/cartao | Reproduzir a configuracao em hardware/cartao adicional. | Placa/cartao de homologacao preparados e H2testw registrado. | Checklist de homologacao, observer e diferencas sanitizadas entre placas. | Resultado da placa de desenvolvimento nao ser reproduzivel. | Sim |
| Root read-only | Validar root protegido com estado mutavel em `/data` e `/tmp`. | Paths de app/config/cache/log estabilizados e plano de overlay aprovado. | Boot, escrita esperada somente em paths permitidos e ausencia de erro EXT4/remount. | Corte seco corromper root gravavel em campo. | Sim |
| Corte seco | Validar retorno apos desligamento abrupto somente depois de root read-only. | Root read-only aprovado, rollback/config/cache definidos e acesso fisico. | Ciclos documentados, boot posterior, config/cache intactos e filtros criticos limpos. | Testar corte antes da hora e corromper estado. | Sim |
| Rollback real | Provar restauracao de ultima config valida diante de falha real ou simulada controlada. | Backup real existente, servico controlado e criterio de falha/retorno aprovado. | Evidencia agregada de rollback, revalidacao, permissao e estado final. | Backup existir mas nao recuperar operacao. | Sim |
| Teste com player rodando em cenario prolongado | Observar player real com config real sob duracao representativa. | Config real ativa, observer longo aprovado e evidencia sem secrets. | Estado final, playback, MPV, `kiosk.py`, restarts, filtros criticos e sanitizacao. | Player passar no start e falhar em uso continuo. | Sim |
| Validacao visual de `player_error` | Verificar estado visual de erro sem conflito DRM/KMS e sem loop indevido. | Criterio de inducao de erro aprovado, sem publicar logs privados. | Evidencia visual sanitizada, renderer/player separados e recuperacao definida. | Erro operacional ficar invisivel ou disputar tela com player. | Sim |
| Validacao de systemd/HDMI/config real na placa de homologacao | Repetir fluxo integrado fora da placa de desenvolvimento. | Segunda placa/cartao, config real privada, servico e HDMI controlados. | Estado `player_running`, HDMI conectado/ausente quando aplicavel, `NRestarts` e filtros criticos. | Desenvolvimento ser confundido com homologacao. | Sim |

## 3. Relacao com v0.1-rc1

- A homologacao `v0.1-rc1` continua separada.
- Alguns testes de homologacao podem reaproveitar evidencias de
  desenvolvimento como referencia, mas nao sao substituidos por elas.
- Segunda placa/cartao continua obrigatoria antes de producao.

Esta fila nao muda a RC1 e nao autoriza execucao operacional por si so. Cada
teste precisa de roteiro proprio, aprovacao humana quando envolver placa,
evidencia sanitizada e criterios de abortar.
