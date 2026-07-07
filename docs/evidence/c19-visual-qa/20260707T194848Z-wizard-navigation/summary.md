# C19.1 Wizard Navigation Investigation

Run: `20260707T194848Z-wizard-navigation`

Placa: lab via SSH `192.168.18.154`.

Escopo: navegar no wizard real, capturar telas, retornar para midia e registrar
problemas de UX/operacao. O F10 ja havia sido provado antes; esta rodada abriu
a sessao via `totem-open-settings.service` para investigar o wizard.

## Passos

1. Estado inicial: player ativo, MPV vivo, lock ausente.
2. Abertura do wizard: `totem-open-settings.service`.
3. Capturas: orientacao, confirmacao, conexao, selecao de Wi-Fi, paginacao e
   retorno para conexao.
4. Saida por `Esc`.
5. Validacao final: player ativo, MPV vivo, `PLAYER_STATUS=playing`, lock e
   request ausentes, sem escrita real e sem mudanca de Wi-Fi.

## Evidencias

Capturas brutas: `*.png`.

Capturas para revisao humana no Windows: `*-visible.jpg`.

Principais:

- `01-orientation-visible.jpg`
- `05-connection-default-visible.jpg`
- `07-wifi-list-page1-visible.jpg`
- `08-wifi-list-pagedown-visible.jpg`
- `10-back-to-connection-visible.jpg`

## Achados

P1 - Lista de Wi-Fi invade rodape em `1024x768`.

Na lista real, a quinta rede fica parcialmente encoberta pelo rodape. Isso
acontece na pagina 1 e pagina 2. Impacta diretamente configuracao por usuario.

Causa localizada: em landscape, `WIFI_LIST_PAGE_SIZE=5`, os cards comecam em
`y=262`, tem `82px` de altura e `14px` de intervalo. O quinto card ocupa
aproximadamente `y=646..728`, mas o rodape comeca em `y=638`.

P1 - Cancelamento por `Esc` volta a midia, mas deixa systemd `failed`.

Comportamento funcional final esta correto: player volta, lock/request somem,
MPV fica vivo e status volta para `playing`. Porem `totem-open-settings.service`
fica com `Result=signal` e `ExecMainStatus=15` ate `systemctl reset-failed`.

P2 - Caracteres de sinal aparecem como `????`.

A UI mostra `????` no lugar do indicador visual de sinal. Provavel limite de
fonte/renderizador no framebuffer. Causa localizada: o wizard usa blocos
Unicode (`████`) em `signal_bars()`, e a fonte/renderizacao atual nao suporta
esses glifos. Melhor usar texto ASCII ou desenhar barras como retangulos SVG.

P2 - Display atual opera em `1024x768`.

O modo baixo e 4:3 reduz espaco util e pode ser esticado pela TV. Este item
pertence a frente de display/perfil HDMI.

## Ordem Recomendada

1. Corrigir layout/paginacao da lista de Wi-Fi para caber em `1024x768`.
2. Corrigir encerramento limpo por `Esc` para nao deixar unidade `failed`.
3. Trocar indicador de sinal para texto/simbolo compativel.
4. Tratar `1024x768` na frente de display, sem misturar com a correcao do
   wizard.
