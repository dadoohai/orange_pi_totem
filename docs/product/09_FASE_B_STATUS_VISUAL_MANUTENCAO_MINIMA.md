# Fase B - status visual e manutencao minima

Status: planejamento. Nao implementa mudancas.

Data: 2026-05-01

## Objetivo

Transformar a primeira tela tecnica da Fase A em uma experiencia visual de
produto mais clara, consistente e preparada para manutencao minima, ainda sem
implementar Wi-Fi, hotspot ou portal completo.

A Fase B deve manter a regra operacional validada: qualquer renderer visual
precisa sair antes do MPV principal do player assumir DRM/KMS.

## Escopo

Incluido:

- melhorar a tela `config_missing`;
- padronizar mensagens publicas Dadooh;
- criar codigos publicos de estado para operador e suporte;
- preparar area visual para QR code futuro, sem gerar QR funcional ainda;
- definir manutencao minima e seus limites;
- planejar `player_error` visual sem habilitar comportamento arriscado sem
  teste dedicado;
- manter contrato de privacidade e sanitizacao.

Manutencao minima nesta fase significa desenhar e especificar um modo local
limitado para:

- ver estado publico agregado;
- identificar codigo publico de erro;
- confirmar se display/config/player/servico estao em estado esperado;
- preparar comandos futuros de reiniciar player e coletar diagnostico
  sanitizado;
- definir textos e fluxo antes de implementar a camada de execucao.

## Fora de escopo

- hotspot Wi-Fi;
- portal local completo;
- ativacao backend;
- troca de config por codigo;
- escrita real de `/data/config/config.json` por operador;
- factory reset real;
- reset leve operacional;
- coleta automatica de diagnostico por interface;
- telemetria;
- instalacao de pacotes;
- Chromium, desktop, Xorg, Wayland ou compositor.

## Estados visuais

### config_missing

Estado principal da Fase B. A tela deve informar que a configuracao esta
pendente, sem expor config privada e sem sugerir comandos de terminal.

Elementos esperados:

- marca Dadooh;
- titulo curto: "Configuracao pendente";
- texto de acao: "Acione a manutencao autorizada para concluir a ativacao.";
- codigo publico: `CONFIG_MISSING`;
- area reservada para QR code futuro;
- indicador simples de que o player esta parado por seguranca.

### display_missing, quando display voltar

Enquanto o display esta ausente, nao ha tela fisica para exibir. Quando o HDMI
voltar, o launcher deve reavaliar o estado atual:

- se config valida, iniciar player e nao mostrar renderer persistente;
- se config ausente, mostrar `config_missing`;
- se houver erro de player futuro, mostrar `player_error`.

O status local deve continuar publicando `DISPLAY_MISSING` para manutencao e
telemetria futura.

### player_error

Estado planejado para falha recuperavel do player. Deve ser visualmente
distinto de `config_missing`, mas sem mostrar stack trace, paths, URL, payload
ou nome privado de midia.

Elementos esperados:

- marca Dadooh;
- titulo curto: "Exibicao indisponivel";
- codigo publico: `PLAYER_EXITED` ou outro codigo allowlisted;
- mensagem: "O sistema tentara reiniciar automaticamente.";
- contador ou texto de retry apenas se vier de fonte publica segura.

Habilitar esse estado no renderer operacional exige teste dedicado de parada do
renderer antes de cada tentativa de reiniciar o player.

### maintenance_placeholder

Estado reservado para manutencao local minima. Na Fase B, deve ficar definido
como experiencia e contrato, nao como painel completo.

Elementos esperados:

- marca Dadooh;
- titulo: "Manutencao local";
- lista curta de estado publico: display, configuracao, player, servico;
- codigo publico do estado atual;
- area reservada para QR code futuro;
- nenhum botao real de reset ou shell.

## Codigos publicos

Codigos iniciais esperados:

- `CONFIG_MISSING`: config ausente, invalida ou incompleta.
- `DISPLAY_MISSING`: display nao detectado.
- `PLAYER_EXITED`: player saiu ou falhou de forma recuperavel.
- `PLAYER_STATUS_STALE`: status do player nao convergiu no prazo.
- `SERVICE_FAILED`: servico local falhou.
- `UNKNOWN_ERROR`: fallback generico, sem detalhe privado.

Codigos publicos devem ser estaveis, curtos e independentes de mensagens brutas
de excecao.

## Proposta de layout

Layout base 16:9, sem depender de navegador:

- faixa superior discreta com cor por estado;
- marca Dadooh no canto superior esquerdo;
- bloco central com titulo grande e mensagem curta;
- codigo publico em area secundaria, legivel a distancia;
- area lateral ou inferior reservada para QR code futuro;
- rodape com estado publico e horario de atualizacao;
- nenhum path local, URL, identificador privado, SSID ou dado de config.

Diretrizes:

- texto curto, sem instrucoes tecnicas extensas;
- contraste alto;
- legibilidade em 720p;
- evitar depender de fontes externas;
- manter SVG auto-contido;
- preservar sanitizacao por allowlist.

## Criterios de aceite

- A tela `config_missing` fica mais clara que a A1.4 e mantem Dadooh como sinal
  visual principal.
- `status.json` e `status.svg` continuam sem dados sensiveis.
- Renderer nao roda em `player_running`.
- Renderer nao roda sem display.
- Renderer para antes de qualquer inicio de `kiosk.py`.
- `player_running` apos restauracao mantem IPC sem timeout em observer curto.
- `systemctl --failed=0`.
- Nenhuma dependencia grafica nova e instalada.
- Nenhuma mudanca no `kiosky-player`.
- Nenhum `.tar.gz`, `raw/` ou `extracted/` entra no Git.

## Plano de teste

Validacao local:

- gerar previews SVG para `config_missing`, `player_error` e
  `maintenance_placeholder`;
- checar sanitizacao de SVG e JSON;
- manter smoke do launcher cobrindo renderer fake;
- `git diff --check`.

Validacao em placa de desenvolvimento, quando implementacao for aprovada:

- deploy apenas na placa de desenvolvimento;
- testar `config_missing` com override temporario de config inexistente;
- confirmar visualmente layout novo;
- confirmar `kiosk.py=0`, MPV principal `0`, renderer `1`;
- remover override e restaurar player;
- confirmar renderer `0`, `kiosk.py=1`, MPV principal `1`;
- observer curto de 2 a 3 minutos com IPC success, timeout `0` e aliases
  avancando;
- `systemctl --failed=0`;
- filtro critico de kernel limpo;
- README de evidencia sanitizado.

Validacao de `player_error` so deve ocorrer em rodada separada, com falha
controlada e criterio explicito de retry.

## Rollback

Rollback deve manter o comportamento A1.4:

- `config_missing` simples continua disponivel;
- renderer ausente nao derruba o launcher;
- config valida volta para `player_running`;
- sem HDMI continua `display_missing`;
- sem config continua sem iniciar `kiosk.py` ou MPV principal.
