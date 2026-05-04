# C10.0 - Wizard Visual -> Writer Real Controlado

Status: implementado e validado em bancada com confirmacao humana explicita.

Data: 2026-05-04

## Objetivo

Ligar o wizard visual local C9.9.1 ao writer real C6 ja validado, permitindo
gerar uma candidata privada, validar C5.1 `real-dry-run`, escrever
`/data/config/config.json` com backup/permissoes e iniciar o player de forma
controlada.

## Implementado

- `scripts/board/totem_visual_setup_writer_handoff.py`;
- `scripts/remote/run_c10_0_visual_setup_writer_real.sh`;
- handoff privado sob `/tmp`, com diretorio `0700` e arquivos `0600`;
- injecao de endpoint/credencial privada a partir de arquivo restrito sob
  `/tmp`;
- preservacao de `environment_id` e `rotation_deg` vindos do wizard visual;
- C5.1 `real-dry-run` antes de qualquer escrita real;
- chamada do writer real existente, somente com confirmacao explicita;
- restauracao do `kiosky-player.service` ao final do runner;
- evidencia/status sanitizados.

## Validado em Bancada

- `--prepare-only` passou;
- `--preflight` passou sem ler/escrever config real;
- `--run-dry-run` passou sem tocar `/data`;
- `--run-real-write-start` passou com fonte privada autorizada a partir da
  config ativa;
- candidata privada passou C5.1 `real-dry-run`;
- writer real retornou `passed`;
- backup foi criado;
- config ativa ficou `root:totem` `0640`;
- usuario `totem` le e nao escreve;
- servico final `active/enabled`;
- `NRestarts=0`;
- `public_state=player_running`;
- playback `playing`;
- player/MPV ativos e setup/renderer ausentes.

## Fluxo

1. O runner prepara os scripts em `/tmp`.
2. O wizard visual coleta ambiente e tela na HDMI, sem shell visivel.
3. O handoff C10 gera uma candidata privada temporaria.
4. A candidata privada passa C5.1 `real-dry-run`.
5. Com a frase `CONFIRMO ESCRITA REAL CONFIG C10.0`, o runner para o servico.
6. O writer C6 escreve somente `/data/config/config.json`, cria backup e aplica
   `root:totem` `0640`.
7. Temporarios privados sao removidos.
8. O servico e iniciado e o runner aguarda `player_running`.

## Fonte Privada

O operador nao digita token/API no wizard e esses valores nao passam por chat
ou argumento de linha de comando. A fonte aceita nesta rodada e um arquivo
privado aprovado sob `/tmp`, com pai `0700`, arquivo `0600` e sem symlink.
Opcionalmente, o runner pode extrair essas categorias da config ativa ja
existente, mas somente com a frase adicional
`CONFIRMO USAR CONFIG ATIVA COMO FONTE PRIVADA C10.0`; essa leitura nao publica
conteudo e grava apenas um arquivo temporario restrito sob `/tmp`.

Os valores privados nao aparecem em stdout persistente, status, summary,
documentacao ou evidencia. A candidata privada e artefato temporario e nao deve
ser copiada para Git.

## Protecoes

- writer real bloqueado sem confirmacao humana explicita;
- destino real exato: `/data/config/config.json`;
- backup real restrito: `/data/config/backups`;
- config ativa esperada: `root:totem` `0640`;
- usuario `totem` deve ler e nao escrever;
- rollback do writer permanece responsabilidade do writer C6;
- Wi-Fi, hotspot, portal, backend/login e repo `kiosky-player` ficam fora.

## Como Validar

```text
scripts/remote/run_c10_0_visual_setup_writer_real.sh <host> --prepare-only
scripts/remote/run_c10_0_visual_setup_writer_real.sh <host> --preflight
scripts/remote/run_c10_0_visual_setup_writer_real.sh <host> --run-dry-run
scripts/remote/run_c10_0_visual_setup_writer_real.sh <host> --run-real-write-start
```

`--run-real-write-start` so deve ser executado com humano na HDMI/teclado e a
frase exata de confirmacao.

Quando a fonte privada for a config ativa ja existente, usar tambem:

```text
--private-values-from-active-config
```

## Fora do Escopo

- hotspot;
- portal;
- backend/login;
- QR funcional;
- reboot/autoboot;
- alteracao do Wi-Fi;
- alteracao do `kiosky-player`;
- publicacao da config real, backup ou candidata privada.

## Proximo Passo

C10.1 deve validar reboot/autoboot controlado com Wi-Fi persistente, config real
e wizard visual ja integrados.
