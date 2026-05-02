# C4.2 - roteiro hibrido/local para Wi-Fi controlado

Status: roteiro documental. Nao executa Wi-Fi.

Data: 2026-05-02

## Objetivo

C4.2 prepara uma nova tentativa C4 sem senha pelo Codex. O objetivo e separar
responsabilidades entre Codex e humano para validar Wi-Fi real de teste sem
expor credencial, preservando Ethernet, privacidade e rollback.

Nota posterior: C4.2 foi seguido por C4.5 para registrar a remocao local do
perfil/configuracao de teste que havia sido mantido por decisao humana.

C4.2 define o modelo recomendado apos o postmortem C4.1:

- Codex roda diagnostico C3 antes/depois/final;
- humano executa localmente a etapa sensivel de credencial fora do Codex;
- Codex registra apenas evidencia sanitizada;
- nenhuma senha passa pelo agente;
- nenhum output bruto de rede e versionado.

Este roteiro nao conecta Wi-Fi, nao cria perfil, nao insere senha, nao executa
`nmcli --ask connection up` e nao autoriza comandos mutaveis nesta tarefa.

## Responsabilidades

### Codex pode

- rodar C3 antes;
- gerar comandos com placeholders;
- orientar a sequencia;
- rodar C3 depois;
- rodar C3 final;
- registrar evidencia sanitizada;
- verificar que nada foi escrito em `/data`;
- verificar que `/data/config/config.json` nao foi escrito;
- verificar que Ethernet permanece preservada pelo estado agregado C3.

### Humano deve

- estar fisicamente presente;
- inserir senha fora do Codex;
- executar a etapa sensivel localmente;
- nao enviar senha no chat;
- nao colar output bruto no chat;
- informar ao Codex apenas resultado sanitizado.

Respostas sanitizadas permitidas do humano:

- "conectou";
- "falhou";
- "perfil removido";
- "abortei".

### Codex nao deve

- receber senha;
- pedir senha;
- executar comando que peca senha;
- executar `nmcli --ask connection up`;
- registrar SSID real;
- registrar nome real de conexao;
- registrar saida bruta;
- executar hotspot;
- criar portal;
- tocar em Ethernet;
- modificar conexao antiga;
- apagar conexao antiga;
- escrever em `/data`;
- alterar launcher, renderer, `systemd` ou `kiosky-player`.

## Pre-condicoes para execucao futura

Checklist obrigatorio antes de qualquer nova tentativa real:

- [ ] placa de desenvolvimento confirmada;
- [ ] placa de homologacao fora do escopo;
- [ ] acesso fisico confirmado;
- [ ] Ethernet conectada;
- [ ] C3 antes roda limpo;
- [ ] rede de teste controlada definida;
- [ ] senha nao sera enviada ao Codex;
- [ ] metodo local de insercao de senha definido;
- [ ] perfil de teste sera removido ao final;
- [ ] internet/backend externo fora do escopo;
- [ ] criterio de abortar confirmado.

## Sequencia hibrida proposta

### Fase A - Codex

1. Rodar C3 antes.
2. Confirmar `ethernet_connected=true`.
3. Confirmar `networkmanager_observed=true`.
4. Confirmar que os artefatos C3 estao sanitizados.
5. Preparar placeholders publicos:
   - `WIFI_TEST_SSID`;
   - `WIFI_TEST_CONNECTION_NAME`;
   - senha: inserida localmente pelo humano, nao registrada.

### Fase B - humano fora do Codex

1. Criar ou conectar Wi-Fi de teste localmente.
2. Inserir senha localmente, fora de chat, transcript, SSH gerenciado pelo
   agente, script ou arquivo versionavel.
3. Nao copiar output bruto para o Codex.
4. Informar apenas resultado sanitizado.

### Fase C - Codex

1. Rodar C3 depois.
2. Registrar somente campos agregados.
3. Confirmar Ethernet preservada pelo agregado C3.
4. Nao interpretar sucesso de internet/backend nesta fase.

### Fase D - humano ou Codex sem segredo

1. Remover perfil de teste.
2. Se a remocao envolver apenas nome placeholder autorizado e nenhum segredo,
   Codex pode executar somente apos autorizacao humana explicita.
3. Se a remocao exigir nome real, segredo, output bruto ou risco de afetar
   conexao antiga, humano remove localmente.

### Fase E - Codex

1. Rodar C3 final.
2. Confirmar `ethernet_connected=true`.
3. Confirmar que nada foi escrito em `/data`.
4. Criar README de evidencia sanitizada.
5. Nao versionar outputs brutos.

## Frases permitidas para humano retornar ao Codex

O humano deve retornar somente frases sanitizadas como:

- "Wi-Fi de teste conectado."
- "Wi-Fi de teste falhou."
- "Perfil de teste removido."
- "Abortado antes de conectar."
- "Ethernet preservada visualmente."
- "Preciso abortar."

Fica proibido retornar ao Codex:

- senha;
- SSID real;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome real de conexao;
- output bruto do `nmcli`;
- URL privada;
- secrets;
- payloads;
- paths privados.

## Criterios de abortar

Abortar a tentativa se qualquer item ocorrer:

- C3 antes nao mostrar Ethernet preservada;
- humano nao tiver acesso fisico;
- senha precisar passar pelo Codex;
- output bruto contiver dado sensivel;
- conexao antiga parecer afetada;
- Ethernet cair;
- perfil de teste nao puder ser removido;
- houver duvida sobre placa;
- houver duvida sobre rollback;
- houver pedido para publicar SSID, senha, IP, gateway, hostname, MAC, BSSID,
  DNS real ou nome real de conexao.

Ao abortar, parar novas mudancas, preservar Ethernet, remover somente perfil de
teste quando for seguro e registrar apenas evidencia sanitizada.

## Evidencia esperada

A evidencia C4.2 deve ser um README sanitizado, sem outputs brutos.

Conteudo esperado:

- objetivo;
- execucao hibrida;
- placa: desenvolvimento, sem IP ou hostname;
- rede: teste, sem SSID real;
- Codex nao recebeu senha;
- C3 antes/depois/final;
- resultado agregado;
- perfil removido ou estado final;
- Ethernet preservada;
- privacidade;
- confirmacao de que nada foi escrito em `/data`;
- confirmacao de que `/data/config/config.json` nao foi escrito;
- confirmacao de que launcher, renderer, `systemd` e `kiosky-player` nao foram
  alterados;
- conclusao;
- bloqueios remanescentes.

Nao versionar:

- saida bruta de `nmcli`, `ip`, `iw` ou NetworkManager;
- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome real de conexao;
- URLs;
- secrets;
- payloads;
- paths privados.
