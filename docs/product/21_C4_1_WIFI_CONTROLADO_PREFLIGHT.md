# C4.1-preflight - roteiro final para Wi-Fi controlado

Status: preflight documental. Nao executa comandos.

Data: 2026-05-02

## Objetivo

Este documento prepara a execucao C4.1, que sera a primeira rodada futura com
Wi-Fi mutavel em bancada. O objetivo e confirmar decisoes humanas, reduzir
risco antes de qualquer alteracao real e corrigir o ponto critico de secrets:
senha Wi-Fi nao pode aparecer em comando registrado, README, chat, historico,
script, arquivo versionado ou evidencia.

C4.1-preflight nao usa SSH, nao toca nas placas, nao executa `nmcli`, `ip`,
`iw` ou qualquer comando remoto, nao altera NetworkManager e nao cria perfil
real.

## Decisoes humanas obrigatorias antes de execucao

Checklist ainda nao preenchido:

- [ ] Placa de desenvolvimento autorizada.
- [ ] Placa de homologacao explicitamente fora do escopo.
- [ ] Operador com acesso fisico presente.
- [ ] Ethernet conectada.
- [ ] Fonte e tela estaveis.
- [ ] Rede de teste controlada definida.
- [ ] Senha de teste controlada definida.
- [ ] Metodo seguro de inserir senha sem registrar definido.
- [ ] Nome do perfil de teste definido.
- [ ] Perfil de teste sera removido ao final: sim/nao. Recomendado: sim.
- [ ] Internet/backend fora do escopo inicial: sim/nao. Recomendado: sim.
- [ ] Criterio de abortar definido.
- [ ] Responsavel por autorizar prosseguir comando a comando definido.
- [ ] Evidencia sanitizada esperada revisada.

## Roteiro de execucao futura C4.1

Sequencia futura, sem execucao neste preflight:

1. Confirmar decisoes humanas do checklist.
2. Copiar ou confirmar script C3 em `/tmp`, se necessario.
3. Rodar C3 snapshot antes.
4. Confirmar Ethernet agregada no C3 antes.
5. Preparar perfil de teste com `WIFI_TEST_CONNECTION_NAME`.
6. Inserir senha por metodo seguro aprovado, sem registrar valor em comando,
   terminal copiado, historico, arquivo ou evidencia.
7. Tentar conexao com rede de teste.
8. Rodar C3 snapshot durante ou depois da tentativa.
9. Registrar sucesso ou erro de forma sanitizada.
10. Remover perfil de teste se definido no checklist.
11. Rodar C3 snapshot final.
12. Confirmar Ethernet preservada.
13. Criar README de evidencia sanitizado.
14. Revisar que nenhum artefato bruto foi versionado.

## Comandos futuros

Os comandos abaixo sao exemplos a revisar na execucao. Eles nao sao
autorizacao automatica. Nao incluem SSID real, senha real, IP ou hostname.

Placeholders permitidos:

- `WIFI_TEST_SSID`;
- `WIFI_TEST_CONNECTION_NAME`;
- senha: fornecida interativamente pelo humano, nao registrada.

## Regra forte: Codex nao executa comando que solicite senha Wi-Fi

Codex nao deve executar `nmcli --ask connection up` se o comando puder
solicitar senha Wi-Fi. Qualquer acao com credencial acontece fora do agente.

Qualquer etapa que envolva senha deve ser feita localmente por humano, fora de
chat, log, transcript, terminal remoto gerenciado pelo Codex, historico, script
ou arquivo versionavel. "Nao colocar senha inline" nao e suficiente se a senha
ainda for digitada em uma sessao controlada pelo agente.

Codex pode preparar comandos com placeholders e pode registrar resultado
sanitizado depois. Se a proxima tentativa exigir senha via sessao Codex/SSH,
abortar antes do comando.

Exemplos a revisar:

```sh
python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-before
nmcli connection add type wifi ifname "*" con-name WIFI_TEST_CONNECTION_NAME ssid WIFI_TEST_SSID
# inserir senha somente por metodo seguro aprovado; nao registrar senha inline
nmcli connection up WIFI_TEST_CONNECTION_NAME
python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-after
nmcli connection down WIFI_TEST_CONNECTION_NAME
nmcli connection delete WIFI_TEST_CONNECTION_NAME
python3 /tmp/totem_wifi_readonly_snapshot.py --out-dir /tmp/dadooh-c3-wifi-readonly-final
```

Observacoes:

- se qualquer ferramenta ecoar senha, SSID real ou nome real de conexao, a
  saida vira artefato bruto proibido;
- saida bruta de `nmcli`, `ip` ou `iw` nao deve ser versionada;
- usar C3 para evidencia agregada sempre que possivel;
- a execucao deve parar antes do comando se a senha precisaria ser colada
  inline.

## Comandos proibidos

Continuam proibidos em C4.1:

- qualquer comando que altere Ethernet;
- qualquer comando que apague conexao antiga;
- qualquer comando com senha real inline;
- qualquer comando em placa de homologacao;
- hotspot;
- portal local;
- `apt`;
- `systemctl`;
- escrita em `/data`;
- escrita em `/data/config/config.json`;
- alteracao de launcher, renderer, `systemd` ou `kiosky-player`;
- `ping`, `curl`, `wget` ou backend externo, salvo decisao futura separada.

## Criterios de parar antes de comecar

Nao iniciar C4.1 se qualquer item ocorrer:

- sem acesso fisico;
- Ethernet ausente;
- rede de teste nao definida;
- senha teria que ser colada em comando;
- operador nao consegue confirmar rollback;
- duvida sobre placa;
- C3 antes nao roda limpo;
- criterio de abortar nao foi confirmado;
- responsavel por prosseguir comando a comando nao foi definido.

## Evidencia esperada

A evidencia C4.1 deve ser somente README sanitizado no repositorio.

O README deve conter:

- objetivo da rodada;
- placa: desenvolvimento, sem IP ou hostname;
- rede: teste, sem SSID real;
- comandos com placeholders;
- C3 antes/depois/final com campos agregados;
- resultado agregado;
- rollback ou remocao do perfil de teste;
- confirmacao de Ethernet preservada;
- confirmacao de que nada foi escrito em `/data`;
- inspecao de privacidade;
- conclusao.

Nao incluir:

- outputs brutos;
- SSID real;
- senha;
- IP;
- gateway;
- hostname;
- MAC;
- BSSID;
- DNS real;
- nome de conexao real;
- URL privada;
- secrets;
- payloads;
- paths privados.
