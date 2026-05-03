# Produto V1 - operacao, onboarding e recuperacao

Status: visao de produto. Nao implementa operacao real.

Data: 2026-05-03

## 1. Objetivo

Este documento define a visao Produto V1 para o appliance Dadooh baseado em
Orange Pi Zero 3. O foco deixa de ser apenas guardrail tecnico e passa a cobrir
a operacao completa por pessoa nao tecnica:

- onboarding;
- operacao diaria;
- troca de ambiente;
- rotacao de tela;
- manutencao;
- diagnostico;
- reset;
- hard reset local;
- recuperacao quando algo falha;
- restauracao de sistema/app.

O documento orienta desenvolvimento funcional futuro. Ele nao substitui
homologacao, nao executa testes, nao toca placa, nao altera launcher,
renderer, player, NetworkManager, `systemd` ou config real.

## 2. Principios de produto

- O operador principal nao e tecnico.
- A operacao normal nao deve exigir terminal, SSH, shell, editor ou JSON.
- A UI nao deve mostrar token/API, segredo, URL privada, payload, IDs reais,
  SSID, senha, IP, hostname, MAC, gateway, DNS ou paths privados.
- O aparelho deve parecer produto, nao computador em manutencao.
- Robustez nao pode bloquear a UX indefinidamente: quando o sistema nao
  consegue seguir, deve explicar o estado e oferecer proxima acao segura.
- Estados devem ser claros, curtos e acionaveis.
- Recuperacao deve ser simples antes de ser completa.
- Suporte precisa de diagnostico seguro, agregando estado sem copiar dados
  brutos.
- Player e setup/manutencao nao devem disputar tela. Quando setup ou status
  aparecem, o player principal deve estar parado ou fora da tela.
- Evidencia, screenshot, README, diagnostico e prototipo nao podem vazar
  segredo ou identificador real.
- Toda acao destrutiva precisa dizer o que apaga, o que preserva e como voltar.
- Reset nao deve virar shell perigoso.
- O fluxo deve preservar uma ultima configuracao valida quando isso for
  possivel e seguro.

## 3. Papeis

| Papel | Pode fazer | Nao pode fazer | Confirmacao forte |
| --- | --- | --- | --- |
| Operador de instalacao | Ligar o totem, seguir setup guiado, escolher rede, ativar/provisionar, selecionar ambiente, escolher orientacao, revisar e iniciar exibicao. | Usar terminal, editar JSON, ver token/API, alterar arquivos internos, executar shell ou publicar diagnostico bruto. | Salvar config, trocar ambiente, limpar configuracao, reset de rede, factory reset. |
| Operador de loja/local | Ver estado publico, tentar novamente, reiniciar exibicao, trocar rede quando autorizado, abrir manutencao limitada e coletar diagnostico seguro. | Mudar segredo, ver config privada, apagar sistema, acessar shell, mexer em perfis internos ou usar credenciais fora da UI aprovada. | Reiniciar exibicao, trocar rede, limpar config, limpar cache, factory reset. |
| Suporte remoto | Orientar operador por codigos publicos, solicitar diagnostico sanitizado, autorizar retry/reset leve, decidir se suporte presencial e necessario. | Pedir senha, token, SSID real, IP, MAC, payload, foto com segredo ou output bruto; executar comando local sem canal aprovado. | Factory reset, restauracao de release anterior, emissao/revogacao futura de token. |
| Suporte presencial | Executar manutencao autorizada, usar teclado USB/pendrive/botao local se o metodo for aprovado, regravar cartao ou restaurar release. | Bypassar confirmacoes, publicar artefatos brutos, deixar modo de manutencao aberto ou transformar reset em shell. | Hard reset local, factory reset, restauracao de sistema/app, regravacao de cartao. |
| Admin/backend | Criar ambientes, autorizar ativacao, emitir/revogar token de dispositivo no futuro, definir lista de ambientes e politicas de permissao. | Usar token humano como runtime permanente, expor token na UI, depender de segredo digitado por operador. | Emissao/revogacao de credencial de dispositivo, troca de ambiente entre contas/unidades, desativacao remota. |
| Codex/agente de desenvolvimento | Criar docs, prototipos estaticos, contratos, scripts mock/local e alteracoes versionadas revisaveis. | Receber senha/token real, tocar placa sem autorizacao, ler config real, executar comandos remotos, publicar secrets, fazer commit sem revisao humana. | Qualquer escrita real, operacao em placa, alteracao de rede, service control, uso de dados reais. |

Confirmacao forte significa uma tela ou procedimento que:

- nomeia a acao;
- mostra impacto;
- mostra dados apagados/preservados;
- exige escolha explicita;
- registra evidencia sanitizada;
- permite cancelar sem mudar estado.

## 4. Jornada principal V1

Fluxo desejado para primeira operacao:

```text
Liga o totem
-> Dadooh / inicializando
-> verifica HDMI
-> verifica config
-> se config valida: inicia player
-> se config ausente/incompleta: setup guiado
-> conexao
-> ativacao/provisionamento
-> selecao de ambiente
-> orientacao/rotacao de tela
-> revisao
-> salvar config
-> iniciar exibicao
```

Comportamento esperado por etapa:

| Etapa | Experiencia publica | Regra tecnica futura |
| --- | --- | --- |
| Inicializando | Marca Dadooh e mensagem curta. | Sem terminal visivel; estado publico `booting`. |
| Verifica HDMI | Se sem tela, estado local `display_missing`. | Nao renderizar sem display; nao iniciar player. |
| Verifica config | Se valida, seguir para exibicao; se ausente/incompleta, setup. | Nao iniciar player com config invalida ou parcial. |
| Setup guiado | Operador ve etapas simples. | Setup separado do player e sem shell. |
| Conexao | Escolha/teste de rede ou modo conectado ja existente. | NetworkManager adapter futuro, rollback e evidencia sanitizada. |
| Ativacao/provisionamento | Login, codigo ou lista futura. | Token/API nunca visivel; backend emite credencial de runtime. |
| Selecao de ambiente | Lista segura ou entrada manual temporaria. | Valor real nao entra em diagnostico/status/evidencia. |
| Rotacao | Escolha visual 0/90/180/270 ou retrato/paisagem. | Aplicacao tecnica ainda a decidir. |
| Revisao | Resumo sem segredo. | Mostrar apenas nomes publicos e estados agregados. |
| Salvar config | Progresso e confirmacao. | Writer atomico, validacao, backup e rollback. |
| Iniciar exibicao | Setup sai da tela e player assume. | Renderer/setup parado antes do MPV principal. |

## 5. Jornadas secundarias

| Jornada | Objetivo | Entrada | Saida esperada |
| --- | --- | --- | --- |
| Trocar rede | Corrigir Wi-Fi, senha ou conectividade. | Manutencao ou setup. | Rede nova testada, anterior preservada ate sucesso. |
| Trocar ambiente | Mudar o ambiente operacional do totem. | Manutencao autorizada. | Config candidata validada e player reiniciado com estado claro. |
| Rotacionar tela | Corrigir orientacao de instalacao. | Setup ou manutencao. | Orientacao aplicada ou documentada como pendente no MVP. |
| Ver diagnostico | Dar suporte sem terminal. | Manutencao. | Snapshot sanitizado com codigos publicos. |
| Reiniciar player | Resolver falha comum sem reset amplo. | Manutencao. | Player reinicia, config/rede/cache preservados. |
| Reset leve | Voltar para setup removendo config operacional. | Manutencao com confirmacao. | Config limpa, rede/cache conforme politica, evidencia preservada se definido. |
| Factory reset | Voltar o aparelho ao estado inicial de produto. | Suporte autorizado. | Config/rede/cache limpos conforme matriz, sistema/app preservados. |
| Hard reset local | Recuperar sem portal/rede quando UI normal falha. | Acao fisica/local. | Totem entra em setup ou modo recovery. |
| `player_error` | Recuperar erro de exibicao. | Erro do player. | Retry automatico, opcao de reiniciar exibicao e diagnostico seguro. |
| `display_missing` | HDMI ausente ou instavel. | Boot ou perda de display. | Nao renderizar; retomar fluxo quando HDMI voltar. |
| Backend indisponivel | Operar com erro remoto sem vazar endpoint. | Setup ou runtime. | Retry, erro publico e cache/offline quando disponivel. |
| Sem internet | Rede local sem saida. | Setup ou runtime. | Trocar rede, tentar novamente, operar cache se possivel. |
| Cache/offline | Continuar exibindo conteudo local. | Falha de rede/backend com cache valido. | Player segue, status mostra conectividade limitada. |
| Restaurar release anterior | Recuperar app/sistema apos update ruim. | Recovery/manutencao avancada. | Release anterior ativa e estado publico coerente. |

## 6. Camadas de recuperacao

### Nivel 1 - recuperacao automatica

Recuperacao sem acao humana:

- restart do player quando criterio seguro permitir;
- restart/recriacao de MPV;
- retry de API com timeout e backoff;
- uso de cache offline quando houver conteudo valido;
- retomada quando HDMI e reconectado;
- config invalida ou ausente volta para setup em vez de iniciar player.

O Nivel 1 nunca deve esconder uma falha infinita. Se tentativas excederem o
limite, o estado publico deve mudar para erro recuperavel.

### Nivel 2 - recuperacao pelo operador

Acoes simples na UI de setup/manutencao:

- tentar novamente;
- reiniciar exibicao;
- trocar rede;
- trocar ambiente;
- rotacionar tela;
- ver diagnostico;
- limpar configuracao.

O operador nao ve JSON, token, URL privada, SSID real em evidencia, IP, logs
brutos ou shell.

### Nivel 3 - reset local fisico

Recuperacao quando a UI normal, rede ou backend nao bastam:

- botao no gabinete;
- teclado USB;
- pendrive de manutencao;
- arquivo de reset;
- combinacao local;
- metodo final ainda a decidir.

Esse nivel deve ser simples de explicar para suporte presencial e dificil de
acionar por acidente.

### Nivel 4 - restauracao de sistema

Recuperacao avancada:

- rollback de app;
- factory reset completo;
- recovery image;
- regravacao de cartao;
- suporte avancado.

O Nivel 4 deve ser documentado como suporte, nao operacao diaria.

## 7. Tipos de reset

| Tipo | Quem aciona | Como aciona | Apaga | Preserva | Confirmacao | Risco | Evidencia esperada |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Reiniciar player | Operador local, suporte remoto autorizado | Manutencao: "Reiniciar exibicao" | Processos de exibicao em memoria | Config, rede, cache e sistema | Simples | Perda breve de exibicao | Estado antes/depois, codigo publico e resultado. |
| Reset de configuracao operacional | Operador de instalacao, suporte | Manutencao: "Limpar configuracao" | Config operacional ativa e dados de ativacao local conforme politica | Sistema/app, diagnostico sanitizado, rede se escolhido preservar | Forte | Totem volta para setup e pode ficar sem exibicao | Config limpa: sim/nao, setup exibido, nenhum segredo publicado. |
| Reset de rede | Operador local com autorizacao, suporte presencial | Manutencao: "Trocar/limpar rede" | Perfil Wi-Fi dedicado ou credencial de rede do produto | Config do ambiente, cache, sistema e Ethernet quando houver | Forte | Perder conectividade sem canal local | Estado de rede agregado antes/depois e retorno a setup de conexao. |
| Reset de conteudo/cache | Suporte local/remoto autorizado | Manutencao: "Limpar cache" | Midia/cache local e downloads temporarios | Config, rede, app e diagnostico essencial | Forte | Player pode precisar baixar tudo de novo | Cache limpo, espaco liberado agregado, player revalida conteudo. |
| Factory reset | Suporte autorizado, operador treinado | Manutencao protegida ou hard reset local | Config operacional, rede do produto, cache, estado local e ativacao | Imagem/app base e logs essenciais se politica mandar preservar | Muito forte | Perda de operacao ate novo setup | Estado `config_missing`, setup pronto, resumo do que foi limpo. |
| Restauracao do sistema/app | Suporte presencial/avancado | Recovery, rollback de release ou regravacao | Release/app atual ruim ou sistema corrompido conforme metodo | Config e dados quando compativel; caso contrario factory reset guiado | Muito forte | Incompatibilidade de config, perda de dados ou tempo de campo | Versao anterior/restaurada, healthcheck publico, decisao de rollback. |

## 8. MVP funcional vs V1 final

### MVP funcional

O MVP funcional deve provar a menor jornada operavel sem prometer campo:

- setup minimo sem Wi-Fi real;
- `environment_id` manual ou ambiente mock/lista mock;
- token provisionado localmente fora da UI;
- rotacao mock/documentada;
- config candidate;
- writer controlado;
- start player;
- reset leve documentado.

Limites do MVP:

- sem Wi-Fi real;
- sem portal/hotspot funcional;
- sem backend de ativacao;
- sem credencial visivel;
- sem manutencao avancada;
- sem factory reset real;
- sem hard reset fisico final.

### V1 final

V1 final deve ser operavel em campo por pessoa nao tecnica:

- Wi-Fi setup;
- ambiente por login, codigo ou lista autorizada;
- rotacao funcional;
- modo manutencao;
- diagnostico sanitizado;
- reset leve;
- factory reset;
- hard reset local;
- ativacao/token por backend;
- UX visual refinada.

## 9. Decisoes abertas

- Login vs codigo de ativacao vs lista de ambientes.
- Como o operador entra em manutencao sem terminal.
- Metodo fisico de hard reset: botao, teclado USB, pendrive, arquivo de reset
  ou combinacao local.
- Como rotacao sera aplicada tecnicamente.
- Quando permitir troca de ambiente e se isso exige parar player.
- Se reset apaga midia/cache/config em cada tipo de reset.
- Como token/API sera emitido, escopado, revogado e rotacionado no futuro.
- Qual visual final da marca Dadooh no setup, manutencao e recovery.
- Quanto diagnostico preservar antes de reset destrutivo.
- Como restaurar release anterior sem expor shell ao operador.
