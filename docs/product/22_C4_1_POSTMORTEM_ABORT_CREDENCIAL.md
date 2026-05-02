# C4.1-postmortem - abort seguro por credencial

Status: postmortem documental. Nao repete C4.1.

Data: 2026-05-02

## Resumo da rodada

A primeira rodada C4.1 foi iniciada em bancada na placa de desenvolvimento para
validar Wi-Fi real controlado com Ethernet preservada. A rodada foi abortada
antes de inserir senha, porque o proximo passo poderia solicitar credencial por
um canal remoto gerenciado pelo Codex.

O resultado correto da rodada foi o abort seguro: nao houve tentativa de
conexao Wi-Fi, a senha nao foi inserida, o perfil descartavel foi removido e a
evidencia foi registrada de forma sanitizada.

## O que foi executado

Foram executadas apenas etapas preparatorias e rollback:

- validacao local do script C3;
- copia do script C3 para `/tmp` na placa de desenvolvimento;
- self-test C3 na placa;
- snapshot C3 antes da alteracao;
- criacao de um perfil Wi-Fi descartavel com placeholders;
- abort antes de qualquer comando que pudesse solicitar senha;
- remocao do perfil descartavel;
- snapshot C3 final;
- README de evidencia sanitizada.

Nao foi executado `nmcli --ask connection up`, nao houve insercao de senha e
nao houve tentativa de conexao Wi-Fi.

## Por que foi abortado

O proximo comando planejado poderia pedir senha Wi-Fi. Mesmo sem senha inline,
um prompt interativo em sessao Codex/SSH/chat poderia registrar credencial em
transcript, terminal copiado, log, historico, ferramenta ou evidencia.

A decisao segura foi abortar antes do comando. Nesta fase, "nao inline" nao e
suficiente se o agente ainda participa do canal que recebe a senha.

## O que funcionou

- Perfil descartavel criado.
- Senha nao inserida.
- `nmcli --ask connection up` nao executado.
- Rollback executado.
- Perfil descartavel removido conforme evidencia da rodada.
- Ethernet preservada antes e no snapshot final.
- Nada escrito em `/data`.
- `/data/config/config.json` nao escrito.
- Launcher, renderer, `systemd` e `kiosky-player` nao alterados.
- Evidencia sanitizada criada sem SSID, senha, IP, hostname, MAC, BSSID,
  gateway, DNS real ou nome real de conexao.

## O que nao foi validado

- Conexao Wi-Fi.
- Senha correta ou incorreta.
- Obtencao de conectividade por Wi-Fi.
- Conectividade de internet.
- Backend.
- Persistencia apos reboot.
- Comportamento de reconexao automatica.

## Verificacao de residuo do perfil

A evidencia da rodada abortada registrou rollback concluido para o perfil
descartavel e snapshot final com Ethernet preservada.

Nesta revisao, foi feita verificacao remota adicional read-only somente na
placa de desenvolvimento. A verificacao consultou apenas se o perfil
placeholder de teste existia, sem imprimir lista de conexoes e sem publicar
nomes reais.

Resultado sanitizado desta revisao:

- perfil placeholder de teste nao encontrado;
- perfil placeholder de teste nao estava ativo;
- nenhuma lista de conexoes foi publicada;
- nenhum nome real de conexao foi publicado;
- nenhum SSID, IP, gateway, hostname, MAC, BSSID ou DNS real foi publicado;
- nenhuma conexao foi alterada.

## Licao principal

Codex, SSH remoto gerenciado pelo agente, chat e transcript nao devem ser canal
de insercao de senha Wi-Fi. A regra vale mesmo quando a senha nao aparece inline
no comando.

Qualquer etapa que possa receber segredo precisa acontecer fora do agente ou
usar uma rede de teste descartavel cujo segredo nao seja sensivel.

## Decisao proposta

A proxima tentativa C4.1 deve ser hibrida ou local:

- Codex pode preparar comandos com placeholders;
- Codex pode rodar C3 antes e depois;
- a etapa que recebe senha deve ser executada por humano fora do Codex;
- Codex pode registrar apenas resultado sanitizado depois;
- se a senha precisar passar por Codex, SSH gerenciado pelo agente, chat,
  historico, script ou evidencia, abortar antes.

## Alternativas

1. Humano executa a etapa de senha no console fisico da placa.
2. Humano usa rede de teste descartavel com credencial nao sensivel.
3. Adiar Wi-Fi mutavel ate existir mecanismo seguro para segredo.

## Recomendacao

Preferir execucao hibrida:

1. Codex roda C3 antes.
2. Humano executa localmente a etapa sensivel de conexao Wi-Fi.
3. Codex roda C3 depois.
4. Humano remove o perfil de teste localmente, ou autoriza uma remocao remota
   sem segredo.
5. Codex registra evidencia sanitizada.

Nao repetir C4.1 remoto com senha via Codex/SSH/chat.
