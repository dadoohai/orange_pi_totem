# C4.0 - plano de bancada para Wi-Fi controlado

Status: planejamento. Nao executa comandos mutaveis.

Data: 2026-05-02

## Objetivo de C4

C4 sera a primeira fase que podera alterar Wi-Fi, mas somente em bancada e
somente depois de aprovacao humana explicita para a execucao C4.1.

C4 deve:

- acontecer apenas na placa de desenvolvimento selecionada;
- preservar Ethernet como linha de vida;
- manter acesso fisico disponivel durante toda a rodada;
- usar rede de teste controlada, sem dados reais de cliente;
- registrar evidencia sanitizada;
- validar rollback antes de qualquer conclusao positiva.

C4 ainda nao e producao. C4 nao e hotspot, nao e portal local, nao e
onboarding final, nao grava config do player e nao substitui C5/C6.

Este documento e C4.0: plano. Ele nao autoriza execucao imediata de comandos
mutaveis.

## Diferenca entre C3, C4.0 e C4.1

### C3 - diagnostico read-only

C3 observa estado agregado de rede/Wi-Fi usando comandos allowlisted e publica
somente dados sanitizados. C3 nao conecta, desconecta, cria perfil, remove
perfil, testa senha, cria hotspot ou chama internet/backend.

### C4.0 - plano sem execucao

C4.0 define pre-condicoes, comandos candidatos, rollback, sequencia,
criterios de sucesso, criterios de aborto e evidencia esperada. C4.0 nao usa
SSH, nao toca nas placas, nao executa `nmcli`, `ip`, `iw` ou qualquer comando
remoto, e nao altera NetworkManager.

### C4.1 - execucao controlada futura

C4.1 sera uma rodada separada. Nela, comandos mutaveis so poderao ser usados
se houver aprovacao humana explicita, placa de desenvolvimento confirmada,
Ethernet preservada, rede de teste definida e rollback aceito antes do inicio.

## Pre-condicoes antes de C4.1

Antes de iniciar C4.1, todos os itens abaixo precisam estar verdadeiros:

- placa de desenvolvimento selecionada;
- placa de homologacao proibida para a rodada;
- Ethernet conectada e preservada;
- acesso fisico disponivel;
- fonte e tela estaveis;
- operador humano presente;
- C3 read-only rodado antes da alteracao;
- backup ou registro sanitizado do estado anterior criado;
- rede de teste nao sensivel definida;
- senha de teste nao real ou ambiente controlado definido;
- nome do perfil de teste definido como placeholder publico;
- criterio de abortar confirmado;
- rollback revisado antes de qualquer comando mutavel;
- evidencia sanitizada preparada sem artefatos brutos versionados.

## Proibicoes permanentes

Mesmo quando C4.1 for autorizado, continuam proibidos:

- derrubar Ethernet de bancada;
- publicar SSID, senha, IP, gateway, hostname, MAC, BSSID, nome de conexao ou
  DNS real;
- usar rede real de cliente na primeira rodada;
- mexer na placa de homologacao;
- executar comandos sem plano de rollback;
- fazer hotspot;
- criar portal local;
- escrever config do player;
- escrever em `/data/config/config.json`;
- misturar C4 com C5/C6;
- instalar pacotes;
- alterar launcher, renderer, `systemd` ou `kiosky-player`;
- versionar artefatos brutos de rede;
- apagar conexoes antigas.

## Comandos mutaveis candidatos para C4.1

Os comandos abaixo sao apenas candidatos para revisao humana em C4.1. Nao foram
executados em C4.0.

## Regra de senha e secrets na execucao C4.1

Senha Wi-Fi nunca deve aparecer em linha de comando registrada. A senha tambem
nao deve aparecer em README, chat, terminal copiado, historico, script, arquivo
temporario versionavel ou evidencia.

Se senha for necessaria, ela deve ser digitada interativamente por humano ou
usada em rede de teste descartavel conforme procedimento aprovado. Comandos em
documentos devem usar placeholders e nunca devem conter valor real de senha.

Qualquer saida que ecoe senha, SSID real ou nome de conexao real vira artefato
bruto proibido. Se houver duvida sobre exposicao da senha, abortar antes do
comando.

### Permitidos somente em C4.1 com aprovacao

Usar placeholders em documentacao, revisao e evidencia:

- `WIFI_TEST_SSID`;
- `WIFI_TEST_CONNECTION_NAME`;
- senha: fornecida interativamente pelo humano, nao registrada.

Candidatos a revisar:

```sh
nmcli connection add type wifi ifname "*" con-name WIFI_TEST_CONNECTION_NAME ssid WIFI_TEST_SSID
# inserir segredo somente por metodo seguro aprovado; nao registrar senha inline
nmcli connection up WIFI_TEST_CONNECTION_NAME
nmcli -t -f DEVICE,TYPE,STATE device status
nmcli -t -f NAME,TYPE,DEVICE connection show --active
nmcli connection down WIFI_TEST_CONNECTION_NAME
nmcli connection delete WIFI_TEST_CONNECTION_NAME
python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-before
python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-after
```

Observacoes:

- os comandos `nmcli -t ...` de verificacao podem ser substituidos por C3 para
  manter a publicacao sanitizada;
- qualquer comando que mostre SSID, senha, IP, gateway ou nome real deve ter
  saida tratada como artefato bruto nao versionavel;
- a senha de teste nao deve aparecer em linha de comando, README, issue, PR,
  commit, chat, historico, script ou arquivo persistente do repositorio.

### Proibidos mesmo em C4.1

Continuam proibidos:

```sh
nmcli connection down <CONEXAO_ANTIGA_OU_ETHERNET>
nmcli connection delete <CONEXAO_ANTIGA_OU_ETHERNET>
nmcli connection modify <CONEXAO_ANTIGA_OU_ETHERNET> ...
nmcli device disconnect <ETHERNET_DEVICE>
rfkill block wifi
rfkill unblock wifi
ip route add ...
ip route delete ...
ip addr add ...
ip addr delete ...
systemctl start ...
systemctl stop ...
systemctl restart ...
systemctl enable ...
systemctl disable ...
apt ...
```

Tambem continuam proibidos hotspot, portal local, mudanca de launcher,
renderer, `systemd`, `kiosky-player`, escrita em `/data` e teste de
internet/backend externo sem decisao propria.

## Estrategia de rollback NetworkManager

C4.1 deve preservar a conexao anterior e tratar o perfil Wi-Fi de teste como
descartavel.

Regras:

- nunca apagar conexoes antigas;
- nunca modificar perfil Ethernet;
- nunca desconectar Ethernet;
- criar apenas perfil com nome de teste controlado;
- registrar que um perfil de teste foi criado, sem publicar nome real se ele
  contiver dado sensivel;
- remover somente o perfil de teste ao final ou em rollback;
- se a conexao de teste falhar, registrar erro publico e remover apenas o perfil
  de teste;
- se SSH cair, parar a automacao e acionar operador fisico; nao insistir em
  comandos remotos;
- se NetworkManager ficar em estado ambiguo, abortar a rodada, manter Ethernet
  conectada, coletar somente diagnostico sanitizado e chamar revisao humana;
- se for necessario reiniciar algo para recuperar bancada, isso sai de C4.1 e
  exige nova aprovacao humana.

Rollback nominal:

1. parar tentativa de uso do perfil de teste, se estiver ativa;
2. remover somente `WIFI_TEST_CONNECTION_NAME`;
3. rodar C3 read-only depois do rollback;
4. confirmar `ethernet_connected=true` no estado agregado;
5. registrar evidencia sanitizada;
6. nao publicar saida bruta de NetworkManager.

## Sequencia proposta para C4.1

Sequencia futura, sem execucao em C4.0:

1. Confirmar placa de desenvolvimento e proibir placa de homologacao.
2. Confirmar operador humano, acesso fisico, fonte/tela estaveis e Ethernet.
3. Copiar script C3 para `/tmp`, se necessario.
4. Rodar C3 snapshot antes.
5. Confirmar no agregado que Ethernet esta preservada.
6. Criar perfil Wi-Fi de teste com `WIFI_TEST_CONNECTION_NAME`.
7. Inserir senha por metodo seguro aprovado, sem registro em comando ou
   evidencia.
8. Tentar conectar usando `WIFI_TEST_SSID` e `WIFI_TEST_CONNECTION_NAME`.
9. Verificar estado por C3 ou leitura local tratada como artefato bruto.
10. Registrar sucesso ou erro sanitizado.
11. Desconectar e remover somente o perfil de teste, se necessario para
    rollback ou encerramento.
12. Rodar C3 snapshot depois.
13. Comparar estados agregados antes/depois.
14. Confirmar Ethernet preservada.
15. Registrar evidencia README sanitizada.
16. Nao versionar artefatos brutos.

## Criterios de sucesso

C4.1 so deve ser considerada bem-sucedida se:

- Ethernet permaneceu preservada;
- nenhuma credencial foi publicada;
- Wi-Fi de teste conectou ou falhou de forma recuperavel;
- rollback foi testado;
- C3 antes/depois ficou limpo;
- nada foi escrito em `/data`;
- `/data/config/config.json` nao foi escrito;
- player, launcher, renderer e `systemd` nao foram alterados;
- nenhum reboot foi obrigatorio;
- NetworkManager nao ficou em estado ambiguo;
- evidencia foi sanitizada e revisada.

## Criterios de abortar

Abortar C4.1 se qualquer item ocorrer:

- SSH instavel;
- Ethernet ausente;
- acesso fisico indisponivel;
- operador humano nao confirma continuidade;
- comando retorna erro inesperado;
- NetworkManager entra em estado desconhecido;
- qualquer dado sensivel aparece em output compartilhavel;
- risco de derrubar bancada;
- perfil antigo aparece como alvo de alteracao;
- rede de teste deixa de ser controlada;
- duvida sobre rollback antes do proximo comando.

Ao abortar, a prioridade e preservar Ethernet, parar novas mudancas e registrar
somente evidencia sanitizada.

## Evidencia sanitizada esperada

C4.1 deve criar apenas README sanitizado em diretorio de evidencia, por exemplo:

```text
docs/evidence/candidate-a/runs/YYYYMMDD-HHMMSS-c4-wifi-controlled-dev/README.md
```

Conteudo esperado:

- objetivo da rodada;
- placa: desenvolvimento, sem IP ou hostname;
- rede: teste, sem SSID real;
- comandos descritos com placeholders;
- C3 antes/depois;
- resultado agregado;
- rollback executado;
- confirmacao de Ethernet preservada;
- confirmacao de que nada foi escrito em `/data`;
- confirmacao de que launcher, renderer, `systemd` e `kiosky-player` nao foram
  alterados;
- inspecao de privacidade;
- conclusao;
- bloqueios remanescentes.

Nao versionar:

- saida bruta de `nmcli`;
- saida bruta de `ip`;
- saida bruta de `iw`;
- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome de conexao real;
- URLs;
- secrets;
- payloads;
- paths privados.

## Decisoes humanas antes de C4.1

Antes do proximo prompt de execucao, um humano deve decidir:

- qual placa de desenvolvimento sera usada;
- qual rede de teste controlada sera usada;
- se a senha de teste pode ser digitada interativamente sem entrar em arquivos;
- qual nome de perfil de teste sera aceito;
- se a remocao do perfil de teste ao final sera obrigatoria;
- quem fica com acesso fisico durante a rodada;
- qual erro exige abortar imediatamente;
- se internet/backend continuam fora do escopo, como recomendado para a
  primeira C4.1.
