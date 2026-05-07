# C12.3 Image-Lab Freeze Diagnose

Data: 2026-05-07

## Contexto

A image-lab C12.1 foi gravada em cartao de teste e inicializou na placa de
teste com tela Dadooh e estado `config_missing`. O F10 abriu o wizard visual.
O operador configurou orientacao e Wi-Fi, mas o fluxo parou durante a digitacao
do identificador de ambiente.

SSH estava bloqueado por first-login tecnico do Armbian. O first-login foi
concluido apenas para diagnostico, sem reboot e sem provisionar config real.

## Artefatos Coletados na Placa

- `/tmp/dadooh-c12-3-freeze-diagnose/summary.txt`
- `/tmp/dadooh-c12-3-freeze-diagnose/product-journal-tail.txt`

Hashes observados:

- summary_sha256:
  `3b3a6c7bc6257a0c0cc114ed06d0b03cffd587700be74f22a571c81ca769b366`
- product_journal_tail_sha256:
  `19c4e28b2f54ea8f217db4e622b0a5c758efa7b77ce2dc0394b6d159568c0b2e`

## Classificacao

Classificacao principal:

- `open_settings_session_stale`

Classificacoes secundarias:

- `firstboot_interference`
- `tty/input_device_issue` como possibilidade a investigar
- `wizard_input_freeze` observado pelo humano, mas sem processo de wizard ainda
  ativo no momento da coleta

Nao confirmado:

- `framebuffer_render_freeze`

## Achados Sanitizados

- root filesystem ainda estava `ext4 rw`;
- `read_only_enabled=false` por observacao de mount;
- `kiosky-player.service` final: `inactive/enabled`;
- `totem-settings-trigger.service`: `active/enabled`;
- `totem-open-settings.service`: `failed/static`;
- `totem-open-settings.service Result=signal`;
- `ExecMainStatus=9`;
- `player_process_count=0`;
- `mpv_process_count=0`;
- `setup_process_count=0`;
- `session.lock present=true`;
- `request.json present=false`;
- failed_units_count: `2`;
- `product-journal-tail.txt` nao trouxe entradas uteis.

## Interpretacao

O estado final nao mostrou um wizard ainda rodando e congelado. A sessao de
abertura de configuracoes morreu por sinal e deixou lock/estado residual,
mantendo o player parado. Isso classifica a falha operacional como
`open_settings_session_stale`.

O first-login tecnico do Armbian pendente e um fator contaminante real da
image-lab. A imagem ainda nao tem autoconfig/firstrun de produto para eliminar
o first-login tecnico antes da experiencia Dadooh.

## Pendencia C12.x

Criar uma frente de autoconfig/firstrun da imagem:

- eliminar first-login tecnico visivel/necessario para o operador;
- configurar credenciais tecnicas de bancada por mecanismo controlado ou
  bloquear SSH ate procedimento explicito;
- garantir que o wizard nao concorra com fluxo Linux de first-login;
- revalidar F10 -> wizard depois dessa correcao.

## Guardrails

- reboot_executed: false;
- writer_called: false;
- real_config_written: false;
- config_real_published: false;
- wifi_changed_after_freeze: false;
- read_only_changed: false;
- secrets_published: false.
