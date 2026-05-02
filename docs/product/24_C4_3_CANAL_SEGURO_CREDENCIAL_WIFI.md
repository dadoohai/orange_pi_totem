# C4.3 - canal seguro para credencial Wi-Fi

Status: definicao de processo. Canal humano/local definido como SSH proprio
fora do Codex. Nao executa Wi-Fi.

Data: 2026-05-02

## Objetivo

Definir como a proxima tentativa C4 deve obter um canal seguro para inserir
credencial Wi-Fi fora do Codex.

C4.3 nao conecta Wi-Fi, nao cria perfil, nao executa `nmcli`, nao executa
`nmtui`, nao usa SSH, nao toca na placa e nao altera NetworkManager. Este
documento existe para remover o bloqueio operacional identificado em C4.2 antes
de qualquer nova tentativa real.

## Contexto

C4.2 foi encerrado como abort seguro:

- C4.2 foi abortado antes de conectar;
- Codex nao recebeu senha;
- nenhuma tentativa Wi-Fi foi feita;
- player seguia em execucao;
- Ethernet preservada;
- nada escrito em `/data`;
- `/data/config/config.json` nao foi escrito;
- nenhum perfil de teste foi criado localmente;
- o diagnostico C3 antes/depois/final continuou sanitizado.

O bloqueio atual nao e tecnico do Wi-Fi. O bloqueio e operacional: nao havia,
naquele momento, um canal local seguro fora do Codex para inserir credencial
enquanto o player estava rodando na tela.

Atualizacao de processo: o canal humano/local escolhido para a proxima
tentativa e uma conexao SSH propria do humano, fora do Codex e fora do
transcript do agente. Essa conexao pode ser usada pelo humano para executar a
etapa sensivel localmente, sem enviar senha, SSID real, nome real de conexao ou
output bruto ao Codex.

## Problema identificado

- O player ocupa a tela HDMI.
- O humano nao tinha terminal local seguro disponivel para inserir credencial.
- Codex, chat, transcript, SSH gerenciado pelo agente, script e arquivo
  versionavel nao podem receber senha Wi-Fi.
- `nmcli --ask` ou qualquer prompt equivalente nao deve ser executado pelo
  Codex se puder solicitar senha.

Sem canal humano/local seguro, a unica decisao correta e abortar antes da
tentativa de conexao.

## Opcoes seguras futuras

1. Humano abrir SSH proprio fora do Codex e usar `nmtui` ou `nmcli` localmente.
2. Humano conectar teclado/console fisico e executar `nmtui` localmente.
3. Tecnico local executar a etapa sensivel e retornar apenas frase sanitizada.
4. Adiar Wi-Fi mutavel ate existir modo proprio de setup/manutencao local.

Em todas as opcoes, Codex pode rodar C3 antes/depois/final e registrar apenas
evidencia sanitizada, desde que nao receba senha, SSID real, nome real de
conexao ou output bruto.

## Opcoes proibidas

Continuam proibidos:

- senha no chat;
- senha em comando inline;
- senha em script;
- senha em README;
- senha em terminal ou transcript controlado pelo Codex;
- output bruto do `nmcli` no chat;
- SSID real ou nome real de conexao em evidencia;
- Codex executar comando que peca senha;
- Codex executar `nmcli --ask connection up`;
- Codex executar `nmtui` para capturar credencial;
- Codex criar hotspot ou portal nesta fase.

## Decisao recomendada

A proxima tentativa C4 so deve ocorrer se houver canal humano/local fora do
Codex para inserir a credencial Wi-Fi.

Modelo recomendado:

1. Codex roda C3 antes.
2. Humano usa canal local seguro fora do Codex para executar a etapa sensivel.
3. Humano retorna apenas frase sanitizada.
4. Codex roda C3 depois.
5. Humano remove perfil de teste localmente, ou autoriza remocao sem segredo e
   sem nome real.
6. Codex roda C3 final.
7. Codex registra evidencia sanitizada.

Se o canal seguro nao existir, abortar antes de criar perfil, conectar Wi-Fi ou
solicitar senha.

## Impacto no roadmap

- C4.2 validou o processo de abort seguro.
- C4 real segue bloqueado ate existir canal seguro de credencial.
- A proxima etapa C4 deve resolver o canal humano/local antes de tentar Wi-Fi
  novamente.
- O bloqueio antecipa a necessidade futura de modo de setup/manutencao local,
  para que o operador tenha um caminho seguro de entrada de credencial sem
  depender de Codex, chat ou SSH gerenciado pelo agente.

## Criterios para executar nova tentativa C4

Antes de nova execucao real:

- canal local seguro escolhido: SSH humano proprio fora do Codex;
- operador humano treinado para nao copiar output bruto;
- frases sanitizadas de retorno confirmadas;
- Ethernet preservada;
- C3 antes planejado;
- rollback/remocao do perfil de teste definido;
- internet/backend externo mantidos fora do escopo, salvo decisao separada.
