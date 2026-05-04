# C9.1.2 - diagnostico controlado da proporcao visual pos-restauracao

Status: concluido como diagnostico controlado. Nao e producao.

Data: 2026-05-04

## 1. Objetivo

C9.1.2 investiga o warning visual observado depois de C9.1.1: apos restaurar o
player, a midia pareceu com proporcao diferente ou mais esticada.

O objetivo e separar causas possiveis sem alterar config real:

- estado atual do player;
- stop/start controlado do servico;
- troca de TTY/openvt/wizard;
- modo HDMI/framebuffer;
- propriedades MPV observaveis por IPC;
- percepcao visual humana.

## 2. Contexto

C9.1.1 passou tecnicamente:

- wizard local apareceu na HDMI;
- teclado USB funcionou;
- candidata foi gerada em `/tmp`;
- C5.1 `allow-mock` passou;
- C5.1 `real-dry-run` falhou como esperado;
- servico foi restaurado `active/enabled`;
- `NRestarts=0`;
- player=1;
- MPV=1;
- renderer=0.

Ressalvas:

- UI ainda parece terminal Linux/Python interativo;
- nao e UX final para operador;
- humano percebeu possivel alteracao de proporcao visual apos restaurar o
  player.

## 3. Analise critica

O warning pode ocorrer sem mudanca de config por:

- renegociacao de modo HDMI depois de trocar TTY ou reiniciar MPV;
- framebuffer ativo com dimensoes diferentes da expectativa da midia;
- MPV fullscreen usando area de saida diferente;
- diferenca entre dimensoes do video e dimensoes de saida (`dwidth/dheight`);
- troca de midia no momento da observacao;
- efeito visual de conteudo vertical em tela paisagem;
- percepcao humana apos ver terminal/wizard e voltar para midia.

O stop/start do servico precisa ser isolado antes de repetir wizard/openvt,
porque C9.1.1 misturou parada do player, TTY local e execucao do wizard.

## 4. Scripts

Coletor local:

```text
scripts/board/totem_visual_aspect_diagnostic.py
```

Runner remoto:

```text
scripts/remote/run_c9_1_2_visual_aspect_diagnostic.sh
```

O coletor usa Python stdlib e grava apenas em `/tmp`.

## 5. Evidencia

Diretorio padrao:

```text
/tmp/dadooh-c9-1-2-visual-aspect/
```

Arquivos:

```text
status.json
summary.txt
snapshots/<fase>.json
```

Permissoes:

- diretorios `0700`;
- arquivos `0600`.

## 6. Dados coletados

Cada snapshot registra de forma sanitizada:

- `kiosky-player.service`: active/enabled/SubState/NRestarts;
- contagens de processos: player, MPV, renderer;
- categorias de flags MPV observadas em processo, sem cmdline bruta;
- TTY ativa;
- framebuffer: `virtual_size`, `modes`, bpp e rotate;
- conectores DRM: status, enabled, contagem de modos e primeiro modo;
- status publico allowlisted de `/tmp/kiosky-status.json`;
- propriedades MPV via IPC allowlisted:
  - `width`;
  - `height`;
  - `dwidth`;
  - `dheight`;
  - `video-params`;
  - `video-out-params`;
  - `osd-dimensions`;
  - `fullscreen`;
  - `pause`;
  - `time-pos`.

Nao sao consultados `path`, `filename`, playlist, metadata ou URLs.

## 7. Modos

Fase A, read-only:

```text
scripts/remote/run_c9_1_2_visual_aspect_diagnostic.sh root@192.168.18.115 --read-only
```

Fase B, stop/start controlado:

```text
scripts/remote/run_c9_1_2_visual_aspect_diagnostic.sh root@192.168.18.115 --stop-start
```

Fase B so pode ser executada depois da autorizacao humana explicita:

```text
Autorizo C9.1.2: stop/start controlado do serviço apenas para diagnóstico visual de proporção.
```

Fase C, wizard/openvt:

- so deve ser considerada se Fase A/B nao explicarem ou nao reproduzirem o
  warning;
- exige autorizacao humana separada;
- pode reutilizar o runner C9.1.1, acompanhado de snapshots C9.1.2 antes e
  depois.

Autorizacao exigida:

```text
Autorizo C9.1.2: repetir wizard/openvt para diagnóstico visual de proporção.
```

## 8. Guardrails

C9.1.2 nao:

- altera config;
- le `/data/config/config.json`;
- escreve `/data/config/config.json`;
- roda writer;
- usa `--enable-real-write`;
- altera flags MPV;
- altera player;
- altera repo `kiosky-player`;
- altera launcher;
- altera NetworkManager;
- executa `nmcli`;
- limpa cache;
- troca midia;
- executa upgrade;
- publica paths de midia;
- publica `api_url`, `api_key`, `environment_id` ou payload;
- libera producao.

Stop/start de servico so e permitido na Fase B com autorizacao humana explicita.

## 9. Privacidade

Status, summary e snapshots nao copiam:

- conteudo de config;
- valores privados;
- paths de midia;
- URLs;
- payload;
- logs brutos;
- linhas de comando brutas;
- PIDs;
- metadados de rede.

## 10. Validacao humana

Apos cada fase, o humano deve responder:

- a proporcao parece normal?
- a midia parece esticada?
- a diferenca e igual ao warning observado em C9.1.1?
- houve troca visivel de TTY/terminal que possa ter influenciado a percepcao?

## 11. Criterios de sucesso

Criterios:

- Fase A read-only gera snapshot sanitizado;
- se autorizada, Fase B separa stop/start de wizard/openvt;
- snapshots permitem comparar TTY, framebuffer, DRM, MPV e processos;
- servico termina restaurado `active/enabled`;
- renderer nao fica concorrendo;
- `NRestarts=0` ou divergencia fica registrada claramente;
- nenhuma config real e lida ou escrita;
- producao continua bloqueada.

## 12. Resultado esperado

Se o warning reproduzir no stop/start, a causa provavel fica no ciclo
servico/MPV/display e nao no wizard em si.

Se nao reproduzir no stop/start, mas reproduzir ao repetir wizard/openvt, a
hipotese de TTY/openvt ganha forca.

Se nao reproduzir, registrar como warning nao reproduzido, manter cautela antes
de integrar o wizard ao launcher e evitar bloquear indefinidamente sem nova
evidencia.

## 13. Resultado executado

Fase A - snapshot read-only atual:

- executada sem stop/start;
- servico `active/enabled`, SubState `running`;
- `NRestarts=0`;
- player=1;
- MPV=1;
- renderer=0;
- TTY ativa: `tty1`;
- framebuffer `fb0`: `1360,768`, `32` bpp, rotate `0`;
- HDMI `card0-HDMI-A-1`: `connected/enabled`;
- modos anunciados pelo HDMI: `1024x768`, `800x600`, `800x600`, `848x480`,
  `640x480`;
- MPV fullscreen com `--vo=gpu`, `--gpu-context=drm`, `--ao=null`;
- sem `--geometry`;
- sem `--video-unscaled`;
- IPC MPV respondeu com sucesso;
- OSD MPV reportou `1024x768`, aspect `1.333333`;
- video observado por IPC estava em conteudo vertical, com `rotate=270`.

Validacao visual humana da Fase A:

- a midia continuava esticada antes de qualquer stop/start desta etapa.

Fase B - stop/start controlado:

- executada apos autorizacao humana explicita;
- stop/start do `kiosky-player.service` realizado;
- restauracao final `active/enabled`;
- `NRestarts=0`;
- player=1;
- MPV=1;
- renderer=0;
- TTY ativa permaneceu `tty1`;
- framebuffer permaneceu `1360,768`;
- HDMI permaneceu `connected/enabled`;
- MPV continuou fullscreen, sem `--geometry` e sem `--video-unscaled`;
- OSD MPV continuou reportando `1024x768`, aspect `1.333333`.

Validacao visual humana da Fase B:

- a imagem continuou exatamente igual;
- nao melhorou nem piorou apos o stop/start controlado.

Conclusao:

- o warning visual nao foi introduzido pelo stop/start executado em C9.1.2;
- a aparencia esticada ja estava presente na Fase A e permaneceu igual na
  Fase B;
- por isso, repetir wizard/openvt nao foi necessario nesta rodada;
- a hipotese mais forte passou a ser adequacao de modo/resolucao por tela
  fisica/EDID/framebuffer/MPV, nao regressao causada diretamente pelo wizard.

Ponto tecnico relevante:

- o humano suspeitava que a tela fosse Full HD;
- a placa nao observou modo `1920x1080` no HDMI durante esta etapa;
- os modos anunciados foram 4:3 ou proximos, com `1024x768` como primeiro modo;
- a placa estava com framebuffer `1360x768`, enquanto o MPV reportou OSD
  `1024x768`;
- isso sugere necessidade futura de um contrato de display/orientacao/modo por
  tipo de tela, possivelmente com seletor ou preflight visual.

## 14. Evidencia sanitizada

Artefatos na placa:

```text
/tmp/dadooh-c9-1-2-visual-aspect/status.json
/tmp/dadooh-c9-1-2-visual-aspect/summary.txt
/tmp/dadooh-c9-1-2-visual-aspect/snapshots/phase-a-current.json
/tmp/dadooh-c9-1-2-visual-aspect/snapshots/phase-b-before-stop.json
/tmp/dadooh-c9-1-2-visual-aspect/snapshots/phase-b-after-start.json
/tmp/dadooh-c9-1-2-visual-aspect/phase-b-operation.json
/tmp/dadooh-c9-1-2-visual-aspect/phase-b-operation-summary.txt
```

Os artefatos registram apenas metadados, categorias e propriedades MPV
allowlisted. Nao copiam config, valores privados, paths de midia, URLs, logs
brutos, cmdlines brutas ou PIDs.

## 15. Proximos passos

Recomendacao:

- nao bloquear C9 indefinidamente por este warning sem nova evidencia;
- antes de integrar o wizard ao launcher, criar uma etapa de produto para
  contrato visual de tela: modo HDMI, orientacao, area de exibicao, proporcao e
  possivel seletor por tipo de tela;
- considerar um preflight visual simples com padrao de teste para o operador
  confirmar se circulos/quadrados aparecem corretos;
- manter a atual config real intacta ate uma etapa aprovada especificamente
  para display/orientacao.
