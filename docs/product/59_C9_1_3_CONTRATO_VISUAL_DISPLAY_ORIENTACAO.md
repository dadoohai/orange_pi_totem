# C9.1.3 - contrato visual de display/orientacao

Status: executado como etapa curta de diagnostico/produto. Nao e producao.

Data: 2026-05-04

## 1. Objetivo

C9.1.3 cria um padrao visual simples para validar, por observacao humana, se a
tela do totem preserva proporcao, margens, orientacao e area util.

A etapa responde perguntas praticas:

- o circulo parece circulo ou oval?
- o quadrado parece quadrado ou retangulo?
- a borda aparece inteira?
- ha corte/overscan?
- a seta de topo esta correta?
- a imagem parece esticada horizontalmente ou verticalmente?

## 2. Por que existe

C9.1 provou o wizard local por teclado USB, mas a UI ainda parece terminal.
C9.1.1 validou o wizard na HDMI e registrou um warning visual de midia
aparentemente esticada depois da restauracao do player.

C9.1.2 isolou esse warning e mostrou que a aparencia esticada ja existia antes
do stop/start controlado e permaneceu igual depois. C9.1.3 existe para tirar a
comparacao do conteudo de midia e usar um padrao visual neutro, feito para
expor distorcao, corte e orientacao.

## 3. Relacao com C9.1.2

C9.1.2 ja provou:

- o stop/start executado naquela etapa nao introduziu a distorcao percebida;
- a imagem ja parecia esticada na fase read-only;
- a imagem continuou igual apos stop/start;
- o servico terminou `active/enabled`;
- `NRestarts=0`;
- player=1, MPV=1 e renderer=0;
- HDMI estava `connected/enabled`;
- framebuffer observado foi `1360x768`;
- MPV reportou OSD `1024x768`;
- os modos HDMI anunciados nao incluiram `1920x1080`.

Assim, C9.1.3 nao tenta corrigir resolucao. Ela cria evidencia visual e
metadados suficientes para decidir se C9 pode seguir com ressalva ou se deve
abrir uma frente futura de seletor/resolucao por tipo de tela.

## 4. Hipotese atual

A hipotese principal e adequacao de contrato display/modo, nao regressao direta
do wizard.

Possiveis causas ainda abertas:

- EDID da tela anunciando modos diferentes da expectativa fisica;
- framebuffer ativo diferente do modo usado pelo MPV;
- MPV fullscreen renderizando em area 4:3 ou proxima;
- tela fisica escalando a entrada HDMI;
- orientacao fisica e rotacao da midia gerando percepcao de esticamento;
- overscan/corte no painel.

## 5. Padrao visual usado

Script local:

```text
scripts/board/totem_display_visual_contract_probe.py
```

Artefato gerado:

```text
/tmp/dadooh-c9-1-3-display-contract/display-visual-contract.svg
```

O SVG contem:

- borda externa amarela;
- borda interna de seguranca;
- grid simples;
- circulo grande;
- quadrado;
- cruz central;
- setas indicando topo;
- marcadores nos quatro cantos;
- texto: "Se o círculo parecer oval, a tela está esticando a imagem.";
- texto: "Se a borda não aparecer inteira, há corte/overscan.".

O arquivo e local, sem assets externos e sem dados privados.

## 6. Execucao remota

Runner:

```text
scripts/remote/run_c9_1_3_display_visual_contract_probe.sh
```

Modo seguro/read-only:

```text
scripts/remote/run_c9_1_3_display_visual_contract_probe.sh root@192.168.18.115 --prepare-only
```

Esse modo:

- copia o probe para `/tmp`;
- roda `--self-test`;
- gera o SVG em `/tmp`;
- coleta snapshot read-only;
- nao para servico;
- nao inicia MPV temporario;
- nao ocupa HDMI.

Modo com exibicao HDMI:

```text
scripts/remote/run_c9_1_3_display_visual_contract_probe.sh root@192.168.18.115 --display
```

Antes de ocupar a tela, o runner exige a frase exata:

```text
Autorizo C9.1.3: exibir padrão visual temporário na HDMI para diagnóstico de proporção/orientação, com restauração do player ao final.
```

Sem essa confirmacao, o runner registra `blocked` e nao para player, nao inicia
MPV temporario e nao ocupa a HDMI.

## 7. Validacao humana

Durante o teste visual, o humano deve responder:

1. O circulo parece circulo ou oval?
2. O quadrado parece quadrado ou retangulo?
3. A borda aparece inteira?
4. Ha corte nas bordas?
5. A seta "TOPO" esta para cima?
6. O padrao parece esticado horizontalmente ou verticalmente?
7. Depois de restaurar o player, a midia voltou igual ao estado anterior?

O runner registra respostas normalizadas, sem texto livre:

- `circle`, `oval` ou `unclear`;
- `square`, `rectangle` ou `unclear`;
- `yes`, `no` ou `unclear`;
- `none`, `horizontal`, `vertical` ou `unclear`;
- `same`, `changed`, `not_restored` ou `unclear`.

## 8. Metadados coletados

Snapshots sanitizados registram:

- `kiosky-player.service`: active/enabled/SubState/NRestarts;
- contagens de processos: player, MPV e renderer;
- categorias de flags MPV observadas, sem cmdline bruta;
- TTY ativa;
- framebuffer: tamanho virtual, modos, bpp e rotate;
- conectores DRM: status, enabled, contagem de modos e amostra de modos;
- status publico allowlisted de `/tmp/kiosky-status.json`;
- propriedades MPV por IPC allowlisted quando houver socket temporario:
  `width`, `height`, `dwidth`, `dheight`, `video-params`,
  `video-out-params`, `osd-dimensions`, `fullscreen`, `pause` e `time-pos`.

Nao sao consultados path, filename, playlist, metadata, logs brutos ou config.

## 9. Evidencia

Diretorio padrao:

```text
/tmp/dadooh-c9-1-3-display-contract/
```

Arquivos:

```text
status.json
summary.txt
display-visual-contract.svg
snapshots/*.json
operation.json
human-validation.json
```

Permissoes:

- diretorios `0700`;
- arquivos `0600`.

## 10. Guardrails

C9.1.3 nao:

- altera config real;
- le `/data/config/config.json`;
- escreve `/data/config/config.json`;
- roda writer;
- usa `--enable-real-write`;
- altera flags MPV da config;
- altera player;
- altera launcher;
- altera repo `kiosky-player`;
- altera NetworkManager;
- executa `nmcli`;
- forca resolucao;
- escreve em `/data`;
- escreve em `/opt`;
- executa upgrade;
- libera producao.

Parada temporaria do player e inicio de MPV temporario so sao permitidos no
modo `--display` e apos confirmacao humana explicita. O runner tenta restaurar
o estado ativo do player ao final quando foi ele que parou o servico.

## 11. Privacidade

Evidencia sanitizada nao copia:

- conteudo de config;
- `api_url`;
- `api_key`;
- `environment_id` real;
- paths de midia;
- URLs;
- payload;
- logs brutos;
- cmdline bruta;
- IP, SSID, gateway ou hostname.

## 12. Resultado

Resultado desta implementacao:

- probe Python criado com `--self-test`;
- padrao SVG local criado em `/tmp`;
- runner remoto criado com modo `--prepare-only`;
- runner remoto bloqueia exibicao HDMI sem a frase de autorizacao exigida;
- modo `--display` usa MPV temporario via DRM/KMS e restaura o player quando
  ele foi parado pelo script;
- evidencia permanece em `/tmp` e passa por varredura de marcadores sensiveis;
- producao continua bloqueada.

Execucao autorizada `--display`:

- autorizacao humana textual recebida;
- player estava ativo antes da etapa;
- o runner parou temporariamente `kiosky-player.service`;
- MPV temporario foi iniciado para exibir o padrao visual por 90 segundos;
- MPV temporario foi encerrado ao final;
- restauracao foi tentada e aprovada;
- servico final `active/enabled`;
- `NRestarts=0`;
- player final=1;
- MPV final=1;
- renderer final=0;
- nenhum writer/config/rede/launcher/flags MPV permanentes foram alterados.

Validacao humana registrada:

- observacao livre corrigida pelo humano: o circulo parece oval e o quadrado
  parece retangulo;
- a margem amarela criada pelo padrao aparece sem corte;
- a dimensao maior do padrao coincide com a borda da TV;
- na outra direcao, a margem amarela fica menor que a borda da TV;
- a seta esta no topo da margem amarela, mas esse topo nao coincide com o topo
  fisico da tela;
- a midia restaurada continua esticada;
- `circle_answer=oval`;
- `square_answer=rectangle`;
- `border_answer=yes`;
- `cut_answer=no`;
- `top_arrow_answer=no`;
- `stretch_answer=unclear`;
- `player_restored_answer=same`.

Snapshot `display-active`:

- servico estava `inactive/dead`, esperado enquanto o player estava parado;
- MPV temporario=1;
- player=0;
- renderer=0;
- MPV temporario observado com `--vo=gpu`, `--gpu-context=drm`, `--ao=null`,
  fullscreen e socket IPC;
- sem `--geometry`;
- sem `--video-unscaled`;
- IPC do MPV temporario respondeu `success`;
- para o SVG estatico, dimensoes de video ficaram indisponiveis e OSD reportou
  `w=0`, `h=0`, portanto esses campos nao foram usados para inferir proporcao.

Smoke remoto `--prepare-only`:

- resultado `prepared`;
- padrao visual gerado;
- snapshot `prepare-read-only` coletado;
- servico `active/enabled`;
- `NRestarts=0`;
- player=1;
- MPV=1;
- renderer=0;
- TTY ativa `tty1`;
- framebuffer `fb0` observado em `1360,768`, 32 bpp, rotate `0`;
- modo framebuffer observado `U:1360x768p-0`;
- HDMI `card0-HDMI-A-1` observado `connected/enabled`;
- primeiro modo HDMI observado `1024x768`;
- amostra de modos HDMI: `1024x768`, `800x600`, `800x600`, `848x480`,
  `640x480`;
- IPC MPV nao foi consultado no prepare-only porque nenhum MPV temporario foi
  iniciado.

Resultado visual humano:

- o padrao confirma distorcao de proporcao: circulo virou oval e quadrado virou
  retangulo;
- a margem amarela nao foi cortada, mas o padrao nao ocupa/alinha igualmente os
  dois eixos da tela;
- a direcao exata do esticamento ficou inconclusiva no formulario normalizado;
- a midia restaurada continuou esticada, consistente com C9.1.2.

## 13. Proximos passos

Proximos passos recomendados:

- executar `--prepare-only` como smoke remoto seguro;
- se autorizado, executar `--display` e registrar respostas humanas;
- se circulo/quadrado/borda indicarem distorcao ou overscan, abrir frente
  futura de seletor/resolucao/tipo de tela;
- se o padrao estiver correto, seguir C9 com a ressalva documentada de midia e
  tratar a UX final do setup local separadamente;
- nao bloquear C9 indefinidamente por EDID/tela sem nova evidencia.
