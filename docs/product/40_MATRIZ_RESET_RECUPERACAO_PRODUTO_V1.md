# Matriz de reset e recuperacao - Produto V1

Status: matriz de produto. Nao implementa reset real.

Data: 2026-05-03

## 1. Objetivo

Definir uma matriz unica para tipos de reset, recuperacao, acionamento,
confirmacao, dados apagados/preservados, impacto e fase de implementacao.

Esta matriz evita que "reset" vire uma acao ambigua. Nenhuma acao aqui esta
implementada por este documento.

## 2. Regras de seguranca

- Reset nao expoe shell.
- Reset nao imprime token/API, URL privada, payload, IDs reais, SSID, senha,
  IP, hostname, MAC, DNS, gateway, paths privados, config ou backup.
- Toda acao destrutiva mostra dados apagados e preservados.
- Confirmacao forte e obrigatoria para reset que apaga config, rede, cache ou
  estado.
- Diagnostico seguro deve ser preservado ou oferecido antes de apagamento,
  quando a politica permitir.
- Player nao deve iniciar com config parcial apos reset.

## 3. Camadas de recuperacao

| Nivel | Nome | Acao tipica | Dono |
| --- | --- | --- | --- |
| 1 | Automatica | Retry, restart controlado, cache offline, HDMI reconectado. | Sistema |
| 2 | Operador | Tentar novamente, reiniciar exibicao, trocar rede/ambiente, diagnostico, reset leve. | Operador autorizado |
| 3 | Local fisico | Botao, teclado USB, pendrive, arquivo de reset ou combinacao local. | Suporte presencial/operador treinado |
| 4 | Sistema/app | Rollback de app, factory reset, recovery image, regravacao de cartao. | Suporte avancado |

## 4. Matriz

| Tipo | Gatilho | Metodo de acionamento | Usuario autorizado | Confirmacao | Dados apagados | Dados preservados | Impacto no player | Impacto na rede | Rollback | Riscos | Status publico esperado | Fase |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Retry automatico de API | Falha temporaria de backend ou internet. | Sistema, timeout/backoff. | Sistema. | Nenhuma. | Nada. | Config, rede, cache, diagnostico. | Player continua se cache permitir; senao mostra erro recuperavel. | Nenhum, apenas nova tentativa. | Nao necessario. | Loop infinito ou bloquear UX. | `network_limited`, `backend_unavailable` ou `offline_cache`. | V1 final |
| Restart MPV automatico | MPV travou ou ficou irresponsivo. | Watchdog/controle local. | Sistema. | Nenhuma. | Processo MPV em memoria. | Config, rede, cache, app. | Pausa breve e retoma exibicao. | Nenhum. | Sistema tenta recriar processo. | Reinicio repetido mascarar erro. | `player_error` temporario ou `player_running`. | Parcial ja existe no player; V1 endurece UX |
| Reiniciar player | Erro recuperavel, tela travada ou pedido de suporte. | Botao "Reiniciar exibicao" em manutencao. | Operador local, suporte remoto autorizado. | Simples. | Processos de exibicao em memoria. | Config, rede, cache, sistema, diagnostico. | Player para e inicia novamente. | Nenhum. | Se falhar, voltar a `player_error`/manutencao. | Interromper conteudo em horario critico. | `restarting_player` -> `starting_player` -> `player_running` ou `player_error`. | MVP/V1 |
| Reset de configuracao operacional | Ambiente errado, config invalida, troca de titularidade ou reativacao. | Manutencao: "Limpar configuracao". | Operador de instalacao, suporte. | Forte. | Config operacional ativa, ativacao local e credencial de runtime conforme politica. | Sistema/app, rede se politica preservar, cache se politica preservar, diagnostico permitido. | Player para e fica bloqueado ate novo setup. | Nenhum se rede for preservada. | Restaurar ultima config valida se backup aprovado e autorizado. | Apagar config correta; vazar backup; ficar sem exibicao. | `config_missing` e tela de configuracao pendente. | MVP documentado; V1 funcional |
| Reset de rede | Senha/rede errada, conexao limitada, mudanca de local. | Manutencao: "Limpar rede" ou "Trocar rede". | Operador autorizado, suporte presencial. | Forte. | Perfil Wi-Fi dedicado/credencial de rede do produto. | Config operacional, cache, app, Ethernet e conexoes antigas nao pertencentes ao produto. | Player pode continuar com cache ou mostrar rede limitada. | Wi-Fi cai ate nova configuracao; Ethernet preservada. | Preservar rede anterior ate nova passar, quando possivel. | Apagar perfil errado, perder conectividade, vazar SSID/senha. | `wifi_select`, `network_limited` ou `setup_pending`. | V1 final |
| Reset de conteudo/cache | Cache corrompido, midia antiga, falta de espaco ou suporte. | Manutencao: "Limpar cache". | Suporte, operador autorizado. | Forte. | Midia/cache local e temporarios de conteudo. | Config, rede, app, diagnostico essencial. | Player pode parar ou exibir erro ate baixar conteudo; se houver rede, rebaixa. | Nenhum direto. | Nao ha rollback simples; conteudo deve ser baixado novamente. | Campo sem internet ficar sem conteudo; apagar evidencia util. | `cache_clearing`, `starting_player`, `offline_cache_empty`. | V1 final |
| Reset leve combinado | Recuperacao simples quando setup/config ficaram inconsistentes. | Manutencao protegida: "Voltar para configuracao". | Operador treinado, suporte. | Forte. | Config operacional e/ou estado de setup conforme escopo escolhido. | Sistema/app; rede/cache conforme opcao escolhida. | Player fica parado ate config valida. | Depende da opcao de preservar rede. | Restaurar backup de config se politica permitir. | Escopo confuso apagar dado errado. | `config_missing` ou `setup_start`. | MVP documentado; V1 funcional |
| Factory reset | Reinstalacao de campo, troca de cliente/local, estado desconhecido. | Manutencao protegida ou hard reset local aprovado. | Suporte autorizado, operador treinado. | Muito forte. | Config operacional, rede do produto, cache, estado local, ativacao local. | Imagem/app base; diagnostico previo se preservacao/exportacao for escolhida. | Player para e so volta apos setup completo. | Wi-Fi removido; setup de conexao necessario. | Limitado; pode exigir novo setup/provisionamento. | Apagar dados errados, perder evidencia, reset acidental. | `factory_resetting` -> `config_missing`. | V1 final |
| Hard reset local | UI inacessivel, sem rede, operador sem portal, aparelho preso em erro. | Botao, teclado USB, pendrive, arquivo de reset ou combinacao local; metodo em aberto. | Suporte presencial, operador treinado. | Fisica/local e possivelmente dupla confirmacao. | Depende do modo escolhido: entrar em recovery, limpar config ou factory reset. | Deve preservar sistema/app salvo escolha de Nivel 4. | Player para ou fica bloqueado. | Pode preservar ou limpar rede conforme acao selecionada. | Se for apenas entrada em recovery, cancelar deve voltar ao estado anterior. | Acionamento acidental, metodo virar shell, falta de acesso fisico. | `recovery`, `config_missing` ou `maintenance`. | V1 final, decisao aberta |
| Rollback de app/release | Update ruim, app nao sobe, regressao visual ou player_error persistente. | Recovery/manutencao avancada. | Suporte presencial/avancado. | Muito forte. | Release/app atual ou symlink ativo ruim. | Config, rede e cache se compativeis; diagnostico. | Player reinicia com release anterior. | Nenhum direto. | Voltar para release anterior validada. | Incompatibilidade de config, rollback parcial. | `app_rollback` -> `starting_player` ou `maintenance`. | C10/fase update |
| Restauracao de sistema/recovery image | Sistema corrompido, root quebrado, rollback insuficiente. | Recovery image ou regravacao de cartao. | Suporte avancado. | Muito forte e procedimento externo. | Pode apagar sistema/app e, dependendo do metodo, config/cache/rede. | O que estiver em backup aprovado e compativel. | Player indisponivel ate restaurar. | Pode exigir nova rede. | Regravar imagem anterior ou restaurar backup externo. | Perda ampla de dados, tempo de campo, erro humano. | `recovery` ou setup inicial. | C10/suporte avancado |

## 5. Fases de implementacao sugeridas

| Fase | Entrega |
| --- | --- |
| C8.1 | Setup minimo funcional sem Wi-Fi real, com reset leve documentado. |
| C8.4 | Reiniciar exibicao e reset leve como comandos limitados. |
| C8.5 | Integracao com writer/config, preservando rollback e status publico. |
| C9 | Reset/troca de rede com Wi-Fi/portal/hotspot e adapter seguro. |
| C10 | Factory reset, hard reset local, rollback de app e recuperacao avancada. |

## 6. Decisoes abertas

- Se reset de configuracao preserva rede.
- Se reset de configuracao preserva cache.
- Se factory reset preserva diagnostico sanitizado por padrao.
- Como impedir acionamento acidental de hard reset local.
- Qual metodo fisico sera escolhido.
- Como rollback de app valida compatibilidade de config.
- Como operador cancela recovery sem deixar estado parcial.
