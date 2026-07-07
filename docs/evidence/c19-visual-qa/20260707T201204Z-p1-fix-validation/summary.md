# C19.2 P1 Fix Validation

Data: 2026-07-07.

Objetivo: validar na placa real que a lista de Wi-Fi em paisagem cabe sem
invadir o rodape e que PageDown/PageUp seguem o novo tamanho de pagina.

Resultado:

- lista de Wi-Fi em paisagem renderizou 4 redes por pagina;
- `PageDown` foi para `Mostrando 5-8 de 25`;
- `PageUp` voltou para `Mostrando 1-4 de 25`;
- nenhum card invadiu o rodape nas capturas visiveis;
- `????` do sinal permanece como P2 fora de escopo.

Artefatos principais:

- `03-wifi-page1-visible.jpg`;
- `04-wifi-pagedown-visible.jpg`;
- `05-wifi-pageup-visible.jpg`;
- `operation.log`;
- `captures.tgz`.

Nota: o `Esc` enviado a partir da lista de Wi-Fi voltou para navegacao local,
como esperado; o cancelamento global foi validado separadamente em
`20260707T201447Z-esc-clean-cycles`.
