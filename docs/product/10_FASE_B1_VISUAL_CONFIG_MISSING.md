# Fase B1 - visual config_missing

Status: implementacao local em andamento. Ainda requer validacao em placa de
desenvolvimento antes de revisao final.

Data: 2026-05-01

## Objetivo

Refinar a tela publica `config_missing` para parecer um produto Dadooh em campo,
nao uma placa Linux em bancada. A B1 melhora apenas a apresentacao visual e os
textos publicos do renderer SVG, mantendo o contrato v0 e a regra operacional
validada na Fase A: renderer visual e player principal nao rodam juntos.

## Racional UX

A tela A1.4 atual mostra:

- marca textual Dadooh;
- rotulo publico "Totem Dadooh";
- "Configuracao pendente" como rotulo e tambem como mensagem principal;
- dica para acionar manutencao autorizada;
- rodape com `config_missing` e horario de atualizacao.

A hierarquia visual e funcional, mas ainda simples demais para operador nao
tecnico. O texto repetido reduz clareza, o codigo publico `CONFIG_MISSING` nao
aparece com destaque, e a tela nao separa claramente motivo, acao e seguranca do
player. Tambem nao havia uma area reservada para configuracao futura.

O risco de parecer erro tecnico era moderado: embora nao mostrasse stack trace,
o layout claro e seco parecia mais uma tela de diagnostico do que uma tela de
produto. O risco de sugerir acao inexistente era baixo, porque nao havia QR nem
botao, mas tambem nao preparava o operador para o fluxo assistido futuro.

Na B1, a tela passa a priorizar:

- marca Dadooh visivel no primeiro olhar;
- titulo grande e humano;
- mensagem curta de motivo;
- acao unica para operador;
- codigo publico legivel para suporte;
- estado explicito "Player parado com segurança";
- area lateral de "Configuração assistida" marcada como "Em breve", sem QR
  funcional.

## Antes e depois conceitual

Antes:

- painel claro simples;
- estado repetido como titulo e mensagem;
- sem codigo publico destacado;
- sem indicacao visual de parada segura do player;
- sem area preparada para setup futuro.

Depois:

- fundo escuro/neutro de alto contraste;
- bloco principal com titulo, motivo, acao, estado seguro e codigo publico;
- area lateral reservada para configuracao assistida futura;
- texto "Sem QR ativo agora" para nao induzir escaneamento;
- rodape discreto com estado publico e horario.

## Conteudo da tela config_missing

Conteudo publico esperado:

- Marca: "Dadooh";
- Titulo: "Configuração pendente";
- Mensagem: "Este totem ainda não foi ativado.";
- Acao: "Acione a equipe responsável para concluir a configuração.";
- Estado de seguranca: "Player parado com segurança";
- Codigo publico: `CONFIG_MISSING`;
- Rodape: estado publico `config_missing` e timestamp de atualizacao.

Nao aparecem dados privados, URLs, identificadores de ambiente/unidade, SSID,
paths locais, payloads, excecoes brutas ou stack trace.

## Hierarquia visual

A hierarquia visual foi organizada para leitura a distancia em 1280x720:

1. Marca textual Dadooh no topo.
2. Titulo grande do estado.
3. Mensagem curta com o motivo.
4. Acao unica para operador nao tecnico.
5. Indicador de seguranca do player.
6. Codigo publico para suporte.
7. Area lateral de configuracao assistida futura.
8. Rodape discreto de estado/atualizacao.

O visual usa SVG auto-contido, sem imagens externas, sem fontes externas e sem
dependencia de internet, desktop, compositor, Chromium, Xorg ou Wayland.

## Estados com preview

A B1 mantem previews locais para consistencia visual:

- `/tmp/totem-status-b1-config_missing.svg`;
- `/tmp/totem-status-b1-display_missing.svg`;
- `/tmp/totem-status-b1-player_error.svg`;
- `/tmp/totem-status-b1-maintenance_placeholder.svg`;
- `/tmp/totem-status-b1-player_running.svg`.

`player_running` e gerado apenas para consistencia visual. Operacionalmente, o
renderer nao deve permanecer ativo nesse estado.

`player_error` e `maintenance_placeholder` continuam como estados planejados ou
reservados. Habilitar `player_error` no renderer operacional ainda exige rodada
dedicada de retry e ordem de parada/inicio.

## Regras de privacidade

O SVG e o JSON publico continuam allowlisted. A B1 nao deve publicar:

- `api_url`;
- `api_key`;
- `environment_id`;
- `station_id`;
- URLs privadas;
- payloads privados;
- paths reais;
- nomes privados;
- SSID;
- IP publico;
- tokens, headers, cookies ou senhas.

Os textos livres renderizados passam por sanitizacao basica e devem continuar
vindo de mensagens publicas controladas.

## Por que nao ha QR funcional

O QR funcional fica fora da B1 porque exigiria setup local real: endpoint,
hotspot ou rede acessivel, regras de expiracao, seguranca do codigo e fluxo de
ativacao. Desenhar um QR falso seria pior para campo, porque induziria o
operador a escanear algo inexistente.

Por isso a area lateral mostra apenas "Configuração assistida", "Em breve" e
"Sem QR ativo agora".

## Fora de escopo

A B1 nao implementa:

- Wi-Fi setup;
- hotspot;
- portal local;
- ativacao backend;
- escrita real de config por operador;
- reset;
- manutencao operacional;
- player_error operacional;
- telemetria;
- instalacao de pacotes;
- mudancas no `kiosky-player`.

## Criterios de aceite

- `config_missing` mostra Dadooh, "Configuração pendente", mensagem clara,
  acao unica, `CONFIG_MISSING` e "Player parado com segurança".
- Area de configuracao futura existe sem QR funcional e sem sugerir
  escaneamento.
- SVG gerado em 1280x720 e legivel em 720p.
- `status.json` e `status.svg` continuam sanitizados.
- Contrato v0 nao ganha campo novo.
- `display_missing` nao inicia app, MPV principal ou renderer.
- `config_missing` nao inicia `kiosk.py` nem MPV principal.
- Renderer para antes de qualquer inicio do player.
- `player_running` nao mantem renderer ativo.
- Nenhum pacote novo e instalado.
- Nenhuma mudanca e feita no `kiosky-player`.

## Rollback

Rollback visual:

- restaurar `scripts/board/totem_status_render_preview.py` para o layout A1.4;
- manter o agregador e launcher atuais;
- reiniciar o servico na placa de desenvolvimento apos reimplante.

Rollback operacional continua igual ao da A1.4: remover ou renomear o renderer
em `/opt/totem/bin` faz o launcher continuar publicando `config_missing` sem
iniciar o player.

## Plano de validacao em placa

Usar apenas a placa de desenvolvimento.

1. Fazer deploy dos scripts para os caminhos operacionais.
2. Aplicar override temporario apontando para config inexistente, sem alterar a
   config real.
3. Reiniciar o servico.
4. Confirmar `active`, estado publico `config_missing`, `status.json` e
   `status.svg` gerados.
5. Confirmar renderer ativo, `kiosk.py=0` e MPV principal `0`.
6. Confirmar sanitizacao e `systemctl --failed=0`.
7. Obter observacao humana da tela.
8. Remover override temporario e reiniciar o servico.
9. Confirmar renderer `0`, `kiosk.py=1`, MPV principal `1` e estado
   `player_running`.
10. Rodar observer curto de 2 a 3 minutos com IPC success, timeout `0` e aliases
    avancando.
11. Coletar diagnostico e registrar README sanitizado da rodada.

