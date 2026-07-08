# C20.1 Environment Copy And Stepper Review

Objetivo: validar ajuste pequeno do wizard visual sem mudar o fluxo de gravacao.

Resultado:

- tela Ambiente usa copy mais simples;
- footer remove a instrucao visivel confusa de Ctrl+U/setas;
- atalhos existentes continuam cobertos por self-test;
- labels do stepper em retrato usam nomes curtos (`Amb.`, `Fim`);
- a galeria QA foi alinhada ao wizard real;
- navegacao livre por etapas fica como vertical posterior com estado explicito de pendencia/default.

Artefatos:

- `visible/`: 53 JPGs abríveis no Windows;
- `svg/`: SVGs fonte;
- `contact-sheet-all.jpg`: folha geral;
- `index.html`: lista navegavel local;
- `run-summary.json`, `ux-review-summary.md`, `visual-metrics-summary.md`: resumo automatico.

Non-claims:

- nao tocou Wi-Fi real;
- nao escreveu configuracao real;
- nao alterou player-runtime, media-system, kernel ou imagem;
- a captura decisiva de percepcao final ainda deve ser feita no framebuffer/HDMI da placa apos OTA.
