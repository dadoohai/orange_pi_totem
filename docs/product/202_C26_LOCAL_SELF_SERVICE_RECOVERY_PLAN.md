# 202 - C26 - Recuperacao local pelo usuario

Status: decisao de produto aprovada para execucao. Nao declara implementacao.

Data: 2026-07-17

## Missao

Reduzir visitas tecnicas permitindo que uma pessoa nao tecnica identifique e
resolva localmente as falhas comuns do totem, sem internet e sem colocar em
risco a baseline `prod15`.

A solucao deve continuar simples: mostrar o estado, indicar uma unica proxima
acao e preservar dados. Nao sera um painel tecnico nem um reset geral.

## Base existente

- `prod15 + C25B + C21.24` continua sendo a referencia aceita.
- Retry, cache offline, watchdog e restart do servico ja tratam automaticamente
  varias falhas. A protecao de rollback OTA continua interna ao sistema e nao
  vira acao do usuario.
- Wi-Fi ja usa troca transacional com retorno ao perfil anterior.
- Config ja usa candidata, validacao, backup e escrita atomica.
- `F10` abre o configurador local sem depender da rede.
- A matriz historica `40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md` definiu os
  tipos de recuperacao, mas nao implementou os resets ali descritos.

## Decisao de produto

### Entrada unica

- Sem configuracao: `F10` abre diretamente o setup atual.
- Ja configurado: `F10` abre uma home curta com `Ajustes`,
  `Ajuda e recuperacao` e `Voltar a exibicao`.
- A ajuda nao vira um sexto passo do onboarding.
- Toda tela de ajuda oferece saida clara para a exibicao sem salvar mudancas.

Antes de o fluxo `F10` pausar o player, ele deve capturar um retrato rapido,
sanitizado e best-effort. Falha nessa captura nunca pode impedir a abertura nem
o retorno ao player. A classificacao distingue o estado anterior do estado da
sessao de ajuda.

### Experiencia

A tela mostra somente:

1. o que foi confirmado em linguagem comum;
2. uma acao recomendada para aquele estado;
3. uma categoria de suporte curta, como `PLY-02` ou `NET-01`.

Quando os sinais forem antigos, conflitantes ou insuficientes, o resultado e
`Nao foi possivel confirmar`, seguido de uma acao que nao apaga dados. A
categoria nao e protocolo nem identificador unico de incidente.

### Escada de recuperacao

| Nivel | Responsavel | Acao |
| --- | --- | --- |
| 0 | Sistema | Retry, cache offline, watchdog, restart e rollback ja existentes. |
| 1 | Usuario | Ver estado, seguir uma orientacao e voltar para a exibicao. |
| 2 | Usuario | Reiniciar exibicao, trocar Wi-Fi, abrir ajustes ou reiniciar o aparelho sob protecao. |
| 3 | Suporte | Cache, rollback/update manual, troca de cliente e diagnostico aprofundado. |
| 4 | Suporte avancado | Recovery de sistema, regravacao ou troca fisica. |

## Escopo funcional V1

Categorias fechadas:

- tela/display;
- exibicao/player;
- rede/backend;
- configuracao/ativacao;
- update/sistema;
- indeterminado.

| Categoria | Sinal publico confirmado | Acao unica | Codigo |
| --- | --- | --- | --- |
| Tela | Tela local ausente ou sink suspeito | Verificar tela, entrada, energia e cabo; ciclar somente a tela | `DSP-01` |
| Player | Tela local funciona, mas o player anterior estava parado ou stale | Reiniciar exibicao | `PLY-01` |
| Rede | Conexao local nao foi confirmada | Trocar Wi-Fi | `NET-01` |
| Backend | Rede local existe, mas o servico Dadooh esta indisponivel | Aguardar e tentar novamente | `NET-02` |
| Config | Configuracao esta ausente ou invalida | Abrir ajustes | `CFG-01` |
| Sistema | Update ou gravacao esta em andamento | Aguardar | `SYS-01` |
| Indeterminado | Sinais antigos, conflitantes ou insuficientes | Voltar a exibicao e informar o codigo ao suporte | `UNK-01` |

Acoes permitidas:

- aguardar ou tentar novamente somente quando isso tiver efeito real;
- voltar para a exibicao;
- reiniciar a exibicao uma vez, com intervalo entre tentativas;
- trocar Wi-Fi pelo fluxo transacional existente;
- abrir os ajustes existentes, mantendo a configuracao atual ate uma nova
  candidata ser validada e gravada;
- reiniciar o aparelho como ultimo recurso local, com confirmacao.

`Reiniciar exibicao` restaura somente o player ao sair da sessao local. Nao
limpa cache, rede, config ou OTA e nao executa um segundo restart desnecessario.

Para suspeita de tela/TV travada com a placa saudavel, a ordem e: verificar
energia, entrada e cabo da tela; desligar e ligar somente a tela; depois voltar
a exibicao. Reiniciar a placa nao e a primeira recomendacao desse caso.

Todas as acoes mutantes compartilham um unico guard: uma acao por vez,
bloqueio diante de transacao de update, writer, settings ou rede, intervalo
contra repeticao e falha fechada. A UI nunca chama writer ou comandos livres
diretamente.

## Diagnostico seguro

O resultado usa schema allowlist com enums e textos fixos. Pode registrar apenas
o ultimo resumo em `latest.json`, por substituicao atomica, permissao restrita e
tamanho maximo pequeno. Nao existe historico crescente.

Nunca registrar SSID, senha, IP, MAC, DNS, hostname, URL, token, IDs reais,
config, backup, nome/path de midia, journal ou saida bruta de comando.

## Fora da V1

- limpar cache;
- botoes de update ou rollback;
- shell, logs brutos ou dashboard;
- reset amplo de NetworkManager;
- desligar o aparelho pela UI;
- hard reset, reflash ou factory reset;
- identificador remoto, upload ou telemetria;
- navegador para portal cativo.

`Preparar para novo cliente` fica em roadmap separado e nao aparece na UI V1.
Antes de existir, precisa revogar a credencial no backend, declarar exatamente
o que apaga, preservar identidade/imagem/OTA, usar locks e ser transacional sob
queda de energia. Restaurar o sistema operacional e outro fluxo.

## Verticais de entrega

1. **Entender e retornar:** home `F10`, captura antes da pausa, classificacao,
   categoria de suporte e retorno seguro, ainda sem nova acao destrutiva.
2. **Resolver falhas comuns:** integrar restart contextual, Wi-Fi e ajustes
   existentes sob o guard unico.
3. **Ultimo recurso local:** reboot confirmado e guia curto para tela, energia,
   cabo, Ethernet e `F10`.
4. **Fechar em produto:** fault injection, QA visual na placa, pacote
   `totem-core`, rollback e acumulacao na proxima imagem.

As verticais devem usar primeiro as superficies ja permitidas de `totem-core`.
Se uma mudanca exigir novo binario privilegiado, unit systemd, updater ou
allowlist de imagem, ela entra explicitamente na proxima imagem; nao sera
disfarcada em OTA comum.

## Validacao curta

Testar sem campanhas de horas:

- sem internet, backend indisponivel e senha Wi-Fi errada;
- MPV/status preso e `player_error` persistente;
- display ausente e suspeita de sink travado;
- config ausente/invalida e sessao de settings antiga;
- update, writer e rede com lock ativo;
- F10 repetido, acao repetida e crash da UI;
- interrupcao durante escrita do resumo;
- retorno a midia e preservacao de config, rede, cache, identidade e OTA;
- regressao de primeiro setup, timers, rollback e quarentena da `prod15`;
- varredura de segredo, limite de tamanho e ausencia de crescimento continuo,
  inclusive em backups criados por ajustes repetidos.

## Definicao de pronto

A V1 fecha quando um usuario consegue abrir `F10`, entender o estado, executar
a acao segura indicada e voltar para a midia; quando nao consegue resolver,
informa uma categoria publica ao suporte. Nenhuma acao pode apagar dados por
ambiguidade, concorrer com uma transacao, alterar a identidade da placa ou
regredir playback, boot, wizard ou OTA.
