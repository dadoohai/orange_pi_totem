# C12.3.5 - Boot + Read-only + Wizard Apply Classification

Data: 2026-05-07

## Objetivo

Validar a imagem-lab C12.1.8 em placa e separar tres pontos:

- boot/firstboot da imagem;
- ativacao de root read-only/overlay;
- comportamento do wizard ao concluir sem valores privados do player.

Nenhum writer real foi chamado, nenhuma config real foi provisionada, Wi-Fi e
NetworkManager nao foram alterados e nenhum secret foi publicado.

## Resultado

A imagem C12.1.8 bootou e ficou acessivel por SSH em bancada:

- `boot_success=true`;
- `ssh_available=true`;
- `lab_bootstrap_state=complete`;
- `firstboot_marker_present=false`;
- `public_state=config_missing`;
- `config_real_present=false`.

O estado `config_missing` e esperado para a imagem-lab, porque ela nao embute
`api_url`, `api_key` ou config real do player.

## Read-only

O read-only ainda nao ativou:

- `overlayroot.conf` esta presente com `overlayroot=tmpfs`;
- boot script em `/boot` referencia `uInitrd`;
- `initrd.img` contem hook `overlayroot`;
- `initrd.img` contem modulo `overlayfs`;
- `initrd.img` contem marker C12.1.8;
- `uInitrd` existe e nao esta vazio;
- `read_only_enabled=false`;
- `overlay_active=false`;
- `root_fstype=ext4`;
- `root_write_blocked=false`;
- `/data`, `/tmp` e `/run` gravaveis: `true`;
- `journald_volatile=true`.

Classificacao:

```text
IMAGE_LAB_READ_ONLY_NOT_ACTIVE
```

Isso bloqueia C12.4.

## Wizard

Ao concluir o wizard na imagem-lab:

- `candidate_generated=true`;
- `candidate_files_count=1`;
- `writer_called=false`;
- `real_config_written=false`;
- `C5.1 allow-mock=true`;
- `C5.1 real-dry-run=false/not_run`;
- `final_state=config_missing`.

Classificacao:

```text
CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES
UX_AMBIGUOUS_CANDIDATE_ONLY
```

Voltar para `config_missing` e esperado enquanto a imagem-lab nao tiver valores
privados e enquanto o writer real permanecer bloqueado. A pendencia de produto e
de UX: o operador pode entender que "concluir" aplicou a configuracao, quando na
verdade apenas preparou a candidata.

## Servicos

Servicos principais:

- `kiosky-player.service`: active/enabled;
- `totem-settings-trigger.service`: active/enabled;
- `totem-open-settings.service`: inactive/static, result success;
- `totem-firstboot-gate.service`: inactive/enabled, result success;
- `totem-lab-firstboot-autoconfig.service`: inactive/enabled, result success.

`systemctl_failed_count=1`, categorizado como:

```text
console_setup
```

Esse item nao explica o retorno para `config_missing` e nao foi tratado como
blocker principal nesta rodada, mas permanece como pendencia secundaria da
imagem/base.

## Guardrails

Nao foi feito:

- writer real;
- escrita de `/data/config/config.json`;
- leitura de config real;
- provisionamento de `api_url`/`api_key`;
- alteracao de Wi-Fi/NetworkManager;
- instalacao de pacotes;
- reboot;
- poweroff;
- corte seco;
- publicacao de secrets ou logs brutos.

## Decisao

C12.4 nao pode comecar ainda.

O retorno para `config_missing` nao e bug de writer nesta rodada; e o
comportamento esperado de `candidate-only` sem valores privados, com UX ainda
ambigua.

O blocker real continua sendo a nao ativacao do read-only/overlay. O proximo
passo deve diagnosticar por que o initramfs valido com overlayroot e marker
C12.1.8 ainda resulta em root `ext4 rw` no boot.
