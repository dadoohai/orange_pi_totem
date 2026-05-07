# C12.3 Boot Image-Lab Bloqueado por Firstboot/Sessao

Data: 2026-05-07

## Resultado observado

A imagem-lab C12.1 foi gravada e bootada em placa de teste. O produto apareceu
no HDMI com `Dadooh inicializando` e depois `config_missing`. O gatilho F10
abriu o wizard visual; o operador avancou por orientacao e Wi-Fi. Durante o
input de `environment_id`, o fluxo travou apos os primeiros caracteres.

O SSH ainda estava no first-login tecnico do Armbian. O first-login foi
concluido apenas para diagnostico, sem reiniciar antes da coleta.

## Achados sanitizados

- `totem-open-settings.service=failed`;
- resultado da unit: `signal`;
- status principal do processo: `SIGKILL`;
- nao havia `totem_setup_visual_wizard.py` rodando ao fim da coleta;
- nao havia MPV/player rodando ao fim da coleta;
- `/run/dadooh-settings/session.lock` ficou presente;
- `request.json` estava ausente;
- `kiosky-player.service=inactive/enabled`;
- root estava montado como ext4 `rw`;
- a coleta de journal de produto nao trouxe entradas uteis.

## Classificacao

- principal: `open_settings_session_stale`;
- secundaria: `firstboot_interference`;
- possivel: `tty/input_device_issue`;
- observado pelo humano: `wizard_input_freeze`;
- nao comprovado: `framebuffer_render_freeze`.

## Decisao

C12.3 fica bloqueado. Este boot nao valida read-only e nao deve ser tratado como
sucesso de imagem-lab. Tambem nao deve ser tratado como falha definitiva do
wizard isolado, porque o first-login tecnico do Armbian competiu com o fluxo de
produto.

## Correcoes C12.3.1

C12.3.1 endurece a proxima imagem-lab:

- `totem-open-settings.service` passa a ter `ExecStopPost` de cleanup;
- a sessao F10 ganha limpeza externa de `session.lock` e `request.json`;
- o trigger F10 passa a remover lock stale quando a unit nao esta ativa;
- sob falha, o cleanup tenta restaurar player ou tela `config_missing`;
- um gate de firstboot bloqueia servicos Dadooh enquanto
  `/root/.not_logged_in_yet` existir;
- o build passa a aceitar `C12_LAB_FIRSTBOOT_CONF` privado fora do Git para
  autoconfig de bancada;
- read-only validation passa a exigir assert explicito:
  `read_only_enabled`, `overlay_active`, `root_write_blocked`, `/data`, `/tmp`
  e `/run` gravaveis.

## Proximo passo

Rebuild da imagem-lab como C12.1.2, reflash como C12.2.1 e nova validacao como
C12.3.2. Nao provisionar config real, nao chamar writer e nao avancar para
C12.4 antes desses gates.

## Atualizacao C12.1.2

O rebuild C12.1.2 foi concluido em 2026-05-07. A nova imagem inclui os fixes de
sessao/firstboot e passa a ser o artefato correto para C12.2.1. C12.3 segue
bloqueado para a imagem antiga; a revalidacao deve acontecer como C12.3.2 apos
reflash controlado.
