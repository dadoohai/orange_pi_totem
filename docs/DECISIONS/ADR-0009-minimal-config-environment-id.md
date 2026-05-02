# ADR-0009 - Configuracao minima por environment_id

## Status

Proposta.

## Contexto

O totem ja tem base tecnica validada em desenvolvimento para launcher,
`systemd`, HDMI ausente/reconexao, `config_missing`, status agregado e renderer
Dadooh. Quando a config esta ausente ou incompleta, o sistema nao inicia
`kiosk.py` nem MPV principal, e mostra uma tela publica de configuracao
pendente.

C0 e ADR-0008 propuseram uma visao ampla de onboarding com hotspot, portal
local por celular e ativacao por codigo curto. Essa visao continua util, mas a
proxima etapa de UX precisa de um recorte menor para nao misturar Wi-Fi,
ativacao backend, secrets, troca de ambiente, manutencao e producao.

Nesta fase, o problema imediato e: um operador nao tecnico encontrou um totem
com servico e HDMI funcionando, mas sem config essencial para iniciar o player.
Ele deve conseguir completar o minimo necessario sem terminal, SSH ou editor de
JSON.

## Relacao com C0 e ADR-0008

ADR-0008 permanece como proposta de visao futura para onboarding por celular,
hotspot e ativacao por codigo.

ADR-0009 nao substitui ADR-0008. Ela refina o escopo corrente para C1:

- Wi-Fi;
- sinal claro de conexao funcionando;
- `environment_id` manual;
- `api_key` fora da UI;
- sem ativacao por codigo nesta fase.

## Decisao proposta

- Nesta fase, o operador informa `environment_id` manualmente.
- O operador nao informa `api_key`.
- O operador nao ve `api_key`.
- `api_key` vem de variavel de ambiente, mock ou provisionamento externo.
- Ativacao por codigo fica para fase futura.
- Login e lista de ambientes ficam para fase futura.
- Config writer real deve validar a config minima antes de substituir config
  ativa.
- Renderer/setup visual deve parar antes de iniciar o player.

## Alternativas consideradas

### Operador digitar api_key

Rejeitada para esta fase. `api_key` e secret, e digitar esse valor aumenta o
risco de vazamento, erro humano, suporte dificil e captura em tela, logs ou
diagnostico.

### Codigo curto de ativacao

Continua sendo alternativa futura e esta documentada em C0/ADR-0008. Nao entra
em C1 porque exige backend, expiracao, troca segura por config, tratamento de
erro remoto e writer real.

### Login e lista de ambientes

Fica para fase futura. Exige conta, sessao, autorizacao, backend, tratamento de
conectividade e UX mais ampla do que o minimo necessario agora.

### JSON manual

Rejeitada para operador. Funciona em bancada, mas exige conhecimento tecnico e
pode expor secrets, paths, URLs e IDs privados.

## Consequencias

- O fluxo C1 fica menor e mais testavel.
- O operador manipula apenas um identificador operacional permitido para esta
  fase.
- Secrets continuam fora da UI.
- A implementacao futura precisara resolver como `api_key` chega ao player sem
  ser digitada pelo operador.
- O config writer futuro nao pode salvar config parcial nem iniciar player se
  `api_key` externa estiver ausente.
- Ativacao por codigo, login e lista de ambientes continuam possiveis, mas nao
  bloqueiam o primeiro mock do onboarding minimo.

## Riscos

- `environment_id` digitado errado pode apontar o totem para ambiente indevido.
- `api_key` externa pode estar ausente, errada ou expirada.
- Uma config parcial pode parecer salva, mas falhar no player.
- C1 pode ser confundida com producao ou com ativacao definitiva.
- Validacao apenas de formato nao garante que o ambiente existe no backend.

## Proximos passos

1. Documentar fluxo minimo C1 e estados publicos.
2. Fazer mock visual/formulario sem alterar rede.
3. Fazer diagnostico Wi-Fi read-only.
4. Definir decisao tecnica para fornecimento de `api_key` fora da UI.
5. Implementar config writer minimo/mock antes de escrita real.
6. So depois salvar config minima real com validacao, escrita atomica e
   rollback.
7. Reavaliar ativacao por codigo, login e lista de ambientes em fase futura.
