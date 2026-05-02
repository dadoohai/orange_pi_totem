# C1 - fluxo de usuario minimo

Status: fluxo documental planejado. Nao implementa mudancas operacionais.

Data: 2026-05-02

## Objetivo

Este documento descreve o fluxo minimo desejado para um operador nao tecnico
sair de `config_missing` em fase futura. O recorte C1 e Wi-Fi mais
`environment_id` manual, com `api_key` fora da UI.

O documento nao implementa varredura de redes, conexao Wi-Fi, portal, hotspot,
QR funcional, validacao backend ou escrita real de config.

## 1. Boot normal com config valida

1. Totem liga.
2. Tela Dadooh aparece como sinal publico de inicializacao.
3. Launcher verifica HDMI.
4. Launcher verifica config.
5. Config valida e encontrada.
6. Renderer/setup nao permanece ativo.
7. Player inicia.
8. Estado publico converge para `player_running`.

Resultado esperado: o operador nao precisa fazer nada.

## 2. Boot com config ausente ou incompleta

1. Totem liga.
2. Tela Dadooh aparece.
3. Launcher verifica HDMI.
4. Launcher verifica config.
5. Config ausente, invalida ou incompleta.
6. Launcher publica `config_missing`.
7. `kiosk.py` e MPV principal nao iniciam.
8. Renderer mostra "Configuracao pendente".
9. Em fase futura, tela oferece acao clara para iniciar configuracao.

Resultado esperado: o operador entende que a configuracao esta pendente e que o
player esta parado por seguranca.

## 3. Fluxo futuro de configuracao Wi-Fi

Fluxo planejado:

1. Iniciar configuracao a partir da tela pendente.
2. Listar redes disponiveis.
3. Operador escolhe a rede.
4. Operador insere senha.
5. Sistema testa conexao.
6. Tela mostra sucesso ou erro recuperavel.
7. Em caso de erro, operador pode voltar, corrigir senha ou escolher outra
   rede.

Limite de C1: esta fase documental nao implementa varredura, senha, conexao,
alteracao de rede, NetworkManager, hotspot ou portal.

## 4. Niveis de "conexao funcionando"

O produto deve separar niveis de conectividade, porque "Wi-Fi conectado" nao
garante que o player conseguira operar.

Niveis propostos:

| Nivel | Significado | Uso em C1 |
| --- | --- | --- |
| Wi-Fi associado | O dispositivo associou a uma rede sem fio. | Planejado, nao implementado. |
| IP obtido | O dispositivo recebeu endereco local valido. | Planejado, nao implementado. |
| Internet basica | Ha conectividade minima para fora da rede local. | Planejado, nao implementado. |
| Backend acessivel | Servico necessario do produto responde, se aplicavel. | Fase futura, nao obrigatorio em C1. |

Mensagens publicas devem ser simples, por exemplo: conectado, conectado sem
internet, servico indisponivel ou tente novamente. Detalhes internos de DNS,
URL, payload ou endpoint nao devem aparecer.

## 5. Configuracao de ambiente

Fluxo planejado:

1. Operador informa `environment_id`.
2. Sistema valida formato minimo.
3. Campo vazio gera erro publico e nao avanca.
4. Campo com formato invalido gera erro publico e nao avanca.
5. Campo com formato aceitavel permite prosseguir.

C1 nao valida `environment_id` contra backend. Validacao remota, lista de
ambientes, login, ativacao por codigo e troca de ambiente ficam para fases
futuras.

O valor real informado pelo operador nao deve ser publicado em docs, status
publico, diagnostico ou logs compartilhaveis.

## 6. Salvar config e iniciar player

Fluxo futuro:

1. Sistema monta uma config minima usando os dados permitidos.
2. `api_key` e obtida fora da UI por env, mock ou provisionamento separado.
3. Sistema valida a config antes de substituir qualquer config ativa.
4. Escrita real, quando existir, deve ser atomica e com rollback.
5. Se a validacao falhar, config ativa anterior deve ser preservada quando
   existir.
6. Se a config for salva com sucesso, o estado passa para `config_saved`.
7. Renderer/setup para.
8. Launcher inicia o player.
9. Estado publico passa para `starting_player` e depois `player_running`.

C1 nao escreve `/data/config/config.json`. O writer real fica para fase
posterior.

## 7. Erros esperados

| Erro | Comportamento esperado |
| --- | --- |
| Senha Wi-Fi errada | Mostrar erro recuperavel, nao registrar senha e permitir nova tentativa. |
| Wi-Fi conectado sem internet | Mostrar conexao limitada e permitir testar novamente ou trocar rede. |
| Backend inacessivel, se aplicavel futuramente | Manter erro publico sem URL, payload ou detalhe interno. |
| `environment_id` vazio | Bloquear avanco e pedir preenchimento. |
| `environment_id` invalido | Bloquear avanco e explicar formato minimo esperado sem expor IDs reais. |
| `api_key` ausente em env/mock/provisionamento | Bloquear salvamento ou inicio do player e publicar erro seguro de provisionamento. |
| Falha ao salvar config | Preservar config anterior, mostrar erro recuperavel e nao iniciar player com config parcial. |
| Queda de energia no meio | No boot seguinte, detectar estado incompleto e voltar para `config_missing` ou `setup_error` sem config parcial ativa. |

## Linha de seguranca

- Operador nao digita `api_key`.
- Operador nao ve `api_key`.
- Operador nao usa terminal, SSH ou editor de JSON.
- Renderer/setup e player principal nao rodam juntos.
- Alteracoes reais de rede e config so entram em fases futuras com rollback e
  validacao propria.
