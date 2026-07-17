# 202 - C26 - Recuperacao local pelo usuario

Status: decisao refinada e aprovada para implementacao. Nao declara que os
novos controles ja existem.

Data: 2026-07-17

## Missao

Reduzir visitas tecnicas dando a uma pessoa nao tecnica poucos comandos locais
capazes de recuperar o totem ou devolve-lo a uma configuracao valida. O fluxo
deve funcionar sem suporte remoto, ter baixo atrito cognitivo e preservar a
baseline `prod15`.

Prioridade: primeiro oferecer ancoras amplas e previsiveis. Diagnostico
granular e tratamento de casos especificos evoluem depois, a partir de falhas
reais.

## Base preservada

- `prod15 + C25B + C21.24` continua sendo a referencia aceita.
- Retry, watchdog, restart do player, cache offline e rollback OTA continuam
  automaticos e invisiveis para o usuario.
- `F10` ja abre o wizard local, para o player com seguranca e o restaura ao
  sair.
- Config so vira ativa depois de candidata valida e escrita atomica com backup.
- Wi-Fi usa o perfil dedicado do produto e restaura o anterior quando a nova
  conexao falha.
- Os splashes de reboot e desligamento ja existem; o desligamento real ainda
  precisa ser validado nesta baseline.

## Experiencia escolhida

Existe uma unica entrada: segurar `F10`.

`F10` continua abrindo diretamente o wizard atual. Nao havera home nova,
`F12`, sexto passo, painel de diagnostico ou outro modelo mental. Um controle
discreto e sempre visivel no cabecalho abre `Acoes do totem`; ele participa da
mesma navegacao por setas e Enter do wizard.

A tela tem somente tres acoes e `Voltar`:

| Acao | Resultado | O que preserva | Confirmacao |
| --- | --- | --- | --- |
| `Configurar novamente` | Recomeca o wizard na primeira etapa. | Software, OTA, cache, identidade e a config ativa ate o salvamento final. | Sem confirmacao destrutiva; salvar continua sendo a confirmacao final. |
| `Reiniciar totem` | Reinicia a placa inteira e volta automaticamente. | Config, rede, cache, identidade, software e OTA. | Segunda tela, com foco inicial em cancelar. |
| `Desligar com seguranca` | Encerra o sistema e desliga a placa. | Todos os dados persistentes. | Segunda tela forte; avisa que e preciso retirar e reconectar a energia para ligar. |

`Esc` ou `Voltar` sempre retorna ao wizard ou a exibicao sem executar acao.
Nenhuma opcao mutante recebe foco inicial e repeticao de tecla nao pode disparar
duas vezes.

Na confirmacao de reboot, uma unica orientacao evita promessa falsa para falha
de tela: `Sem imagem? Verifique antes a energia e o cabo da tela.` Ha caso real
em que a TV travou com placa e player saudaveis; reiniciar o totem nao e cura
universal para isso.

## Semantica de configuracao

`Configurar novamente` e um reset seguro do fluxo, nao factory reset:

- limpa apenas as escolhas ainda nao salvas da sessao e volta a primeira etapa;
- a config ativa permanece valida ate uma nova candidata passar e ser gravada;
- cancelar preserva a config ativa;
- uma nova rede Wi-Fi pode ser aplicada durante o wizard e permanece somente
  se conectar com sucesso; em caso de falha, o perfil anterior e restaurado;
- Ethernet, cache, imagem, identidade, releases e estado OTA nao sao apagados;
- sem internet, a UI nao pode afirmar que ambiente ou backend foram validados;
- nao revoga credencial no backend nem prepara o aparelho para outro cliente.

A copy curta da acao deve ser fiel: `A configuracao so muda ao concluir. Uma
nova rede so fica se conectar.`

## Por que nao expor outras acoes

- `Reiniciar exibicao` e redundante: o sistema ja tenta recuperar player/MPV e
  a propria sessao F10 para e restaura o player.
- `Resetar rede` e pior que o fluxo atual de troca transacional de Wi-Fi.
- `Limpar cache` pode deixar um totem offline sem nenhuma midia.
- Rollback/update manual, shell e logs sao operacoes de suporte, nao de usuario.
- Factory reset real ainda nao possui transacao unica, revogacao backend e
  comportamento seguro sob queda de energia.

Factory reset permanece no roadmap. Antes de existir, precisa declarar o que
apaga, revogar/desvincular credenciais no backend, preservar imagem/OTA e
identidade, sobreviver a queda de energia e voltar ao setup sem estado parcial.

## Execucao protegida

O wizard nunca chama comando livre nem executa reboot/poweroff diretamente.
Ele grava uma solicitacao privada presa a sessao atual, com schema fechado,
`session_id` e enum `reboot|poweroff`. O shell pai da sessao F10 valida e
executa.

Durante a acao, a sessao deve:

1. manter os locks de settings e update ja adquiridos;
2. rejeitar solicitacao ausente, repetida, adulterada ou de outra sessao;
3. limpar candidatos e credenciais temporarias;
4. nao restaurar o player durante uma transicao de energia;
5. renderizar o splash correto, sincronizar dados e chamar somente
   `systemctl --no-wall reboot` ou `systemctl --no-wall poweroff`;
6. manter os guards ate a transicao ser aceita;
7. se a chamada falhar, cancelar a transicao, restaurar o player e mostrar erro
   recuperavel.

Isso evita a janela em que a limpeza normal reabriria player/TTY enquanto o
sistema comeca a desligar.

## Entrega

O recorte cabe em `totem-core` OTA se permanecer nos arquivos ja permitidos:

- `totem_setup_visual_wizard.py`;
- `totem_open_settings_session.sh`;
- `totem_visual_splash.py`, somente se a copy precisar de ajuste.

Novo unit systemd, runner privilegiado, sudoers/polkit, binario fora da
allowlist ou alteracao do updater exigem nova imagem e ficam fora deste recorte.

Verticais:

1. **Interface e contrato:** controle discreto, foco unico, tres acoes, pedido
   tipado e self-tests adversariais.
2. **Acoes reais:** reconfiguracao segura, reboot e poweroff action-aware com os
   locks existentes.
3. **Fechamento de produto:** QA visual, testes fisicos, pacote `totem-core`,
   apply, rollback e reaplicacao na placa.

Uma vertical que bloquear nao impede testes e acabamento das demais, mas
nenhuma e promovida com regressao conhecida.

## Validacao curta

- abrir F10, entrar/sair de `Acoes do totem` e voltar a midia repetidamente;
- foco, setas, Enter, Esc, confirmacoes, key-repeat e texto em landscape e
  portrait;
- pedido vazio, antigo, duplicado, adulterado, de outra sessao ou com acao
  desconhecida deve falhar fechado;
- update ocupado deve impedir abertura/acao sem quebrar timer ou locks;
- `Configurar novamente`: cancelar, salvar config valida e falhar Wi-Fi,
  provando preservacao/rollback conforme a semantica acima;
- reboot real: boot saudavel, config/rede preservadas, player e timers ativos;
- poweroff real: desligamento limpo, religamento fisico e boot saudavel;
- interrupcao da UI e falha simulada de `systemctl` devem restaurar o player;
- gates, self-tests e fluxo completo do wizard da `prod15` sem regressao;
- pacote `totem-core` com dry-run, apply, validacao, rollback e reaplicacao.

Nao ha campanha de horas neste marco.

## Definicao de pronto

O marco fecha quando um usuario consegue, apenas por F10, configurar novamente,
reiniciar ou desligar o totem sem apagar dados por ambiguidade; quando cancelamento
e falhas retornam a um estado funcional; e quando o mesmo pacote passa QA visual,
placa real e roundtrip OTA sem regressao da `prod15`.
