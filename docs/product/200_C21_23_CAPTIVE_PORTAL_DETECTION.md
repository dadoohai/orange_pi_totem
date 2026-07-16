# C21.23 - Deteccao De Portal Cativo

## Objetivo

Separar uma rede que exige acesso web de uma rede apenas sem internet ou com o
servico Dadooh indisponivel, sem abrir navegador nesta rodada.

## Decisao

- `online`, `limited`, `offline` e `unknown` mantem o significado anterior;
- `captive_portal` e um campo adicional: `required`, `not_detected`,
  `not_applicable` ou `unknown`;
- o health HTTPS Dadooh continua sendo a unica prova de `online`;
- se o HTTPS falhar, uma sonda HTTP no mesmo endpoint espera somente o redirect
  exato para HTTPS;
- redirect diferente, HTTP 511 ou HTML interceptado sao evidencia positiva de
  portal;
- timeout, DNS, TLS ou resposta ambigua nunca viram portal por inferencia.

## Experiencia

Quando houver evidencia positiva, o wizard informa que a rede conectou, mas
exige uma etapa de acesso. O usuario pode verificar novamente, escolher outra
rede ou sair e voltar para a exibicao. O fluxo nao avanca para ambiente enquanto
o portal continuar pendente.

## Guardrails

- rota e transporte precisam estar verificados antes das sondas;
- Ethernet nao pode comprovar o Wi-Fi selecionado;
- redirect, URL, HTML, cookie, SSID, credencial, IP, DNS e erro bruto nao sao
  persistidos nem publicados;
- corpo lido e limitado, redirects nao sao seguidos e o tempo total e limitado;
- nenhum navegador, player-runtime, kernel, display ou politica OTA muda.

## Fechamento

O recorte pode ser distribuido por `totem-core`, pois usa apenas Python stdlib,
`nmcli` e `ip`, ja presentes na imagem. A autenticacao no portal permanece no
M9.8 e exigira decisao explicita de runtime de navegador na proxima imagem.

Testes deterministas devem cobrir redirect esperado, redirect interceptado,
HTTP 511, HTML, timeout, rota ausente, conflito Ethernet/Wi-Fi, retry e
privacidade. A prova em portal fisico ou emulado permanece obrigatoria antes de
declarar suporte de campo completo.
