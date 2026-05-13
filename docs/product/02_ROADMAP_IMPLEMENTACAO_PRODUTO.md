# Roadmap de implementacao produto/UX

Status: proposta incremental. Nao implementa mudancas.

Data: 2026-05-01

Atualizacao C11.3.1: 2026-05-06. C11.3.1 confirmou que o caminho read-only
deve continuar usando o mecanismo oficial do Armbian e que o prerequisito exato
e o pacote `overlayroot`. O dry-run de instalacao na placa dev foi seguro, sem
upgrades/remocoes e sem tocar pacotes kernel/DTB/U-Boot/BSP; depois de
confirmacao humana, o pacote foi instalado na dev sem habilitar read-only. O
instalador passa a declarar `--install-readonly-prereqs` e a imagem final C12
deve incluir esse pacote antes do enablement read-only.

Atualizacao C11.3.4: 2026-05-06. C11.3.4 decidiu o mecanismo read-only apos o
laboratorio C11.3.3: `overlayroot` instalado nao e suficiente nesta base
provisionada. A falha fica classificada como
`initramfs_log_driver_lookup_failed=true`, com hook initramfs e modulo `overlay`
presentes. C11.4 segue bloqueado. O proximo passo permitido e C12.0-prep para
validar uma imagem/base com overlay integrado no build, nao nova tentativa direta
na dev funcional.

Atualizacao C12.0-prep: 2026-05-06. C12.0-prep transformou a decisao ADR-0011
em plano de imagem-lab: nenhuma placa foi tocada, nenhuma imagem foi gerada e
nenhum cartao foi gravado. Foi criado `releases/image-lab-readonly/manifest.md`
e um runner/checklist local para C12.1. A proxima acao correta e preparar o
ambiente de build e recuperar/clonar Armbian Build v25.11; cartao de teste vem
somente depois da imagem-lab e checksums.

Atualizacao C12.1: 2026-05-06. C12.1 gerou a primeira imagem-lab read-only
integrada ao build, sem tocar placas e sem gravar cartao. A imagem inclui
`overlayroot`, executa `update-initramfs` depois da instalacao do pacote e
produziu checksum, build log, package manifest e integration manifest.
`card_written=false`, `boards_touched=false`, `final_image=false` e
`ready_for_c12_2_board_validation=true`.

Atualizacao C12.1.1: 2026-05-07. C12.1.1 preservou e revalidou o artefato
C12.1, registrando checksum ok e manifests presentes. O cartao da placa dev
teve incidente fisico de fumaca/aquecimento e boot anormal por `/dev/mtdblock4`;
fica tratado como midia/hardware nao confiavel, nao como bug de software ate
prova contraria. C12.2 deve usar cartao novo/descartavel e placa teste, sem
depender da dev.

Atualizacao C12.2: 2026-05-07. C12.2 padroniza a gravacao da imagem-lab via
Armbian Imager no Windows: o artefato C12.1 foi revalidado por SHA256, foi
criado runner/checklist local para registrar flash manual e a documentacao
separa gravacao de boot validation. Depois do boot inicial C12.3,
`card_written=true`, `boards_touched=true` e a validacao read-only segue
bloqueada por firstrun tecnico e sessao F10 stale.

Atualizacao C12.3 diagnostico inicial: 2026-05-07. A image-lab bootou em
`config_missing`, F10 abriu o wizard e o operador avancou por orientacao/Wi-Fi,
mas o fluxo parou durante input de ambiente. A coleta sem reboot classificou o
estado como `open_settings_session_stale`, com `totem-open-settings.service`
falhando por sinal e `session.lock` residual; `framebuffer_render_freeze` nao
foi comprovado. A imagem-lab ainda exige first-login tecnico Armbian, que passa
a ser pendencia C12.x de autoconfig/firstrun, nao bug isolado do wizard.

Atualizacao C12.3.1: 2026-05-07. C12.3 fica oficialmente bloqueado por
`open_settings_session_stale` + `firstboot_interference`; nao houve validacao
read-only. A rodada adiciona cleanup externo para `totem-open-settings.service`,
limpeza de lock stale no trigger F10, gate de firstboot para segurar os servicos
Dadooh enquanto `/root/.not_logged_in_yet` existir, template privado de
`firstboot.conf` fora do Git e assert explicito de read-only para a proxima
validacao. Proximos passos: rebuild C12.1.2, reflash C12.2.1 e revalidacao
C12.3.2 antes de qualquer C12.4.

Atualizacao C12.1.2: 2026-05-07. A imagem-lab foi reconstruida com os fixes
C12.3.1 incorporados, sem tocar placas e sem gravar cartao. A nova imagem e
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img`,
com SHA256 `a398399c139c3fee1b05860b216db7facfddd0ae1a57f681b229228390b7abd9`.
O manifest marca a imagem C12.1 como superseded e libera C12.2.1 para gravacao
em cartao novo/descartavel; C12.3.2 deve validar firstboot gate, F10 e
read-only assertion.

Atualizacao C12.1.3: 2026-05-07. A tentativa C12.3.2 com a imagem C12.1.2
ficou bloqueada por `firstboot_bootstrap_missing_or_invalid`: tela preta, F10
aparecendo como escape sequence no console cru, sem Wi-Fi, sem SSH e sem UI
Dadooh. A rodada escolhe a estrategia `lab_autoconfig_required`: a proxima
imagem-lab bootavel deve ser C12.1.4, construida com
`C12_LAB_FIRSTBOOT_CONF` privado fora do Git e
`C12_REQUIRE_LAB_FIRSTBOOT_CONF=1`. Imagens sem esse autoconfig podem existir
para auditoria, mas nao podem ser marcadas como prontas para boot validation.

Atualizacao C12.1.4: 2026-05-07. O `firstboot.conf` privado foi validado sem
publicar valores e passou nos criterios de seguranca/campos/rede. Com Docker
novamente disponivel, a imagem C12.1.4 foi gerada com autoconfig privado de
laboratorio, `overlayroot`, firstboot gate, cleanup F10 e assert explicito de
read-only. SHA256:
`405d4891e62d018862008f3bfdf00e02123b551351655147ec7448b803ccca14`.
Nenhuma placa foi tocada, nenhum cartao foi gravado e nenhum secret foi
publicado. C12.2.2 pode gravar novo cartao de teste com esta imagem.

Atualizacao C12.3.3/C12.1.5: 2026-05-07. A C12.1.4 foi bootada e mostrou o
fallback Dadooh `Bootstrap tecnico pendente`, provando que a imagem nao ficou
muda, mas que o autoconfig lab nao foi efetivo. A inspecao offline mostrou que
o arquivo privado existia no rootfs, porem faltava bootstrap autonomo antes do
`totem-firstboot-gate`. C12.1.5 adicionou inspecao real do rootfs e
`totem-lab-firstboot-autoconfig.service`; C12.1.6 foi gerada com SHA256
`b64808a7ce23d7c19422c816ca558605d39b495019ecac0bb480345bff711a67`,
`rootfs_lab_bootstrap_proven=true` e `ready_for_card_write_by_rootfs=true`.
Nenhuma placa foi tocada e nenhum cartao foi gravado durante a correcao.

Atualizacao C12.3.4: 2026-05-07. A C12.1.6 bootou em placa, SSH ficou
acessivel e o bootstrap lab concluiu. A imagem voltou corretamente para
`config_missing` porque nao embute config real; o wizard gerou candidata em
modo `candidate-only`, sem writer e sem escrita real. Porem o objetivo principal
da image-lab nao passou: apesar de `overlayroot="tmpfs"` e hooks presentes, o
root bootou como `ext4 rw`, com `overlay_active=false` e
`read_only_enabled=false`. C12.4 fica bloqueado; o proximo passo recomendado e
C12.1.7 para diagnosticar overlayroot configurado no rootfs, mas inativo no
boot.

Atualizacao C12.1.7: 2026-05-07. O diagnostico comparou a placa C12.1.6
bootada com o artefato offline sem alterar placa, config, Wi-Fi ou servicos. A
causa provavel foi classificada como `UINITRD_NOT_UPDATED`: `initrd.img` contem
o hook do overlayroot e o modulo `overlay`, mas o boot script carrega `uInitrd`
e o `uInitrd` no artefato da imagem estava vazio. C12.4 segue bloqueado; C12.1.8
deve reconstruir a imagem-lab garantindo `uInitrd` valido antes do primeiro boot
ou ajustando o boot para usar o initramfs correto.

Atualizacao C12.1.8: 2026-05-07. A imagem-lab foi reconstruida com validacao
do initramfs efetivo: o build instala um marker seguro no initramfs, gera
`uInitrd` pelo fluxo Armbian e a inspecao offline segue o symlink, extrai o
payload U-Boot e compara com `initrd.img`. A imagem
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-8_minimal.img`
tem SHA256 `7fbc9a0abc39d39b5fc0803d5f935baaf1795bddc6707e18dbf1d7c804ad830d`,
`uinitrd_nonempty=true`, `uinitrd_payload_matches_initrd_img=true` e
`effective_boot_initramfs_valid=true`. Nenhuma placa foi tocada e nenhum cartao
foi gravado; C12.2.4 deve gravar essa imagem antes da proxima validacao em
placa.

Atualizacao C12.3.5: 2026-05-07. A C12.1.8 bootou em bancada, SSH ficou
acessivel e o firstboot lab concluiu. O wizard gerou candidata, nao chamou
writer e voltou para `config_missing`, classificado como
`CANDIDATE_ONLY_EXPECTED_WITHOUT_PRIVATE_VALUES`, com pendencia
`UX_AMBIGUOUS_CANDIDATE_ONLY`. O read-only ainda nao ativou:
`read_only_enabled=false`, `overlay_active=false`, `root_fstype=ext4` e
`root_write_blocked=false`, apesar de o initrd conter hook overlayroot, modulo
overlayfs e marker C12.1.8, e de o boot script em `/boot` referenciar
`uInitrd`. C12.4 segue bloqueado.

Atualizacao C12.3.6: 2026-05-08. A placa C12.1.8 foi usada como laboratorio
runtime descartavel para evitar rebuild por hipotese. H1 adicionou
`overlayroot=tmpfs` ao `extraargs` e provou que o hook passa a rodar quando o
parametro chega ao cmdline. H2 regenerou `initramfs` e `uInitrd`, mas o root
continua `ext4 rw`. A causa ficou classificada como
`OVERLAY_DRIVER_UNAVAILABLE_IN_INITRAMFS_RUNTIME`: no initramfs, o script do
`overlayroot` carrega o modulo, mas `overlay` nao aparece em
`/proc/filesystems` naquele momento. C12.1.9 deve corrigir a imagem/base para
precarregar/registrar o driver `overlay` no initramfs e manter
`overlayroot=tmpfs` no boot args. C12.4 segue bloqueado.

Atualizacao C12.3.7: 2026-05-08. A correcao minima foi testada diretamente na
placa lab antes de novo build. `H1_FORCE_MODULE` adicionou `overlay` a
`/etc/initramfs-tools/modules`; `H2_FORCE_LOAD_HOOK` adicionou hook `init-top`
para executar `modprobe overlay` antes do `overlayroot`. Ambas as hipoteses
entraram no initramfs/uInitrd e rebootaram com SSH voltando, mas
`read_only_enabled=false`, `overlay_active=false` e `root_write_blocked=false`
persistem. O mecanismo segue bloqueado; C12.1.9 nao deve ser apenas rebuild com
preload simples de modulo, e C12.4 segue bloqueado.

Atualizacao C12.3.8: 2026-05-08. C12.3.8 foi apenas decision gate read-only,
sem alterar placa ou repetir enable. A inspecao confirmou que `uInitrd` efetivo
contem `overlayroot`, `overlay.ko`, `modules.dep`, `modules.alias`, `modprobe`
e o hook C12.3.7; tambem confirmou que `overlayroot=tmpfs` chega ao boot e que
o hook roda. A causa foi refinada para
`OVERLAY_MODULE_PRESENT_BUT_NOT_REGISTERED_IN_INITRAMFS_RUNTIME`: o driver nao
aparece em `/proc/filesystems` no runtime do initramfs, entao o mount overlay
nem e tentado. Proximo passo permitido: C12.3.9 investigar carregamento/registro
do driver ou compatibilidade kernel/initramfs. C12.1.9 e C12.4 seguem
bloqueados.

Atualizacao C12.3.9: 2026-05-08. C12.3.9 instalou hook temporario de
diagnostico no initramfs com backup, reboot controlado e rollback. O SSH voltou
e o hook foi removido depois da coleta. O diagnostico mostrou `/proc` montado,
`modprobe`/`insmod` presentes, `modules.dep` presente e `modprobe overlay`
retornando zero, mas `overlay.ko` nao foi encontrado no caminho esperado do
runtime do initramfs e `overlay` continuou ausente em `/proc/filesystems`. A
causa passa a ser `OVERLAY_MODULE_PATH_INVALID`. C12.1.9 pode iniciar como
rebuild focado em corrigir layout/caminho de modulos no initramfs efetivo; C12.4
segue bloqueado ate read-only real ser validado.

Atualizacao C12.1.9: 2026-05-08. A imagem-lab foi reconstruida com
`overlayroot=tmpfs` nos boot args, hook `init-top` para carregar `overlay` e
fallback por `insmod` usando o caminho efetivo
`/lib/modules/<kernel>/kernel/fs/overlayfs`. Como o initramfs e usr-merged,
`/lib` aponta para `usr/lib`; a validacao offline agora prova esse caminho
resolvido, `modules.dep` coerente e
`effective_boot_initramfs_overlay_resolvable=true`. A imagem C12.1.9 tem SHA256
`f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c`. Nenhuma
placa foi tocada e nenhum cartao foi gravado. C12.2.5 pode gravar novo cartao;
C12.4 segue bloqueado ate boot provar read-only ativo.

Atualizacao C12.3.10: 2026-05-08. A C12.1.9 foi gravada e bootada na placa lab.
O SHA real foi confirmado como
`f581ffab591462b1daa60a648f0ed0f8c2831deff9004f9ff16cdaa46fd11e6c`, o SSH
ficou disponivel, o firstboot lab concluiu e o produto ficou em
`config_missing`, esperado sem config real. O read-only ainda nao ativou:
`read_only_enabled=false`, `overlay_active=false`, `root_write_blocked=false` e
`root_fstype=ext4`. A causa atual foi refinada para
`INSMOD_FALLBACK_FAILED`: o caminho efetivo do modulo foi encontrado e o
fallback `insmod` foi tentado, mas retornou nonzero no initramfs. C12.4 continua
bloqueado; proximo passo recomendado: C12.3.11 diagnosticar a falha do `insmod`
sem logs brutos.

Atualizacao C12.3.11: 2026-05-08. C12.3.11 instalou hook temporario de
diagnostico no initramfs com backup, reboot controlado e rollback. O SSH voltou
e o hook foi removido ao final. A classificacao foi refinada para
`OVERLAY_MODULE_PATH_MISMATCH`: no runtime do initramfs, `overlay.ko` nao ficou
resolvivel no caminho efetivo usado pelo hook, entao o `insmod` nao foi tentado
nesta coleta. C12.4 continua bloqueado; o proximo passo e
C12.1.10 reconstruir a imagem com path efetivo de modulo corrigido para o
layout usr-merged do initramfs.

Atualizacao C12.1.10: 2026-05-08. A imagem-lab foi reconstruida com resolucao
dinamica do caminho do modulo `overlay`: o hook tenta `/lib/modules`,
`/usr/lib/modules`, deriva caminho por `modules.dep` e faz fallback por busca,
sem publicar logs brutos. A validacao offline agora exige
`overlay_module_discoverable_in_initramfs=true` e
`fallback_hook_dynamic_path=true`, reconciliando a diferenca entre C12.3.10 e
C12.3.11. A imagem C12.1.10 tem SHA256
`c7e3e2af5e2cfa52db0a1cb73141b941a239471940020953d6debfbb0133e4b2`, nao tocou
placas e nao gravou cartao. C12.2.6 pode gravar a nova imagem; C12.4 segue
bloqueado ate boot validar read-only real.

Atualizacao C12.3.12: 2026-05-08. A imagem C12.1.10 foi gravada e bootada na
placa lab, com SSH disponivel e firstboot tecnico concluido. A observacao
humana foi tela preta. O read-only ainda nao ativou:
`read_only_enabled=false`, `overlay_active=false`, `root_write_blocked=false` e
root `ext4`. A correcao dinamica de path entrou no boot:
`overlay_module_path_found=true`, `overlay_module_path_source=static_fallback`,
`modprobe_rc=0`, mas `insmod_rc=1`. A nova classificacao e
`DYNAMIC_PATH_FOUND_INSMOD_FAILED`. Separadamente, a tela preta ficou
classificada como `CONFIG_MISSING_VISUAL_BLACK_SCREEN_WITH_RENDERER_ACTIVE`,
pois o SVG publico existe e renderer/MPV estao ativos. C12.4 continua
bloqueado; proximo passo recomendado: C12.3.13 diagnosticar o erro do `insmod`
com o path dinamico encontrado.

Atualizacao C6.5: 2026-05-02. C6.3A e C6.4 estao concluidos como
desenvolvimento; C6.5 consolida o marco config real + `player_running`; testes
longos foram movidos para fila de homologacao separada.

Atualizacao C7.0: 2026-05-02. C7 passa a iniciar por diagnostico/status
sanitizado do appliance, com contrato e snapshot local/offline. C7.0 nao toca
placa, nao le config real, nao executa comandos operacionais e nao substitui
homologacao longa.

Atualizacao C8 produto V1: 2026-05-03. C8 passa a organizar a visao Produto V1
de operacao, onboarding e recuperacao para operador nao tecnico. Esta
atualizacao e documental: nao implementa operacao real, nao toca placa, nao
altera rede/config/player e nao substitui homologacao.

Atualizacao C8.1: 2026-05-03. C8.1 entrega setup minimo funcional/mock local
sem Wi-Fi real, com servidor HTTP local, prototipo estatico, candidata em
`/tmp`, status/summary sanitizados e smoke seguro opcional na placa usando
somente `/tmp`. Nao escreve config real, nao altera rede, nao chama backend,
nao inicia player e nao substitui homologacao.

Atualizacao C8.1.1: 2026-05-03. C8.1.1 consolida o handoff entre setup minimo
e contrato C5.1: candidata passa em `allow-mock`, falha em `real-dry-run`
enquanto usa placeholders e grava rotacao em `rotation_deg`. Continua somente
em `/tmp`, sem writer real, sem rede e sem player.

Atualizacao C8.2: 2026-05-03. C8.2 troca o caminho principal de ambiente para
uma lista mock/local com nomes publicos e mantem o campo manual como modo
avancado/de bancada. A candidata continua validada por C5.1, somente em `/tmp`,
sem backend, sem rede real, sem writer real e sem player.

Atualizacao C8.3: 2026-05-03. C8.3 troca a escolha principal de rotacao de
graus tecnicos para opcoes amigaveis de orientacao, com preview simples. A
candidata continua gravando `rotation_deg`, somente em `/tmp`, sem aplicar
rotacao real e sem tocar MPV, player, rede, servicos, `/data` ou `/opt`.

Atualizacao C8.4.0: 2026-05-03. C8.4.0 cria a manutencao minima mock/local
como area secundaria do setup, com `restart_player_mock`,
`reset_config_mock`, confirmacao forte para reset e artefatos sanitizados em
`/tmp`. Ainda nao executa reset real, nao chama `systemctl`, nao reinicia
player/MPV, nao altera rede e nao toca `/data` ou `/opt`.

Atualizacao C8.5.0: 2026-05-03. C8.5.0 cria o preflight local/offline de
integracao setup -> writer/config: le a candidata C8 em `/tmp`, confirma
C5.1 `allow-mock`, confirma `real-dry-run` falhando por placeholders e gera
relatorio sanitizado de lacunas para futura config real. Nao chama writer em
modo real, nao usa secrets, nao toca `/data` ou `/opt` e nao altera servico,
player, MPV, rede ou backend.

Atualizacao C8.5.1: 2026-05-03. C8.5.1 define a origem futura aprovada de
valores privados e gera uma candidata real-sintetica somente em `/tmp`, com
valores nao reais gerados localmente. A candidata real-sintetica passa C5.1
`real-dry-run`, mas writer real continua bloqueado; nao usa secrets reais, nao
toca `/data` ou `/opt` e nao altera servico, player, MPV, rede ou backend.

Atualizacao C8.5.2: 2026-05-03. C8.5.2 revisa o contrato minimo e reclassifica
`station_id` como opcional, nao operacional e futuro. `api_url` e `api_key`
continuam valores privados importantes, `environment_id` continua necessario,
e `station_id` deixa de bloquear C5.1 `real-dry-run`. A alteracao permanece em
`/tmp`, sem writer real, sem config real, sem `/data`, sem `/opt`, sem player e
sem rede.

Atualizacao C8.6-preflight: 2026-05-03. C8.6 define o handoff real controlado
sem escrita real: le valores privados aprovados somente de arquivo restrito sob
`/tmp`, gera candidata privada temporaria, valida C5.1 `real-dry-run`, observa
pre-condicoes de servico/player sem alterar estado e registra pontos de aborto.
Writer real continua bloqueado, `--enable-real-write` nao e usado, `/data` e
`/opt` nao sao tocados e nenhum valor privado e publicado.

Atualizacao C8.6.1: 2026-05-03. C8.6.1 adiciona limpeza explicita dos arquivos
privados temporarios do preflight: remove `candidate-private.json` e
`private-values.json`, preserva apenas status/summary sanitizados, registra
cleanup executado e mantem writer real bloqueado. Continua somente em `/tmp`,
sem `/data`, `/opt`, servico, player, MPV, rede ou backend.

Atualizacao C8.7: 2026-05-03. C8.7 cria o gate operacional final antes da
primeira escrita real integrada: inspeciona a placa em modo read-only, confirma
guardrails do writer C6, verifica o fluxo C8.6/C8.6.1, gera checklist go/no-go
e documenta o roteiro exato da rodada real futura. Ainda nao usa
`--enable-real-write`, nao escreve em `/data` ou `/opt`, nao para/inicia
servico, nao inicia player e nao publica valores privados.

Atualizacao C8.8: 2026-05-03. C8.8 executa a primeira escrita real integrada
setup -> writer/config em desenvolvimento: gera candidata C8 em `/tmp`, aplica
valores privados aprovados por arquivo restrito, valida C5.1 `real-dry-run`,
para `kiosky-player.service`, escreve `/data/config/config.json` via writer C6
com flags reais explicitas, cria backup, limpa temporarios privados e roda gate
read-only final. O servico permanece parado ao final; player/MPV/rede/backend
nao sao iniciados e producao continua bloqueada.

Atualizacao C8.9: 2026-05-03. C8.9 executa o start controlado pos-escrita real:
inicia `kiosky-player.service` sem alterar config e sem rodar writer, observa
status publico e processos por categorias, confirma `player_running`, playback
`playing`, `kiosk.py` e MPV ativos, renderer ausente junto do player e
`NRestarts=0` em smoke curto de 120 segundos. Evidencia permanece sanitizada em
`/tmp`; producao continua bloqueada.

Atualizacao C8.10: 2026-05-03. C8.10 executa reboot/autoboot controlado com a
config real escrita pelo fluxo C8: confirma pre-check `player_running`, pede
autorizacao humana explicita, reinicia a placa por reboot controlado, aguarda
SSH voltar, observa servico/status/player/MPV/renderer e confirma retorno para
`player_running` com playback `playing`, MPV ativo, renderer inativo e
`NRestarts=0`. Validacao visual humana confirmou midia visivel apos boot.
Config, backups, writer, rede/Wi-Fi e repo do player nao foram alterados;
producao continua bloqueada.

Correcao pos-C8.10: observacao de 30-60 minutos com config real pertence a fila
de homologacao paralela, nao a uma etapa C8.11 de desenvolvimento. A proxima
frente de desenvolvimento passa a ser C9.0: acesso temporario ao setup pela
rede local existente, sem Wi-Fi real, hotspot, portal definitivo, writer ou
alteracao da config real.

Atualizacao C9.0: 2026-05-03. C9.0 executa o acesso temporario ao setup C8 pela
rede local de bancada existente: sobe o servidor em `/tmp`, expoe porta
temporaria para navegador, gera candidata de teste apenas em `/tmp`, coleta
evidencia sanitizada e encerra o servidor ao final. Nao implementa Wi-Fi real,
hotspot, portal definitivo, NetworkManager, `nmcli`, writer, config real ou
alteracao do player; `kiosky-player.service` permanece ativo e producao
continua bloqueada.

Atualizacao C9.1: 2026-05-03. C9.1 corrige a premissa de produto: setup pela
propria tela HDMI do totem e obrigatorio, enquanto rede local/QR/navegador sao
caminhos auxiliares. A etapa cria um wizard local controlado por teclado USB,
sem Chromium, desktop, compositor ou shell livre, que seleciona ambiente
mock/local, orientacao, revisao e gera candidata apenas em `/tmp` validada por
C5.1. Nao escreve config real, nao roda writer, nao toca `/data`, `/opt`,
servico, player, MPV, rede ou Wi-Fi.

Atualizacao C9.1.1: 2026-05-04. C9.1.1 executa a validacao humana do wizard
local na propria placa, com HDMI e teclado USB. O runner remoto copia scripts
para `/tmp`, roda self-tests, observa console/servico/processos por categorias,
abre o wizard em TTY local com parada temporaria do player somente apos
autorizacao humana explicita e restaura o estado ao final. Resultado: passou
tecnicamente, gerou candidata em `/tmp`, C5.1 `allow-mock` passou,
`real-dry-run` falhou como esperado e o servico voltou `active/enabled` com
`NRestarts=0`, player=1, MPV=1 e renderer=0. Ressalvas: UX ainda parece
terminal Linux/Python interativo, nao esta aprovada para operador final, e foi
registrado warning visual de midia aparentemente mais esticada apos
restauracao. Nao integra launcher, nao chama automaticamente em
`config_missing`, nao roda writer e nao altera config real, `/data`, `/opt`,
rede ou Wi-Fi.

Atualizacao C9.1.2: 2026-05-04. C9.1.2 diagnostica a proporcao visual
pos-restauracao observada em C9.1.1. A Fase A read-only confirmou que a midia
ja parecia esticada antes de qualquer stop/start da etapa; a Fase B, autorizada
explicitamente, executou stop/start controlado e a imagem continuou exatamente
igual. O servico terminou `active/enabled`, `NRestarts=0`, player=1, MPV=1 e
renderer=0. A placa observou HDMI `connected/enabled`, framebuffer `1360x768`,
MPV OSD `1024x768` e modos HDMI anunciados sem `1920x1080`; por isso, a
hipotese mais forte passa a ser adequacao de modo/resolucao por tela
fisica/EDID/framebuffer/MPV, nao regressao direta do wizard. Proxima frente
deve considerar contrato visual/seletor por tipo de tela antes de UX final.

Atualizacao C9.1.3: 2026-05-04. C9.1.3 cria e executa o contrato visual curto
de display/orientacao: gera um SVG local em `/tmp` com borda, grid, circulo,
quadrado, cruz central e setas de topo; coleta snapshots sanitizados de
servico/processos/TTY/framebuffer/DRM/MPV; e fornece runner remoto com
`--prepare-only` seguro e `--display` bloqueado por confirmacao humana textual
explicita. Na execucao autorizada, o player foi parado temporariamente, o
padrao apareceu via MPV/DRM por 90s, e o player foi restaurado para
`active/enabled`, `NRestarts=0`, player=1, MPV=1 e renderer=0. O humano
corrigiu a validacao: circulo parece oval, quadrado parece retangulo, a margem
amarela nao esta cortada, mas o padrao nao ocupa/alinha igualmente os dois
eixos da tela; a midia restaurada continua esticada. A etapa nao altera config
real, writer, flags MPV, launcher, rede, NetworkManager, `/data`, `/opt` ou
repo do player. Producao continua bloqueada; a frente futura de
seletor/resolucao/tipo de tela deve ser aberta sem travar C9 indefinidamente.

Atualizacao C9.2: 2026-05-04. C9.2 documenta o contrato futuro de chamada do
setup local pelo launcher no estado `config_missing`, sem alterar o launcher
operacional. O contrato define que o setup local continua obrigatorio no proprio
totem e QR/navegador seguem auxiliares; o wizard deve entrar somente com display
conectado, config invalida/ausente, gatilho local controlado, renderer parado e
player ausente. A TTY futura deve ser reservada, preferencialmente `tty2`, com
exec direto do wizard e sem shell livre. O handoff permanece em `/tmp`, com
candidata/status/summary `0700`/`0600`, e writer/config real ficam para etapa
futura. O problema de display/EDID fica registrado como risco e frente separada,
sem bloquear C9.2. Producao continua bloqueada.

Atualizacao C9.2.1: 2026-05-04. C9.2.1 cria uma simulacao source-only da
decisao launcher/setup local, sem executar o launcher real, renderer, MPV,
wizard HDMI, writer, servico ou acoes operacionais. A matriz cobre display
ausente, config valida, config ausente sem setup, config ausente com setup,
cancelamento do wizard, candidata pronta e config valida apos escrita futura.
A regra `renderer xor wizard xor player` e validada em fixtures, com TTY futura
`tty2`, handoff de candidata em `/tmp` e writer/config real reservados para
etapa futura. Nao altera launcher, `/data`, `/opt`, rede, display ou
`kiosky-player`; producao continua bloqueada.

Atualizacao C9.3: 2026-05-04. C9.3 implementa uma integracao experimental do
launcher com o wizard local em `config_missing`, desligada por padrao e atras
de `TOTEM_SETUP_LOCAL_ENABLED=1` mais autorun/gatilho explicito em `/tmp`. O
launcher passa a conseguir parar renderer, chamar o wizard via `openvt` em TTY
reservada, registrar cancelamento/falha/candidata pronta e voltar para status
sem chamar writer nem iniciar player enquanto a config segue invalida. O
agregador de status passa a mapear estados experimentais `setup_local_*` para
estado publico seguro `config_missing`. Foi criado runner remoto controlado que
usa copia em `/tmp`, config override inexistente, renderer fake sem MPV e
restauracao do servico real ao final. A execucao autorizada provou o caminho de
cancelamento do wizard e depois o caminho de `candidate_ready` com candidata em
`/tmp`; em ambos os casos restaurou `active/enabled`, `NRestarts=0`, player=1,
MPV=1 e renderer=0, com status publico final `player_running`. Nao altera
config real, `/data/config`, writer, rede, display/EDID, flags MPV ou
`kiosky-player`; producao continua bloqueada.

Atualizacao C9.4: 2026-05-04. C9.4 evolui o wizard local para Setup Produto
Local V0, ainda em TTY/curses e atras das flags C9.3. O fluxo passa a exibir
cabecalho Dadooh, titulo "Configuracao do Totem" e passos Conexao, Ambiente,
Tela, Revisao e Concluir. A etapa de conexao e somente read-only agregada ou
mock; ambiente recebe `environment_id` manual com validacao C5.1; tela grava
apenas `rotation_deg` na candidata. A candidata C9.4 fica em
`/tmp/dadooh-c9-4-setup-product-v0/config.candidate.json`, passa C5.1
`allow-mock` e falha em `real-dry-run` como esperado por placeholders.
NetworkManager, writer, config real, player, MPV principal, renderer real,
display real e repo `kiosky-player` nao sao alterados; producao continua
bloqueada. Proxima frente recomendada: C9.5 Wi-Fi real controlado com adapter
estreito, rollback, Ethernet preservada, timeout e diagnostico sanitizado.

Atualizacao C9.4.1/C9.5 plano: 2026-05-04. C9.4.1 validou em placa o
cancelamento com humano no HDMI/teclado e a conclusao `--run-complete-scripted`
com candidata em `/tmp`, C5.1 `allow-mock` passando e `real-dry-run` falhando
como esperado. O servico final ficou `active/enabled`, `NRestarts=0`, player
`playing`, MPV ativo e renderer/setup ausentes. A rodada tambem registrou que
o TTY/openvt precisa de UI ASCII e marcador sanitizado para cancelamento
confiavel. C9.5 foi aberto apenas como plano de Wi-Fi real controlado com
adapter NetworkManager estreito; `--apply` real, hotspot, portal, backend,
writer e config real seguem bloqueados.

Atualizacao C9.5 read-only/plan: 2026-05-04. C9.5 implementa o adapter
`totem_wifi_nm_adapter.py` somente com `--read-only`, `--plan` e `--self-test`.
A leitura de NetworkManager e agregada/sanitizada, usa timeout curto, tolera
ausencia de `nmcli` e grava artefatos apenas em `/tmp`; `--apply` aborta com
`apply disabled in C9.5`. Foi criado runner remoto que copia o adapter para
`/tmp` e nao para servico, nao altera rede, nao coleta senha, nao le/escreve
config real, nao chama writer e nao toca player/MPV. Apply real fica para C9.6,
com confirmacao humana explicita, Ethernet preservada, perfil dedicado,
timeout, teste de conexao e rollback; hotspot/portal continuam fora.

Atualizacao C9.6: 2026-05-04. C9.6 evolui o adapter para apply Wi-Fi real
controlado em bancada, mas totalmente gateado: `--preflight-apply` decide de
forma sanitizada, `--apply` exige flag real, frase exata, arquivo de credencial
restrito em `/tmp`, perfil dedicado permitido, timeout e rollback limitado ao
perfil do produto. O runner remoto exige host informado, nao para servico,
nao altera player/MPV, nao le/escreve config real e nao chama writer. Hotspot,
portal e integracao ao wizard seguem fora; C9.7 deve consumir o resultado
controlado no fluxo local depois de apply real validado em bancada.

Atualizacao C9.6.1: 2026-05-04. C9.6.1 adiciona o caminho de apply real com
console local quando Ethernet nao esta disponivel e o SSH atual depende de
Wi-Fi. O operador digita credenciais apenas na HDMI/teclado do totem; o
secrets-file temporario fica em `/tmp` com `0700/0600`; o apply exige nova
frase textual, `--local-console-confirmed`, perfil dedicado, timeout e
rollback-after-test. O runner abre o fluxo por `openvt` para continuar mesmo se
SSH cair. Seguem bloqueados hotspot, portal, writer/config real, player/MPV e
integracao ao wizard.

Observacao C9.6.1: com o player/MPV exibindo midia, o TTY local pode nao ficar
visivel sem alterar o player. O runner passa a falhar de forma segura quando
nao ha credencial local coletada nem status do adapter, evitando falso positivo
de apply. A proxima rodada deve decidir uma pausa operacional controlada do
player ou outro caminho local de entrada antes de repetir apply real.

Atualizacao C9.6.2: 2026-05-04. C9.6.2 adiciona um patch estreito de bancada:
o runner pode pausar temporariamente `kiosky-player.service`, confirmar que
player/MPV/renderer/setup sairam da HDMI, abrir TTY2 por `openvt`, coletar
credenciais localmente e executar apply Wi-Fi com rollback-after-test. A pausa
exige frase textual especifica e o servico e restaurado por `trap`. Config real,
writer, hotspot, portal, wizard e alteracoes no `kiosky-player` continuam fora.
Validacao de bancada: TTY apareceu, apply real foi tentado, ativacao retornou
`failure`, perfil dedicado ficou ausente ao fim, servico voltou `active/enabled`
com `NRestarts=0` e playback `playing`.

Atualizacao C9.6.3: 2026-05-04. C9.6.3 adiciona diagnostico sanitizado da
falha de ativacao e uma unica retentativa controlada com pausa do player. A
categoria publica da falha anterior e da retentativa ficou
`nm_activation_failed_generic`; NetworkManager/nmcli e Wi-Fi device estavam
presentes, apply foi tentado, rollback foi efetivo, o perfil dedicado ficou
ausente ao fim, secrets-file foi removido, servico voltou `active/enabled` com
`NRestarts=0` e playback `playing`. Uma correcao estreita posterior no adapter
passou a validar o perfil dedicado por `connection.id` e manter a origem do
perfil durante a ativacao; nova retentativa controlada retornou `success`,
rollback-after-test efetivo, perfil dedicado ausente ao fim, servico
`active/enabled`, `NRestarts=0`, playback `playing` e SSH acessivel. C9.7 pode
integrar esse resultado ao Setup Produto Local V0, ainda sem hotspot/portal e
sem writer/config real.

Atualizacao C9.7: 2026-05-04. C9.7 integra o apply Wi-Fi real controlado ao
wizard local na etapa Conexao, com opcao `Testar Wi-Fi agora`. O fluxo coleta
credenciais apenas na HDMI/teclado do totem, usa secrets temporario sob `/tmp`,
perfil dedicado permitido e rollback-after-test por padrao. A candidata e o
status registram somente resultado agregado; SSID, senha, IP, MAC, DNS,
gateway, hostname, BSSID, UUID, nome real de conexao e logs brutos seguem
proibidos. `--prepare-only` e smoke scripted remoto passaram; validacao HDMI
com humano tambem passou: cancelamento, Wi-Fi real integrado com activation
`success`, rollback-after-test `success`, candidata gerada, C5.1 allow-mock
passou, real-dry-run falhou como esperado, servico final `active/enabled`,
`NRestarts=0`, `public_state=player_running`, playback `playing`, player/MPV
ativos, renderer/setup ausentes e perfil dedicado ausente. C9.8 deve tratar
perfil Wi-Fi persistente dedicado sem writer/config real.

Atualizacao C9.8: 2026-05-04. C9.8 implementa e valida Wi-Fi dedicado persistente no
Setup Produto Local V0. O adapter passa a exigir gate explicito para manter o
perfil (`--persistent-product-wifi`, `--keep-dedicated-profile` e frase de
confirmacao C9.8), limita nomes aos prefixos dedicados e continua removendo
secrets temporarios. O wizard separa teste com rollback de configuracao Wi-Fi
deste totem; o runner C9.8 pausa/restaura o player apenas durante o fluxo local.
A validacao em bancada passou com activation `success`, perfil dedicado final
presente, candidata gerada, C5.1 `allow-mock` passando, `real-dry-run` falhando
como esperado, servico final `active/enabled`, `NRestarts=0`,
`public_state=player_running`, playback `playing`, player/MPV ativos e
renderer/setup ausentes. Hotspot, portal, writer, config real, reboot e
alteracao do `kiosky-player` seguem fora.

Atualizacao C9.9: 2026-05-04. C9.9 adiciona um wizard visual local em
`scripts/board/totem_setup_visual_wizard.py`, com telas SVG privadas em `/tmp`
e exibicao via MPV/DRM, sem desktop, Chromium, Xorg, Wayland ou compositor. O
fluxo visual cobre Boas-vindas, Conexao, Ambiente, Tela, Revisao e Concluir,
usa teclado local e reaproveita o Wi-Fi persistente dedicado C9.8. O runner
`scripts/remote/run_c9_9_visual_wizard.sh` prepara preview, cancelamento e
conclusao usando Wi-Fi ja configurado, com pausa/restauracao controlada do
player quando precisa tomar a HDMI. Validacao em bancada passou com preview
visual, cancelamento, candidata gerada, C5.1 `allow-mock` passando,
`real-dry-run` falhando como esperado, servico final `active/enabled`,
`NRestarts=0`, `public_state=player_running`, playback `playing`, player/MPV
ativos e renderer/setup ausentes. Hotspot, portal, writer, config real,
backend/login, reboot e alteracao do `kiosky-player` continuam fora. Proxima
frente: C10 para writer/config real controlado.

Atualizacao C9.9.1: 2026-05-04. C9.9.1 diagnosticou o atraso visual do wizard
com probe sintetico e runner dedicado. A causa provavel ficou classificada como
`mpv_ipc_load_not_presenting_immediately` no caminho `gpu+drm` para SVG
estatico. MPV reiniciado por tela respondeu no primeiro input, mas piscava para
TTY/shell; MPV via IPC evitava o flash, mas seguia um input atrasado. A solucao
aceita foi `framebuffer_svg`, renderizando diretamente em `/dev/fb0` com fonte
PSF instalada, sem desktop/browser/compositor e mantendo os SVGs privados em
`/tmp` como artefatos. Tambem foi corrigido o tratamento de sequencias de
teclado: `Esc` sozinho cancela, mas `PgUp`/`PgDn` nao cancelam acidentalmente.
Validacao humana confirmou caracteres visiveis, Enter no primeiro input e
ausencia de flash para shell durante digitacao. C9.9 `--run-cancel` e
`--run-complete-existing-wifi` passaram, candidata foi gerada, C5.1
`allow-mock` passou e `real-dry-run` falhou como esperado. Estado final:
servico `active/enabled`, `NRestarts=0`, `public_state=player_running`,
playback `playing`, player/MPV ativos e setup ausente. C10.0 fica liberado
para writer/config real controlado.

Atualizacao C10.0: 2026-05-04. C10.0 conecta e valida em bancada o wizard
visual local com o writer real C6 por um handoff privado temporario em `/tmp`.
O novo handoff injeta
endpoint/credencial aprovados de arquivo restrito, preserva `environment_id` e
`rotation_deg` vindos do wizard, valida C5.1 `real-dry-run` e entrega uma
candidata privada para o writer. O runner C10.0 prepara, faz preflight, roda
dry-run sem tocar `/data` e tem modo de escrita real/start bloqueado por frase
humana explicita. O fluxo real para o servico, chama o writer somente para
`/data/config/config.json`, cria backup, aplica `root:totem` `0640`, limpa
temporarios privados e restaura o player. Se necessario, a config ativa pode
ser usada como fonte privada somente com confirmacao adicional explicita, sem
publicar conteudo. A execucao real passou com writer `passed`, backup criado,
usuario `totem` lendo e sem permissao de escrita, servico final
`active/enabled`, `NRestarts=0`, `public_state=player_running`, playback
`playing`, player/MPV ativos e setup/renderer ausentes. Wi-Fi, hotspot, portal,
backend/login, reboot e repo `kiosky-player` seguem fora. C10.1 fica reservado
para reboot/autoboot controlado.

Atualizacao C10.1: 2026-05-04. C10.1 valida reboot/autoboot controlado com
Wi-Fi persistente e config real ja escrita pelo C10.0. O novo runner prepara,
faz preflight sanitizado e executa um reboot somente com a frase humana
explicita `CONFIRMO REBOOT CONTROLADO C10.1`. A placa voltou por SSH em 46s e
convergiu para servico `active/enabled`, `NRestarts=0`,
`public_state=player_running`, playback `playing`, player/MPV ativos e
renderer/setup ausentes. A config real permaneceu presente com `root:totem`
`0640`, usuario `totem` lendo e sem permissao de escrita, e o perfil Wi-Fi
dedicado permaneceu presente. C10.1 nao le/escreve config real, nao chama
writer, nao altera Wi-Fi/NetworkManager, nao habilita root read-only e nao faz
corte seco. O `wizard_rc=8` visto em C10.0 fica classificado como retorno bruto
de wrapper TTY nao bloqueante para boot/autoboot, com hardening opcional
posterior. C10.2 fica reservado para fluxo `config_missing` real controlado.

Atualizacao C10.2: 2026-05-04. C10.2 valida o fluxo real de recuperacao de
produto `config_missing` -> wizard visual local -> handoff privado -> writer
real -> config real -> start player. O `config_missing` foi provocado por uma
copia temporaria do launcher com `KIOSKY_CONFIG_PATH` apontando para arquivo
ausente sob `/tmp`, sem mover ou apagar `/data/config/config.json` e sem
alterar a unit systemd. O dry-run passou sem escrita real. A execucao real,
autorizada pela frase `CONFIRMO CONFIG_MISSING REAL C10.2 COM WRITER`, gerou
candidata visual, passou handoff/C5.1 `real-dry-run`, chamou o writer guardado,
criou backup, escreveu a config real e restaurou o player. Estado final:
servico `active/enabled`, `NRestarts=0`, `public_state=player_running`,
playback `playing`, player/MPV ativos, renderer/setup ausentes, perfil Wi-Fi
dedicado presente e config `root:totem` `0640` com usuario `totem` lendo e sem
escrita. A config ativa foi lida somente como fonte privada autorizada, sem
publicar conteudo. Wi-Fi/NetworkManager, hotspot, portal, reboot, root
read-only, corte seco e repo `kiosky-player` seguem fora.

Atualizacao C10.3: 2026-05-05. C10.3 implementa e valida em bancada a
Superficie de Produto V0
antes de read-only/homologacao. O wizard visual passa a iniciar pela escolha de
orientacao, registra `rotation_deg` na candidata e ajusta layout das telas
seguintes conforme paisagem/retrato. A etapa Conexao troca digitacao manual de
SSID por lista local read-only via NetworkManager, exibindo nomes de rede
somente no HDMI do operador. Status, summary e candidata registram apenas
contagem/categorias (`wifi_networks_found_count`, `selected_network_present`,
`selected_network_signal_bucket`, `selected_network_security_present`); senha
continua oculta e SSID/senha/IP/MAC/DNS/gateway/BSSID/hostname/UUID/logs brutos
seguem proibidos em artefatos. O runner C10.3 adiciona preview/cancelamento,
preview de lista Wi-Fi, conclusao com Wi-Fi existente e modos reversiveis para
guardrails visuais de boot/getty com confirmacao explicita e rollback. A
validacao humana passou com preview visual, preview de lista Wi-Fi, cancelamento
e conclusao usando Wi-Fi dedicado existente; C5.1 `allow-mock` passou e
`real-dry-run` falhou como esperado por placeholders. Guardrails de boot foram
aplicados, SSH voltou apos reboot controlado e o estado final foi
`active/enabled`, `NRestarts=0`, `public_state=player_running`, playback
`playing`, player/MPV ativos e renderer/setup ausentes. Writer, config real,
Wi-Fi/NetworkManager apply, hotspot, portal, root read-only, corte seco e repo
`kiosky-player` seguem fora por padrao. C10.4 fica reservado para Product
Surface V0 + writer real.

Atualizacao C10.4: 2026-05-05. C10.4 valida Product Surface V0 com writer real:
wizard visual com orientacao primeiro, Wi-Fi dedicado existente, handoff
privado, C5.1 `real-dry-run`, writer guardado, backup, permissoes
`root:totem` `0640` e start controlado do player. O runner exige host
explicito, nao hardcoda IP e manteve a escrita real bloqueada pela frase
`CONFIRMO PRODUCT SURFACE WRITER REAL C10.4`. O fluxo real passou: writer
retornou `passed`, backup foi criado, usuario `totem` le e nao escreve, servico
final `active/enabled`, `NRestarts=0`, `public_state=player_running`, playback
`playing`, player/MPV ativos e renderer/setup ausentes. Wi-Fi/NetworkManager,
hotspot, portal, root read-only, corte seco, reboot e repo `kiosky-player`
seguem fora.

Atualizacao C10.5: 2026-05-05. C10.5 foca a superficie visual antes de
read-only: adiciona preview e confirmacao da orientacao no wizard, mantem
`rotation_deg` na candidata, usa layouts simples para paisagem/retrato e cria
um splash leve de framebuffer para boot/transicoes. A validacao em HDMI mostrou
que pausar temporariamente o getty da TTY de produto elimina disputa de login e
volta a responder com uma unica tecla; o splash limpo reduz vazamento tecnico
nas transicoes. A rotacao fisica da UI inteira no framebuffer foi descartada
por distorcer texto e fica para uma camada de renderizacao futura. O runner
`run_c10_5_visual_boot_rotation.sh` nao hardcoda IP e aplica guardrails
reversiveis de boot/getty/splash somente com confirmacao humana, backup e
rollback. Writer, config real, Wi-Fi/NetworkManager, hotspot, portal, root
read-only, corte seco e repo `kiosky-player` seguem fora por padrao.

Atualizacao C10.5.1: 2026-05-05. C10.5.1 corrige o contrato de orientacao sem
rotacionar bitmap pronto: a selecao passa a usar setas como UX principal,
confirmacao/cancelamento usa lista, as telas seguintes sao geradas em canvas
nativo de paisagem `1280x720` ou retrato `720x1280`, e o renderer de
framebuffer mapeia esse canvas para a tela preservando proporcao de texto. O
wizard grava `orientation.json` publico/sanitizado em `/tmp`, preserva
`rotation_deg` na candidata e o splash aceita `--rotation-deg`. Writer, config
real, Wi-Fi/NetworkManager, hotspot, portal, root read-only, corte seco e repo
`kiosky-player` seguem fora. A validacao HDMI com o runner
`run_c10_5_1_orientation_ux_contract.sh` passou para preview de orientacao,
fluxo completo portrait, fluxo completo landscape e preview de splash nas
quatro rotacoes, com estado final `active/enabled`, `NRestarts=0`,
`public_state=player_running` e playback `playing`.

Atualizacao C10.5.2: 2026-05-05. C10.5.2 consolida guardrails visuais de
boot/shutdown/transicao. O splash passa a ler a orientacao publica allowlisted
em `/data/state/totem-display/orientation.json`, contendo apenas
`schema_version`, `updated_at`, `rotation_deg` e `orientation_label`; o wizard
pode gravar esse contrato quando autorizado, sem tocar `/data/config`. O novo
runner `run_c10_5_2_visual_guard_boot_shutdown.sh` adiciona inspecao
sanitizada, preview de splash, stress curto de transicoes,
aplicacao/rollback reversivel de guardrails persistentes e reboot visual
controlado. A validacao tecnica passou: guardrails aplicados, SSH voltou apos
reboot, servico final `active/enabled`, `NRestarts=0`,
`public_state=player_running`, playback `playing`, player/MPV ativos,
renderer/setup ausentes e `systemctl --failed=0`. O runner herdado foi
ajustado para tolerar reset temporario de SSH na coleta pos-reboot. Writer,
config real, Wi-Fi/NetworkManager, hotspot, portal, root read-only, corte seco
e repo `kiosky-player` seguem fora. Observacao humana: ainda aparece
rapidamente texto tecnico tipo Armbian/fsck com `files`/`blocks` antes do splash
Dadooh inicial. Essa janela early-boot fica documentada para a trilha de imagem,
initramfs/read-only e nao foi mascarada desabilitando fsck nesta rodada.

Atualizacao C10.5.3: 2026-05-05. C10.5.3 adiciona auditoria especifica para
vazamento visual early-boot antes dos servicos de produto assumirem a HDMI. O
runner `run_c10_5_3_early_boot_visual_audit.sh` inspeciona categorias
sanitizadas de `/boot/armbianEnv.txt`, cmdline atual, gettys e servicos visuais,
gera plano sem aplicar nada e oferece apply/rollback reversiveis para reduzir
verbosity/console/status/loglevel quando o arquivo Armbian for reconhecido com
seguranca. Nao desabilita fsck, nao altera initramfs, nao habilita read-only,
nao faz corte seco e nao toca config real, writer, Wi-Fi/NetworkManager ou
`kiosky-player`. A validacao aplicou `verbosity=0`, `console=serial`,
`loglevel=0`, `rd.systemd.show_status=false` e `logo.nologo`, com backup e
rollback. O reboot controlado voltou em 8s, estado final
`active/enabled`, `NRestarts=0`, `public_state=player_running`, playback
`playing`, player/MPV ativos, renderer/setup ausentes,
`systemctl --failed=0` e filtro critico de kernel `0`. Observacao humana: o
texto tecnico early-boot sumiu.

Atualizacao C10.6: 2026-05-05. C10.6 redefine a frente de acesso local como
"Abrir Configuracoes do Totem com player rodando". A UI principal continua
sendo o wizard visual do produto; menu de manutencao/suporte, terminal local,
root e shell ficam fora desta etapa. O acesso V0 adiciona gatilhos locais por
teclado USB: `Ctrl+I` ou `F10` segurados por 5 segundos geram apenas uma
solicitacao publica restrita em `/run/dadooh-settings/request.json`; o wizard
visual de Configuracoes abre diretamente. `F12` segue como fallback tecnico
quando disponivel, mas nao e o atalho principal por exigir `Fn` em alguns
teclados. O runner
`scripts/remote/run_c10_6_open_settings_from_player.sh` usa host explicito,
instala/remove o trigger temporario em `/run/systemd/system`, pausa o player de
forma controlada, cobre a HDMI com splash/transicao, abre o wizard visual,
restaura o player ao cancelar e oferece dry-run com handoff/C5.1 sem chamar
writer. A escrita real permanece protegida por confirmacao explicita e delegada
ao fluxo C10.4 ja validado. Wi-Fi/NetworkManager, config real, hotspot, portal,
root read-only, corte seco e repo `kiosky-player` seguem fora por padrao. C10.6.2
fica reservado para PIN/senha local de Configuracoes; C10.7 fica reservado para
Suporte Local V0 separado: diagnostico, reiniciar exibicao,
reboot/desligamento seguro.

Atualizacao C10.6.1: 2026-05-05. C10.6.1 transforma o acesso local de
Configuracoes em gatilho persistente de produto. O caminho principal passa a ser
`F10` segurado por 5 segundos, monitorado pelo servico
`totem-settings-trigger.service`, que cria apenas um request sanitizado em
`/run/dadooh-settings` e aciona o oneshot `totem-open-settings.service` para
abrir o wizard visual existente com o player rodando. `Ctrl+I` e `F12` deixam de
ser caminho principal e ficam disponiveis apenas por flags explicitas de
desenvolvimento. A UI continua sem menu de manutencao, suporte, terminal, shell,
root ou login Linux. Writer real, config real, Wi-Fi/NetworkManager, hotspot,
portal, root read-only e corte seco seguem fora. PIN/senha local fica para
C10.6.2; Suporte Local V0 continua separado para C10.7.

Atualizacao C10.6.2: 2026-05-05. C10.6.2 fecha a aplicacao das Configuracoes
abertas via `F10`. A sessao persistente continua segura por padrao, mas passa a
aceitar uma politica temporaria restrita em `/run/dadooh-settings` para dry-run
ou escrita real autorizada. No fluxo validado, o operador abriu Configuracoes
com `F10`, concluiu o wizard visual, o handoff privado passou, o writer real
escreveu `/data/config/config.json`, criou backup, preservou permissoes
`root:totem 0640`, atualizou `orientation.json` publico seguro e reiniciou o
player. A verificacao sanitizada confirmou `rotation_deg=270` na config ativa e
no contrato publico, splash seguindo `orientation.json`, servico final
`active/enabled`, `NRestarts=0`, `public_state=player_running`, playback
`playing`, player/MPV ativos e renderer/setup ausentes. Wi-Fi/NetworkManager,
hotspot, portal, root read-only, corte seco e repo `kiosky-player` nao foram
alterados, e a politica temporaria de apply foi removida ao final. Observacao
humana confirmou midias na orientacao escolhida e nenhum flash shell/login no
fluxo F10 -> wizard -> salvar -> player. Proxima frente: C10.7 auditoria de
reprodutibilidade placa -> repo para preparar imagem.

Atualizacao C10.7/C10.7.2: 2026-05-05. C10.7 criou a auditoria de
reprodutibilidade placa dev -> repo, com runner remoto read-only, matriz placa
vs repo e evidencia sanitizada. C10.7.1 incorporou o delta pos-C10.6.2:
scripts F10, units persistentes, writer/handoff, contrato `orientation.json`,
guardrails de splash/transicao e evidencia C10.6.2. C10.7.2 encontrou uma
sessao F10 stale, limpou somente estado temporario seguro em
`/run/dadooh-settings`, restaurou o player, corrigiu limpeza/diagnostico de
lock nos scripts de trigger/sessao e confirmou estado final limpo:
`kiosky-player.service=active/enabled`,
`totem-settings-trigger.service=active/enabled`,
`totem-open-settings.service=inactive/static`, sem `session.lock`, sem
`request.json`, sem setup remanescente, `public_state=player_running` e
playback `playing`. Nao houve writer, config real, Wi-Fi, pacote, reboot,
segunda placa, imagem, read-only ou alteracao de `kiosky-player`.

Atualizacao C10.8: 2026-05-05. C10.8 cria a base do instalador idempotente do
appliance. Foram adicionados manifest versionado, installer, verifier, runner
remoto e unit standalone `dadooh-visual-splash.service`. O instalador cobre
usuario/grupo `totem`, layout `/data`, `/opt/totem/bin`, scripts board, units
systemd, guardrails visuais de boot, runtime minimo verificavel,
`orientation.json` publico seguro e manifest instalado sanitizado. Ele nao
embute config real, secrets, SSID/senha, IP/MAC/DNS/gateway, midias, logs,
backups ou candidatos privados; nao chama writer e nao altera NetworkManager.
Os modos seguros `--prepare-only`, `--dry-run-dev`, `--verify-dev` e
`--idempotence-dev-dry-run` passaram na placa dev sem apply. O verify ainda
lista diferencas claras: pin do `kiosky-player` ausente, drift de
`kiosky_service_launcher.sh`, ausencia de `totem_wifi_local_credentials_tty.py`
em `/opt/totem/bin`, ausencia de `/data/state/totem-appliance` e metadata de
diretorios de estado divergente do manifest. Portanto, segunda placa/C10.9
ainda nao deve iniciar ate definir o pin do `kiosky-player` e decidir/aplicar o
refresh C10.8 na placa dev.

Atualizacao C10.8.1: 2026-05-05. C10.8.1 resolveu os deltas de
reprodutibilidade do C10.8. O manifest agora fixa o `kiosky-player` em
`dadoohai/kiosky-player`, ref `appliance-v0.1`, commit
`c71318a64c08e47b8426f1388b95f21364d57123`. O launcher divergente foi
classificado como `REPO_AHEAD_REFRESH_BOARD`; o script
`totem_wifi_local_credentials_tty.py` foi mantido como fallback local seguro; e
os diretorios de runtime state foram reclassificados para checagem de
estrutura/metadata sem hash de conteudo. Com confirmacao humana explicita, o
apply refresh criou `/data/state/totem-appliance`, instalou os dois scripts
versionados e escreveu manifest instalado sanitizado, sem pacote, upgrade,
reboot, writer, Wi-Fi, config real, alteracao do `kiosky-player` ou restart de
produto. O verify final ficou `overall_status=ok`, `ready_for_second_board=true`
e a idempotencia final ficou `stable=true` com `action_count=0`. C10.9 pode
iniciar na segunda placa/cartao, instalando o `kiosky-player` a partir do pin
fixado e mantendo secrets/config real/Wi-Fi privados fora da imagem.

Atualizacao C10.9: 2026-05-05. C10.9 validou uma segunda placa/cartao por
instalacao limpa, sem clonar estado da placa dev. O bootstrap manual previo
ficou limitado a root password e rede/SSH de bancada. O runner
`scripts/remote/run_c10_9_second_board_clean_install.sh` executou inspect,
dry-run, apply com confirmacao humana, verify, idempotencia, config_missing,
F10 assistido e reboot controlado. O apply instalou usuario/grupo `totem`,
layout `/data`, scripts board, units systemd, guardrails de boot, runtime
minimo (`mpv`, `ffmpeg`, `python3-requests`) sem upgrade amplo, e o
`kiosky-player` do pin
`c71318a64c08e47b8426f1388b95f21364d57123`. Nao copiou config real, secrets,
SSID/senha, IP/MAC/DNS/gateway, midias/cache/logs/backups ou estado da placa
dev; nao chamou writer e nao alterou Wi-Fi/NetworkManager. O reboot check
ficou `overall_status=ok`, `systemctl_failed_count=0`, servicos esperados
ativos/enabled, `config_missing_safe=true`, `public_state=config_missing`, F10
passou apos correcao de fallback para placa sem config real, e a idempotencia
final ficou `stable=true` com `action_count=0`. Observacao posterior mostrou
que, em placa limpa, salvar Configuracoes sem config ativa permanece em
`candidate-only` e nao chama writer; tambem faltava
`totem_status_render_preview.py` em `/opt/totem/bin`, impedindo feedback visual
publico de `config_missing`. C10.9 valida a instalacao limpa da camada
appliance, mas C10.9.1 deve aplicar o refresh do manifest/status e definir
provisionamento privado da config mock real antes de C11.0; imagem final,
read-only e provisionamento real definitivo seguem fora desta rodada.

Atualizacao C10.9.1: 2026-05-05. C10.9.1 aplicou refresh na segunda placa,
instalando `totem_status_render_preview.py` e os scripts atualizados. O estado
`config_missing` passou a publicar feedback visual `config_pending`, sem ficar
preso em "Iniciando player". O fluxo `candidate-only` sem config ativa foi
validado: candidata gerada, writer nao chamado, config real nao escrita e
retorno para `config_missing`. O provisionamento real controlado usou arquivo
privado restrito em `/tmp`, com `api_key` e `api_url` sem publicacao de valores;
`environment_id` veio do wizard. C5.1 real-dry-run passou, o writer real
escreveu `/data/config/config.json`, permissoes finais `root:totem 0640`,
temporarios privados removidos, `public_state=player_running`,
`playback=playing`, `NRestarts=0` e `systemctl_failed_count=0`. Reboot
controlado pos-provisionamento passou com config presente,
`public_state=player_running`, `playback=playing`,
`kernel_critical_filter_count=0` e sem logs/secrets publicados. C10.9.1 deixa a
segunda placa pronta para C11.0 read-only readiness audit; backend/login final,
imagem final, root read-only e corte seco seguem fora.

Atualizacao C10.10: 2026-05-05. C10.10 consolida C10.8/C10.9/C10.9.1 em um
pacote instalavel RC de bancada. Foram adicionados o runbook unico
`docs/product/90_PACOTE_INSTALAVEL_RC_BANCADA.md`, o helper seguro
`scripts/board/totem_private_values_prepare.py` e o manifest
`releases/installable-rc/manifest.md`. O runner C10.9.1 passou a validar
private-values por esse helper, mantendo apenas summaries sanitizados e sem
imprimir `api_key`, `api_url` literal ou `environment_id`. O status do RC fica:
`installable_bench_rc=true`, `final_image=false`, `read_only=false`,
`power_cut_tested=false` e `long_test=false`. C11.0 e o proximo passo para
read-only readiness audit; C12.0 deve tratar imagem customizada e eliminar o
bootstrap tecnico manual do Armbian.

Atualizacao C10.10.1: 2026-05-06. C10.10.1 auditou o incidente em que a
segunda placa ficou com HDMI preto e sem SSH apos desligamento normal, voltando
apos power cycle fisico. O runner
`scripts/remote/run_c10_10_1_power_state_audit.sh` fez inspect atual e
postmortem do boot anterior sem reboot/poweroff, sem writer, sem Wi-Fi, sem
config real e sem logs brutos. Resultado: `previous_boot_end_category=clean_poweroff`,
`previous_boot_had_kernel_panic=false`, `previous_boot_had_ext4_error=false`,
`previous_boot_had_mmc_error=false`, `kernel_critical_filter_count=0` e estado
atual `public_state=player_running`, servicos ativos/enabled e
`systemctl_failed_count=0`. Classificacao:
`POWER_STATE_EXPECTED_BUT_UX_UNCLEAR`. O installable bench RC continua valido
com follow-up de UX, mas C11.0 fica bloqueado ate C10.10.2 Shutdown UX separar
claramente `Reiniciar totem` de `Desligar com seguranca` e explicar power cycle
fisico para religar.

Atualizacao C10.10.2: 2026-05-06. C10.10.2 implementa e valida a UX de
desligamento seguro. O splash visual passa a ter `Desligamento seguro` com
mensagem explicita: quando a tela apagar, remover e reconectar energia para
ligar novamente; e adiciona modo `reboot` separado para nao confundir
reinicio com poweroff. O runner
`scripts/remote/run_c10_10_2_shutdown_ux.sh` inclui inspect, preview,
simulacao sem poweroff, refresh controlado dev/test e modo de poweroff real
bloqueado por `CONFIRMO DESLIGAR TOTEM`. A validacao rodou primeiro na placa
dev e depois na segunda placa, sem executar poweroff real, sem alterar config
real, writer, Wi-Fi, pacotes, read-only, corte seco ou `kiosky-player`.
Resultado final nas duas placas: tela renderizada, mensagem de power cycle
confirmada, `poweroff_executed=false`, servico `active/enabled`,
`public_state=player_running`, playback `playing`, player/MPV ativos,
renderer/setup ausentes e `NRestarts=0`. O manifest passa a liberar C11.0 como
auditoria de readiness, ainda sem habilitar read-only e sem imagem final.

Atualizacao C11.0: 2026-05-06. C11.0 executa a auditoria de readiness para
root read-only sem habilitar read-only, sem poweroff, sem corte seco, sem
writer, sem config real, sem Wi-Fi/NetworkManager e sem pacotes. O runner
`scripts/remote/run_c11_0_read_only_readiness_audit.sh` foi criado com
`--prepare-only`, `--audit-dev`, `--audit-test-readonly` opcional e
`--summary`. A auditoria rodou somente na placa dev e confirmou estado
operacional saudavel (`public_state=player_running`, playback `playing`,
servicos ativos/enabled e `NRestarts=0`), mas classificou
`root_read_only_ready=false` e `ready_for_read_only_enablement=false`.
Principais blockers: politica de NetworkManager para perfis em
`/etc/NetworkManager/system-connections` e politica de logs/journald com
`/var/log/journal` presente. Paths mutaveis principais ja estao em `/data`,
`/tmp` e `/run`; C11.1 pode iniciar como rodada de politica/mitigacao, ainda
sem habilitar root read-only e sem corte seco.

Atualizacao C11.1: 2026-05-06. C11.1 define a politica concreta para root
read-only/overlay sem habilitar read-only e sem alterar a placa. Foram criados
`scripts/board/totem_read_only_policy.json`,
`scripts/board/verify_totem_read_only_policy.sh` e
`scripts/remote/run_c11_1_read_only_policy_probe.sh`. A politica mantem estado
persistente em `/data`, runtime em `/tmp`/`/run`, codigo em `/opt/totem`
imutavel, NetworkManager no caminho nativo com janela controlada de manutencao
para escrita de perfis, journald volatil na imagem de produto, `/boot` e
`/etc` alteraveis apenas por instalador/manutencao com backup e rollback, e
`/var` como estado runtime a validar. O probe rodou somente na placa dev, nao
alterou estado, manteve `public_state=player_running`, playback `playing`,
servicos ativos/enabled e `NRestarts=0`. Resultado:
`ready_for_c11_2_enablement=true`, mas `root_read_only_ready=false` e
`ready_for_read_only_enablement=false` ate C11.2 aplicar mitigacoes
reversiveis. Placa teste nao foi tocada.

Atualizacao C11.2: 2026-05-06. C11.2 aplica mitigacoes reversiveis somente na
placa dev, ainda sem habilitar root read-only e sem corte seco. O runner
`scripts/remote/run_c11_2_read_only_mitigation_apply.sh` inclui `--inspect`,
`--dry-run`, `--apply-dev`, `--verify`, `--rollback` e `--reboot-check`.
Aplicado: drop-in reversivel de journald volatil, estados de politica para
NetworkManager, `/var`, `/boot` e `/etc` sob
`/data/state/totem-read-only-mitigation`, e rollback state. O reboot controlado
pos-apply passou com `journald_storage_effective=volatile`,
`rollback_state_present=true`, `ready_for_c11_3_enablement=true`,
`public_state=player_running`, playback `playing`, servicos ativos/enabled,
`NRestarts=0` e `systemctl_failed_count=0`. Nao houve read-only, corte seco,
poweroff, writer, config real, Wi-Fi/NetworkManager, pacotes, `kiosky-player`
ou placa teste. `root_read_only_ready=false` e
`ready_for_read_only_enablement=false` continuam ate C11.3.

Atualizacao C11.3: 2026-05-06. C11.3 criou
`scripts/remote/run_c11_3_read_only_enablement_dev.sh` para enablement
controlado de root read-only/overlay na dev. `--inspect` e `--dry-run-enable`
rodaram sem alterar a placa e detectaram o mecanismo oficial
`armbian_config_module_overlayfs`, mas `overlayroot`/`overlayroot-chroot` nao
estao presentes. Como C11.3 proibe instalacao de pacotes, o enablement foi
bloqueado com seguranca: `enable_executed=false`, `read_only_enabled=false`,
`overlay_active=false`, `ready_for_c11_4=false`. Estado final permaneceu
saudavel (`public_state=player_running`, playback `playing`,
`systemctl_failed_count=0`), sem writer, config real, Wi-Fi/NetworkManager,
pacotes, reboot, poweroff, corte seco ou placa teste. Proximo corte deve
decidir como aprovisionar `overlayroot` sem `apt upgrade` ou mover isso para a
imagem base.

Este roadmap separa a evolucao de produto/UX da homologacao `v0.1-rc1`. A RC1
continua focada em reproduzir a base tecnica validada em outra placa/cartao. As
fases abaixo devem ser implementadas em passos pequenos, sempre mantendo o
player atual recuperavel.

## Fase A - status/splash local minimo

Status: concluida em desenvolvimento. Ver
`docs/product/08_FASE_A_CONCLUSAO.md`.

Objetivo:

- mostrar Dadooh e estado atual;
- esconder terminal/logs do operador;
- continuar sem Chromium, desktop ou compositor;
- ainda sem onboarding;
- nao quebrar o player.

Subfases concluidas em desenvolvimento:

- A0 - contrato/status/render preview: documentar o contrato sanitizado,
  detalhar estados publicos e criar preview local nao integrado;
- A1.1 - agregador de status: gerar `status.json` e `status.svg` publicos em
  `/tmp/dadooh-status`;
- A1.2 - integracao launcher: chamar agregador apos status bruto do launcher;
- A1.2.1 - refresh periodico: convergir `starting_player` para
  `player_running` enquanto o player esta vivo;
- A1.3 - `config_missing`: bloquear app/MPV quando a config minima nao existe
  ou nao e valida;
- A1.4 - renderer visual: exibir SVG publico em `config_missing` e parar antes
  do MPV principal do player.

Arquivos principais:

- `docs/product/03_FASE_A_STATUS_SPLASH.md`;
- `docs/product/STATUS_CONTRACT_V0.md`;
- `docs/product/04_STATUS_AGGREGATOR_A1.md`;
- `docs/product/05_LAUNCHER_STATUS_INTEGRATION_A1.md`;
- `docs/product/06_CONFIG_MISSING_A1.md`;
- `docs/product/07_STATUS_RENDERER_A1.md`;
- `docs/product/08_FASE_A_CONCLUSAO.md`;
- `scripts/board/kiosky_service_launcher.sh`;
- `scripts/board/kiosky-player.service`;
- `scripts/board/totem_status_render_preview.py`;
- `scripts/board/totem_status_aggregate.py`;
- `scripts/board/totem_status_renderer.sh`.

Validacao consolidada em desenvolvimento:

- `config_missing` mostra tela Dadooh/configuracao pendente;
- `kiosk.py=0` e MPV principal `0` enquanto renderer esta ativo;
- renderer e MPV principal nao rodam juntos;
- ao restaurar config valida, renderer para e player volta a `playing`;
- observer curto apos restauracao com IPC success, timeout `0` e `5/5`
  aliases avancando;
- boot sem HDMI continua em `display_missing` sem iniciar app/MPV;
- reconectar HDMI inicia app automaticamente;
- `systemctl --failed=0`;
- status publico sanitizado.

Riscos:

- disputa pelo DRM/KMS entre splash e MPV;
- splash atrasar ou bloquear o player;
- status mostrar dados privados.

Criterios de nao regressao:

- `display_missing` nao inicia app, MPV principal ou renderer;
- `config_missing` nao inicia app ou MPV principal;
- `player_running` nao mantem renderer ativo;
- renderer sempre para antes do player tomar DRM/KMS;
- status publico e SVG continuam sem dados sensiveis;
- metricas do player permanecem iguais as rodadas aprovadas.

Criterio de rollback:

- desabilitar o servico/componente de splash e voltar ao launcher atual que
  inicia apenas o player quando ha HDMI.

## Fase B - status visual e manutencao minima

Status: B1 concluida em desenvolvimento. O restante da manutencao minima segue
planejado. Ver `docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md` e
`docs/product/10_FASE_B1_VISUAL_CONFIG_MISSING.md`.

Objetivo:

- transformar a tela tecnica de `config_missing` em uma experiencia visual
  mais clara;
- padronizar mensagens e codigos publicos Dadooh;
- preparar area visual para QR code futuro, sem QR funcional ainda;
- definir manutencao minima antes de implementar comandos reais;
- manter a regra DRM/KMS validada na Fase A.

Escopo:

- melhorar `config_missing`;
- desenhar estados `player_error` e `maintenance_placeholder`;
- definir codigos publicos como `CONFIG_MISSING`, `DISPLAY_MISSING` e
  `PLAYER_EXITED`;
- especificar manutencao minima: ver estado publico, identificar erro e
  preparar reinicio de player/diagnostico sanitizado para fase posterior.

B1 concluida em desenvolvimento:

- tela publica Dadooh "Configuracao pendente" validada por observacao humana;
- codigo publico `CONFIG_MISSING` visivel;
- area de configuracao assistida marcada como futura, sem QR funcional;
- renderer ativo apenas em `config_missing`;
- `kiosk.py=0` e MPV principal `0` enquanto renderer esta ativo;
- restauracao para `player_running` com renderer parado e observer curto limpo;
- sem Wi-Fi setup, hotspot, portal, ativacao backend, reset real, telemetria ou
  mudanca no `kiosky-player`.

Fora de escopo:

- hotspot Wi-Fi;
- portal local completo;
- ativacao backend;
- factory reset real;
- reset leve operacional;
- telemetria.

Arquivos provaveis:

- `docs/product/09_FASE_B_STATUS_VISUAL_MANUTENCAO_MINIMA.md`;
- extensao do preview SVG;
- possivel tabela de mensagens/codigos publicos;
- ajustes futuros no agregador apenas se o contrato publico precisar de novos
  campos allowlisted;
- ajustes futuros no renderer/launcher somente apos revisao de processo
  DRM/KMS.

Validacao minima:

- previews locais para `config_missing`, `player_error` e
  `maintenance_placeholder`;
- sanitizacao de SVG e JSON;
- renderer nao roda em `player_running`;
- renderer para antes de `kiosk.py`;
- restauracao para player com observer curto sem timeout;
- `systemctl --failed=0`.

Riscos:

- refinamento visual quebrar legibilidade;
- adicionar campo publico que vaze dado privado;
- habilitar `player_error` sem testar retry e ordem de processos;
- introduzir manutencao que pareca pronta antes de haver comandos seguros.

Criterios de aceite:

- operador entende que a configuracao esta pendente sem terminal;
- codigos publicos estao documentados;
- area de QR code futuro existe sem acionar setup real;
- nenhuma acao de manutencao executa shell arbitrario;
- Fase A nao regride.

Criterio de rollback:

- voltar ao layout A1.4 de `config_missing` e manter o launcher atual.

## Fase C0-C2 - planejamento e refinamento minimo de onboarding

Status: C0 e C1 documentados; C1.1/C2 em preparacao documental. Nao implementa
mudancas operacionais.

Documentos:

- `docs/product/12_C0_ONBOARDING_WIFI_CONFIG.md`;
- `docs/product/13_RISCOS_ONBOARDING_WIFI_CONFIG.md`;
- `docs/DECISIONS/ADR-0008-onboarding-wifi-config.md`;
- `docs/product/14_C1_CONFIG_MISSING_MINIMAL_ONBOARDING.md`;
- `docs/product/15_C1_MINIMAL_USER_FLOW.md`;
- `docs/product/16_C1_MINIMAL_STATE_MACHINE.md`;
- `docs/product/17_C2_MOCK_VISUAL_FORMULARIO.md`;
- `docs/product/18_C2_PREVIEW_VISUAL_EVIDENCE.md`;
- `docs/product/25_C5_CONFIG_WRITER_MOCK.md`;
- `docs/product/26_C5_1_CONFIG_CONTRACT_VALIDATOR.md`;
- `docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md`;
- `docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md`;
- `docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md`;
- `docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md`;
- `docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md`;
- `docs/product/36_C7_DIAGNOSTICO_STATUS_APPLIANCE.md`;
- `docs/product/37_PRODUTO_V1_OPERACAO_ONBOARDING_RECUPERACAO.md`;
- `docs/product/38_FLUXO_PRODUTO_V1_ONBOARDING_MANUTENCAO_RECUPERACAO.md`;
- `docs/product/39_INVENTARIO_TELAS_ACOES_PRODUTO_V1.md`;
- `docs/product/40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md`;
- `docs/product/prototypes/v1-operacao-recuperacao/index.html`;
- `docs/DECISIONS/ADR-0009-minimal-config-environment-id.md`;
- `docs/DECISIONS/ADR-0010-api-token-provisioning.md`.

Objetivo:

- especificar o fluxo de onboarding antes de qualquer implementacao de rede;
- separar primeiro boot, Wi-Fi, ativacao e manutencao minima;
- definir estados publicos e mensagens sem dados privados;
- definir limites de seguranca para credenciais, config e diagnostico;
- desenhar rollback antes de alterar NetworkManager ou `/data/config`.

Escopo de planejamento:

- jornadas de operador e suporte;
- contrato publico de estados para setup;
- decisao entre hotspot, rede existente e fallback de bancada;
- politica para credenciais Wi-Fi sem logs sensiveis;
- fluxo de ativacao backend por codigo, ainda sem endpoint implementado;
- escrita atomica futura de config em `/data/config`;
- criterios de teste e bloqueio para placa de desenvolvimento e homologacao;
- criterios de rollback para voltar ao player/status atual.

Fora de escopo em C0-C2:

- implementar Wi-Fi setup;
- criar hotspot;
- criar portal local;
- integrar ativacao backend;
- escrever config real por operador;
- implementar reset real;
- implementar telemetria;
- instalar pacotes.

Refinamento C1:

- foco no caso `config_missing` com sistema/servico/launcher funcionando e HDMI
  conectado;
- operador informa apenas `environment_id`;
- `api_key`/token fica fora da UI e, conforme ADR-0010, pode vir de
  provisionamento local privado em C6;
- ativacao por codigo, login e lista de ambientes ficam como alternativas
  futuras;
- primeira inicializacao completa de cartao Armbian virgem fica para fase
  posterior.

Sequencia incremental refinada:

- C1 - escopo e fluxo minimo Wi-Fi + `environment_id` documentado;
- C1.1 - coerencia documental C0/C1 e preparacao de C2;
- C2 - mock visual/formulario sem alterar rede;
- C3 - diagnostico Wi-Fi read-only;
- C4 - Wi-Fi real controlado em bancada com Ethernet preservada;
- C5 - config writer mock em `/tmp`, sem secrets, sem config real e preparando
  C6;
- C5.1 - contrato de config minima e validador dry-run em `/tmp`;
- C6.0 - plano de writer real concluido;
- C6.1-preflight - checklist e decisoes antes de implementacao real;
- C6.2 - writer real simulado em `/tmp`, sem tocar `/data`;
- C6.2.1 - smoke na placa de desenvolvimento, ainda somente em `/tmp`;
- C6.2.2 - guardrails para modo real do writer;
- C6.3-preflight - inspecao read-only da placa antes da escrita real;
- C6.3.0 - plano de execucao real com servico parado;
- C6.3A - primeira escrita real com servico parado;
- C6.4 - start controlado com config real e smoke curto;
- C6.5 - consolidacao documental do marco config real + `player_running`;
- C7.0 - contrato + snapshot local/offline de diagnostico/status sanitizado;
- C7.1 - futura validacao em placa read-only, se aprovada;
- C8 - Produto V1: operacao, onboarding e recuperacao;
- C8.1 - setup minimo funcional sem Wi-Fi real;
- C8.1.1 - handoff setup minimo -> contrato C5.1;
- C8.2 - selecao de ambiente mock/local, funcional/mock local;
- C8.3 - rotacao mock/local, funcional/mock local;
- C8.4.0 - manutencao minima mock/local e contrato de acoes;
- C8.4 - reset leve e reiniciar player, ainda pendente de acao real aprovada;
- C8.5.0 - preflight setup -> writer/config, local/offline em `/tmp`;
- C8.5.1 - origem de valores privados e candidata real-sintetica em `/tmp`;
- C8.5 - integracao com writer/config;
- C8.6 - handoff real controlado, ainda sem escrita real;
- C8.6.1 - limpeza segura da candidata privada temporaria;
- C8.7 - gate operacional final antes da escrita real;
- C8.8 - primeira escrita real integrada, sem start do player;
- C8.9 - start controlado pos-escrita real, smoke curto;
- C8.10 - reboot/autoboot controlado com config real;
- C9.0 - acesso temporario ao setup pela rede local existente;
- C9.1 - setup local na propria plaquinha;
- C9.1.1 - validacao humana do wizard local HDMI;
- C9.1.2 - diagnostico de proporcao visual pos-restauracao;
- C9.1.3 - contrato visual curto de display/orientacao;
- C9.2 - contrato de chamada do setup local pelo launcher;
- C9.2.1 - simulacao da decisao launcher/setup local;
- C9.3 - integracao experimental launcher/wizard em `config_missing`;
- C9.4 - Setup Produto Local V0;
- C9.4.1 - validacao HDMI humana e conclusao scripted;
- C9.5 - Wi-Fi real controlado com adapter estreito, plano inicial;
- C9 - Wi-Fi/portal/hotspot;
- C10 - manutencao/reset avancado.

Criterios de aceite:

- documento de arquitetura do onboarding aprovado;
- ameacas principais de privacidade e credenciais listadas;
- estados publicos e mensagens definidos;
- plano de teste inclui senha incorreta, rede ausente, reboot, Ethernet
  presente e ausencia de internet;
- plano preserva a separacao entre homologacao `v0.1-rc1`, desenvolvimento
  pos-RC1 e producao futura;
- Wi-Fi setup real, hotspot, portal local, ativacao backend e escrita real de
  config seguem nao implementados ao final de C2.

## Fases C1-C8 - onboarding minimo refinado

Status: C1-C6 avancaram como desenvolvimento incremental; C6.5 consolida config
real + `player_running`; C7.0 inicia diagnostico/status sanitizado
local/offline; C7.1 e C8 continuam planejadas. Homologacao e producao seguem
separadas.

Estas fases substituem a sequencia anterior mais ampla para evitar que hotspot,
ativacao backend, writer real, rotacao e manutencao avancem juntos.

### C1 - escopo e fluxo minimo documentado

Status: concluida/documentada.

Objetivo:

- documentar o caso `config_missing` com HDMI conectado;
- definir fluxo minimo Wi-Fi + `environment_id`;
- manter `api_key` fora da UI;
- registrar a maquina de estados minima;
- preservar C0/ADR-0008 como visao futura.

Aceite:

- documentos C1 e ADR-0009 criados;
- nenhum script, systemd, NetworkManager ou `kiosky-player` alterado;
- C1 marcada como desenvolvimento/proposta, sem liberar producao.

### C1.1 - coerencia documental C0/C1

Status: documental.

Objetivo:

- consolidar que C0/ADR-0008 sao visao original e futura;
- deixar C1/ADR-0009 como recorte vigente atual;
- preparar C2 sem apagar historico;
- explicitar que codigo curto, login, lista de ambientes e ativacao backend
  ficam para C7 ou fase posterior.

Aceite:

- C0 tem nota de leitura para trechos historicos;
- roadmap aponta para C2 como mock visual sem rede real;
- riscos cobrem o mock parecer funcional ou capturar dados reais.

### C2 - mock visual/formulario sem alterar rede

Status: preview visual/mock local em implementacao. Sem integracao
operacional.

Objetivo:

- criar preview visual/mock local para Wi-Fi e `environment_id`;
- nao listar redes reais;
- nao pedir senha real;
- nao persistir senha mock;
- nao alterar NetworkManager;
- nao escrever config real;
- nao criar portal funcional, servidor HTTP, hotspot ou QR funcional.

Validacao:

- previews e/ou mock local sem secrets;
- textos publicos claros para operador nao tecnico;
- renderer/setup continua separado do player;
- SVGs estaticos gerados localmente em `/tmp`;
- nenhuma integracao com rede real, config real, launcher operacional,
  renderer operacional ou `kiosky-player`.

### C3 - diagnostico Wi-Fi read-only

Status: diagnostico Wi-Fi read-only em implementacao/preparado. Sem alteracao
de rede.

Objetivo:

- criar base local sanitizada para observar estado de rede de forma apenas
  leitura;
- diferenciar Wi-Fi device presente, Wi-Fi conectado, IP local, rota default,
  DNS planejado, internet basica futura e backend futuro;
- nao derrubar Ethernet, Wi-Fi ou SSH de bancada;
- nao publicar SSID real, senha, IP local/publico, gateway, hostname, MAC,
  BSSID ou nome de conexao NetworkManager;
- nao executar teste externo de internet/backend por enquanto, salvo decisao
  posterior.

Validacao:

- prova de que nenhum comando altera conexoes;
- diagnostico sanitizado em `/tmp`, com permissoes restritas;
- comandos allowlisted e comandos proibidos testados por self-test;
- falhas aparecem como codigos publicos;
- Ethernet nao e desconectada ou modificada;
- nenhum artefato publica SSID, IP, senha, hostname, gateway ou nome de
  conexao.

### C4 - Wi-Fi real controlado em bancada

Status: C4.0 aprovado/documentado como plano de bancada; C4.1-preflight
documentado; primeira rodada C4.1 abortada com seguranca antes de inserir
senha; C4.1-postmortem concluido; C4.2 hibrido/local consolidou o modelo
humano fora do Codex, com C3 antes/depois/final e retorno humano sanitizado;
C4.3 define canal seguro de credencial como proximo passo de processo; canal
humano/local escolhido como SSH proprio fora do Codex; C4 hibrido validou
conexao Wi-Fi de teste por humano fora do Codex; C4.5 registrou remocao local
da configuracao de teste. C4 esta pausado/fechado temporariamente apos C4.5,
com backlog explicito em `docs/product/27_C4_WIFI_BACKLOG_E_GATES.md`.

Objetivo:

- planejar e depois testar alteracao real de Wi-Fi apenas em bancada;
- preservar Ethernet como recuperacao;
- usar C3 sanitizado antes/depois;
- documentar rollback de NetworkManager antes de executar;
- manter C4 fora de hotspot, portal local, config writer e producao.

Validacao:

- C4.0 documenta pre-condicoes, comandos candidatos, rollback, criterios de
  sucesso/aborto e evidencia esperada;
- C4.1-preflight documenta decisoes humanas finais, regra de senha sem registro
  e roteiro comando a comando sem execucao;
- C4.1 teve tentativa abortada com seguranca antes de inserir senha;
- C4.1-postmortem registrou que Codex/SSH/chat nao devem receber credencial;
- C4.1 nao deve passar senha por Codex, SSH remoto gerenciado pelo agente, chat,
  historico, script ou evidencia;
- C4.2 define o roteiro hibrido/local com Codex rodando C3 antes/depois/final e
  humano executando a etapa sensivel fora do agente;
- C4.2 consolidou o modelo hibrido/local, mantendo Codex fora da credencial e
  restrito a C3/evidencia sanitizada;
- C4.3 definiu canal humano/local seguro para inserir credencial: SSH proprio
  do humano fora do Codex;
- C4 hibrido validou conexao Wi-Fi de teste usando esse canal, mantendo Codex
  restrito a C3/evidencia sanitizada;
- C4.5 removeu o perfil/configuracao de teste por acao humana local e C3 final
  permaneceu saudavel;
- internet/backend continuam nao testados;
- Wi-Fi ainda nao e produto final;
- backlog futuro de Wi-Fi esta documentado em
  `docs/product/27_C4_WIFI_BACKLOG_E_GATES.md`;
- o avanco atual pode seguir por C5/C5.1/C6 sem assumir Wi-Fi como producao;
- antes de produto/campo, voltar aos gates C4 de reboot/reconexao, falhas
  controladas, adapter seguro, politica de credenciais, ciclo de vida de
  perfis e contrato de estados;
- senha errada ou falha de conexao recupera sem vazar credencial;
- Ethernet nao e derrubada indevidamente;
- rollback remove somente perfil de teste;
- reboot nao e criterio obrigatorio e NetworkManager nao pode ficar em estado
  ambiguo;
- nenhum hotspot, portal, config writer, `/data/config/config.json` ou player
  e alterado em C4.

### C5 - config writer mock

Status: base mock local concluida. Sem escrita real de config.

Objetivo:

- criar caminho de validacao de config minima sem substituir config ativa real;
- montar config candidata mock somente em `/tmp`;
- simular `api_key` fora da UI usando placeholder;
- manter `api_url` e `environment_id` como mock/placeholders;
- manter `station_id` apenas como mock opcional/futuro, sem bloquear a config
  minima;
- validar `environment_id` por formato minimo;
- preparar C6, mas sem executar C6.

Validacao:

- `--self-test` cobre `environment_id` valido/invalido, URL, path,
  token/secret, `--out-dir` fora de `/tmp` e escrita atomica;
- artefatos mock gerados em `/tmp/dadooh-c5-config-writer-mock`;
- diretorio com permissao `700` e arquivos com permissao `600`;
- nenhuma config parcial vira ativa;
- nenhuma escrita em `/data` ou `/data/config/config.json`;
- nenhum secret real, `api_url` privada, `environment_id` real ou payload de
  backend;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` permanecem
  fora do escopo;
- writer mock nao imprime secrets.

### C5.1 - contrato de config minima e validador dry-run

Status: contrato e validador dry-run local concluido. Sem escrita real de
config.

Objetivo:

- definir contrato minimo da config candidata;
- validar config candidata em dry-run;
- preparar C6 com bloqueio explicito de placeholders;
- impedir que config mock C5 vire config real;
- escrever apenas relatorio/status em `/tmp`;
- nao escrever, ler ou alterar `/data/config/config.json`.

Validacao:

- config mock C5 passa em `--allow-mock`;
- config mock C5 falha em `--real-dry-run` por placeholders;
- `--out-dir` fora de `/tmp` falha;
- campo obrigatorio ausente falha;
- path fora do contrato falha;
- `api_key` placeholder falha em `--real-dry-run`;
- status e summary nao imprimem valor de `api_key`;
- nada e escrito em `/data`;
- config real nao e lida;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` permanecem
  fora do escopo.

### C6 - config real com validacao e rollback

Status: C6.0 plano concluido; C6.1-preflight documental concluido; C6.2
writer real simulado em `/tmp` concluido localmente; C6.2.1 smoke na placa de
desenvolvimento em `/tmp` concluido; C6.2.2 guardrails de modo real concluidos;
C6.3A tentativa abortada por self-test do writer na placa; C6.2.3 correcao de
compatibilidade do self-test concluida; C6.3-preflight read-only na placa
concluido; C6.3.0 plano de execucao com servico parado concluido; C6.3A
execucao real concluida na placa de desenvolvimento com servico parado, backup
restrito e player mantido parado; C6.4 start controlado com config real
concluido como smoke curto de desenvolvimento; C6.5 consolidacao documental
criada.

Objetivo:

- gravar config minima real somente depois de C5;
- usar provisionamento local privado de `api_key`/token como caminho de
  desenvolvimento conforme ADR-0010;
- validar todos os campos obrigatorios antes de substituir;
- usar escrita atomica;
- preservar ultima config valida quando existir;
- iniciar player apenas depois de config valida.

Validacao:

- queda no meio nao deixa config parcial ativa;
- `api_key` externa ausente bloqueia salvamento ou inicio do player;
- renderer/setup para antes do player;
- rollback restauravel e documentado;
- C6.3A e C6.4 estao concluidos em desenvolvimento, nao homologacao.
- Observer prolongado, reboot/autoboot, segunda placa/cartao, root read-only,
  corte seco e rollback real acionado por falha foram movidos para fila de
  homologacao separada.

#### C6.0 - plano de writer real

Status: plano documental criado em
`docs/product/28_C6_0_CONFIG_WRITER_REAL_PLANO.md`. Sem escrita real.

Objetivo:

- planejar escrita real de `/data/config/config.json`;
- definir origem real da `api_key`/token por provisionamento local privado em
  desenvolvimento;
- definir ownership, permissoes, backup, rollback e criterio de falha;
- definir como queda de energia sera testada;
- definir criterio para launcher iniciar player somente com config valida;
- manter implementacao e execucao bloqueadas ate decisao humana sobre secrets,
  permissoes, rollback, queda de energia e evidencia.

Validacao:

- plano revisado antes de qualquer escrita em `/data`;
- rollback documentado;
- placa de desenvolvimento prevista no preflight e autorizada antes de C6.3A;
- evidencia esperada definida sem secrets;
- nenhuma config real lida, escrita ou alterada em C6.0.

#### C6.1-preflight - checklist e decisoes antes do writer real

Status: checklist documental criado em
`docs/product/29_C6_1_CONFIG_WRITER_REAL_PREFLIGHT.md`. Sem escrita real.

Objetivo:

- consolidar decisoes humanas obrigatorias antes de C6.2/C6.3A;
- definir politica de secrets para `api_key`/token, `api_url`, IDs reais,
  backup e evidencia;
- definir checklist tecnico antes de escrita real;
- separar implementacao futura do writer real de execucao futura em placa;
- definir pontos de abortar e estrategia para evitar inicio prematuro do
  player.

Validacao:

- nenhuma config real lida, escrita ou alterada;
- nenhum writer real implementado;
- nenhuma placa acessada;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player` fora do
  escopo;
- decisoes pendentes explicitadas antes de C6.2/C6.3A.

#### C6.2 - writer real simulado em /tmp

Status: implementado localmente em
`docs/product/30_C6_2_CONFIG_WRITER_REAL_SIMULADO.md` e
`scripts/board/totem_config_writer_real.py`. Sem escrita real em `/data`.

Objetivo:

- implementar writer real reutilizavel em modo simulado;
- manter testes e escrita somente em `/tmp` antes de qualquer placa;
- consumir candidata local de teste sem Codex ver token real;
- usar validador C5.1 em `--real-dry-run`;
- bloquear placeholders e ausencia de `api_key`;
- implementar escrita atomica, permissoes restritivas, backup e rollback
  simulados;
- preparar C6.3A sem tocar `/data/config/config.json`.

Validacao:

- self-test local sem tocar `/data`;
- candidata mock C5 falha em modo real;
- candidata sintetica nao-secret passa;
- destino fora de `/tmp` falha;
- backup-dir fora de `/tmp` falha;
- candidata sob `/data` ou `/opt` falha;
- escrita atomica gera config ativa simulada em `/tmp`;
- backup e rollback simulados cobertos pelo self-test;
- nenhum secret em stdout, log, summary, status ou evidencia;
- candidata sintetica, config ativa simulada, backup e status JSON de `/tmp`
  nao versionados;
- escrita real em `/data/config/config.json` continua bloqueada ate C6.3A.

#### C6.2.1 - smoke do writer simulado na placa

Status: smoke test concluido na placa de desenvolvimento. Ainda sem escrita
real em `/data`.

Objetivo:

- provar que o writer C6.2 roda no ambiente real da Orange Pi;
- copiar scripts somente para `/tmp`;
- criar candidata sintetica nao-secret na placa;
- executar self-tests na placa;
- executar writer com destino, backup-dir e out-dir sob `/tmp`;
- manter C6.3A separada para a escrita real em `/data`.

Validacao:

- self-test do validador C5.1 passou na placa;
- self-test do writer C6.2 passou na placa;
- writer simulado passou na placa;
- config ativa simulada foi criada em `/tmp` com permissao restritiva;
- status e summary nao publicaram `api_key`/token;
- nada foi escrito em `/data`;
- launcher, renderer, `systemd`, NetworkManager e `kiosky-player`
  permaneceram fora do escopo.

#### C6.2.2 - guardrails para modo real

Status: implementado localmente em
`docs/product/33_C6_2_2_WRITER_REAL_MODE_GUARDRAILS.md` e
`scripts/board/totem_config_writer_real.py`. Sem escrita real em `/data`.

Objetivo:

- manter modo padrao restrito a `/tmp`;
- adicionar flags explicitas para modo real futuro;
- permitir somente `/data/config/config.json` como destino real;
- restringir backup real a `/data/config/backups`;
- exigir candidata privada sob `/tmp` e fora do Git;
- testar guardrails sem executar escrita real.

Validacao:

- sem flags reais, destino `/data/config/config.json` falha;
- flags incompletas falham;
- com flags completas, path real aprovado passa apenas na validacao interna de
  guardrail durante self-test;
- destino real diferente falha;
- backup-dir real diferente falha;
- candidata em repositorio, `/data` ou `/opt` falha;
- modo simulado em `/tmp` continua passando;
- C6.3A continua sendo a primeira escrita real autorizada.

#### C6.2.3 - compatibilidade do self-test na placa

Status: concluido. Sem escrita real em `/data`.

Objetivo:

- diagnosticar falha do self-test do writer copiado para `/tmp` na placa;
- corrigir compatibilidade sem relaxar guardrails;
- revalidar localmente e na placa;
- manter C6.3A bloqueada ate nova revisao humana.

Validacao:

- causa identificada: teste de candidata em repo dependia do script estar
  dentro do checkout Git;
- correcao: detectar repo pelos pais da candidata e criar repo fake temporario
  em `/tmp` no self-test;
- self-test local do writer passou;
- self-test do writer na placa passou;
- escrita simulada em `/tmp` passou localmente e na placa;
- nada foi escrito em `/data`;
- servico nao foi parado, iniciado ou reiniciado;
- C6.2.3 permitiu repetir C6.3A desde a Fase 0 apos revisao humana.

#### C6.3-preflight - inspecao read-only da placa

Status: preflight read-only concluido na placa de desenvolvimento. Sem escrita
real em `/data`.

Objetivo:

- inspecionar usuario/grupo `totem` sem publicar arquivos completos do sistema;
- inspecionar existencia, tipo, mode e owner/group agregado de `/data`,
  `/data/config` e `/data/config/config.json`;
- confirmar legibilidade/escrita da config para `totem` sem ler conteudo;
- consultar estado do servico com comandos read-only;
- revisar a logica versionada do launcher;
- definir controle necessario antes da escrita real.

Validacao:

- `/data/config/config.json` existe e nao teve conteudo lido;
- config real nao foi escrita nem copiada;
- servico esta `enabled` e `active/running`;
- launcher usa `/data/config/config.json` por padrao e chama `run_app_once`
  quando a config e valida;
- recomendacao para C6.3A: executar com o servico parado ou bloqueio equivalente
  aprovado;
- C6.3A foi executada posteriormente com o servico parado.

#### C6.3.0 - plano de execucao com servico parado

Status: plano documental criado em
`docs/product/32_C6_3_EXECUCAO_CONFIG_REAL_SERVICO_PARADO.md`. Sem escrita real
em `/data` e sem tocar a placa.

Objetivo:

- transformar a recomendacao do preflight em plano de execucao real;
- exigir C6.3A com `kiosky-player.service` parado ou bloqueio equivalente;
- preservar backup e rollback antes da primeira escrita real;
- validar pos-escrita antes de qualquer decisao de iniciar player;
- manter decisao humana explicita para start do servico.

Validacao:

- C6.3-preflight read-only concluido e servico ativo/running detectado;
- escrita com servico ativo considerada bloqueada;
- sequencia futura documentada: preflight final, parada do servico, backup,
  candidata real privada, escrita atomica, pos-validacao, decisao de servico e
  evidencia sanitizada;
- C6.3A foi executada posteriormente com o servico parado.

#### C6.3A - primeira escrita real em placa de desenvolvimento

Status: concluida na placa de desenvolvimento. Player mantido parado ao final.

Objetivo:

- executar writer real aprovado apenas na placa de desenvolvimento;
- executar com `/data/config/config.json` real somente em fase separada;
- executar com `kiosky-player.service` parado ou bloqueio operacional
  equivalente aprovado;
- usar as flags reais de C6.2.2;
- validar escrita atomica, permissao e rollback;
- preservar ultima config valida quando existir;
- manter player bloqueado se a config falhar.

Validacao:

- execucao autorizada por humano apos C6.1-preflight, C6.2, C6.2.1, C6.2.2,
  C6.3-preflight e C6.3.0;
- `/data/config/config.json` escrito somente pelo writer real aprovado;
- `real-dry-run` e pos-validacao passaram;
- backup restrito foi criado em `/data/config/backups`;
- config ativa observada com owner/group `root:totem` e mode `0640`;
- usuario `totem` consegue ler e nao consegue gravar a config;
- rollback nao foi necessario;
- servico permaneceu parado ao final;
- player nao foi iniciado;
- evidencia sanitizada sem `api_key`, URL privada, IDs reais ou payload.

#### C6.4 - start controlado com config real

Status: concluido como smoke curto de desenvolvimento. Nao e homologacao e nao
libera producao.

Objetivo:

- iniciar `kiosky-player.service` controladamente com a config real escrita em
  C6.3A;
- observar launcher/player por 120s;
- confirmar `player_running` sem ler a config real;
- manter evidencia sanitizada.

Validacao:

- servico iniciou e permaneceu `active/running`;
- status publico chegou a `player_running`;
- playback ficou `playing`;
- MPV e `kiosk.py` ficaram ativos;
- `NRestarts=0` no observer curto;
- renderer junto com player nao foi observado na checagem final;
- servico foi mantido rodando ao final da rodada;
- nenhum secret, `api_url` real, ID real, payload, log bruto ou conteudo de
  config foi publicado.

Limite:

- C6.4 nao provou estabilidade 30-60 min, varias horas, reboot/autoboot,
  segunda placa/cartao, API indisponivel, rede oscilando, cache/offline longo,
  root read-only, corte seco, rollback real acionado por falha ou producao.

#### C6.5 - consolidacao do marco

Status: documentado em
`docs/product/34_C6_5_MARCO_CONFIG_REAL_PLAYER_RUNNING.md`.

Objetivo:

- consolidar C6 como marco de desenvolvimento;
- registrar o que C6.3A/C6.4 provaram e o que nao provaram;
- separar desenvolvimento, homologacao e producao;
- mover testes longos para
  `docs/product/35_FILA_HOMOLOGACAO_TESTES_LONGOS.md`.

Proximos caminhos possiveis, sem decisao automatica:

- C7 status/diagnostico de config real e appliance;
- C8 rollback/parada controlada;
- UX/setup/onboarding;
- `player_error`;
- integracao writer/onboarding;
- update/rollback;
- fila de homologacao.

### C7 - diagnostico/status sanitizado do appliance

Status: C7.0 contrato + snapshot local/offline criado em
`docs/product/36_C7_DIAGNOSTICO_STATUS_APPLIANCE.md`. C7.1 permanece futura.

Objetivo:

- criar contrato de diagnostico/status sanitizado do appliance;
- permitir entender estado publico de config, servico, launcher, player, MPV,
  renderer e privacidade sem ler conteudo de config real;
- tratar `/tmp/kiosky-status.json` como status bruto do player, lendo apenas
  campos allowlisted;
- observar `/data/config/config.json` somente por metadados, sem abrir o
  arquivo;
- gerar snapshot e resumo restritos em `/tmp`;
- preparar futura validacao read-only em placa.

Subfases:

- C7.0 - contrato + script local/offline
  `scripts/board/totem_appliance_status_snapshot.py`, com self-test por
  fixtures sinteticas em `/tmp`;
- C7.1 - futura validacao em placa read-only, se aprovada por roteiro proprio,
  sem journal bruto e sem publicar dados privados.

Validacao C7.0:

- self-test com fixtures contendo dados privados em campos desconhecidos;
- campo allowlisted suspeito redigido ou marcado com `privacy_scan=failed`;
- conteudo de config nao lido e `config_file_content_read=false`;
- out-dir fora de `/tmp` recusado;
- fontes ausentes viram `unavailable`/`unknown`;
- nenhum JSON bruto, log bruto, URL privada, payload, path privado, ID real,
  SSID, IP, hostname ou credencial e publicado.

Limite:

- C7 nao substitui observer prolongado, reboot/autoboot, segunda placa/cartao,
  root read-only, corte seco, rollback real ou homologacao;
- processos e `systemd` continuam fora de C7.0;
- a antiga frente de ativacao por codigo, login ou lista de ambientes fica para
  fase futura de UX/setup/onboarding, nao para este C7.

### C8 - Produto V1: operacao, onboarding e recuperacao

Status: visao documental criada; C8.1/C8.1.1/C8.2/C8.3/C8.4.0/C8.5.0/C8.5.1
funcional/mock local, preflight local ou sintetico local concluidos sem Wi-Fi
real, sem config real e sem acao real de manutencao.

Documentos:

- `docs/product/37_PRODUTO_V1_OPERACAO_ONBOARDING_RECUPERACAO.md`;
- `docs/product/38_FLUXO_PRODUTO_V1_ONBOARDING_MANUTENCAO_RECUPERACAO.md`;
- `docs/product/39_INVENTARIO_TELAS_ACOES_PRODUTO_V1.md`;
- `docs/product/40_MATRIZ_RESET_RECUPERACAO_PRODUTO_V1.md`;
- `docs/product/41_C8_1_SETUP_MINIMO_FUNCIONAL_SEM_WIFI_REAL.md`;
- `docs/product/42_C8_1_1_HANDOFF_SETUP_CONTRATO_CONFIG.md`;
- `docs/product/43_C8_2_SELECAO_AMBIENTE_MOCK_LOCAL.md`;
- `docs/product/44_C8_3_ROTACAO_MOCK_LOCAL.md`;
- `docs/product/45_C8_4_0_MANUTENCAO_MINIMA_MOCK_LOCAL.md`;
- `docs/product/46_C8_5_0_PREFLIGHT_SETUP_WRITER_CONFIG.md`;
- `docs/product/47_C8_5_1_ORIGEM_VALORES_PRIVADOS_CANDIDATA_REAL_SINTETICA.md`;
- `docs/product/48_C8_5_2_STATION_ID_OPCIONAL_CONTRATO_MINIMO.md`;
- `docs/product/49_C8_6_PREFLIGHT_HANDOFF_REAL_CONTROLADO.md`;
- `docs/product/50_C8_6_1_LIMPEZA_CANDIDATA_PRIVADA_TEMPORARIA.md`;
- `docs/product/51_C8_7_GATE_OPERACIONAL_FINAL_PRE_ESCRITA_REAL.md`;
- `docs/product/52_C8_8_PRIMEIRA_ESCRITA_REAL_INTEGRADA.md`;
- `docs/product/53_C8_9_START_CONTROLADO_POS_ESCRITA_REAL.md`;
- `docs/product/54_C8_10_REBOOT_AUTOBOOT_CONFIG_REAL.md`;
- `docs/product/55_C9_0_ACESSO_TEMPORARIO_SETUP_REDE_LOCAL.md`;
- `docs/product/56_C9_1_SETUP_LOCAL_PROPRIA_PLAQUINHA.md`;
- `docs/product/57_C9_1_1_VALIDACAO_HUMANA_WIZARD_LOCAL_HDMI.md`;
- `docs/product/58_C9_1_2_DIAGNOSTICO_PROPORCAO_VISUAL_POS_RESTAURACAO.md`;
- `docs/product/prototypes/v1-operacao-recuperacao/index.html`;
- `docs/product/prototypes/c8-1-setup-minimo/index.html`;
- `docs/product/prototypes/c8-2-selecao-ambiente/index.html`;
- `docs/product/prototypes/c8-3-rotacao/index.html`;
- `docs/product/prototypes/c8-4-manutencao-minima/index.html`.

Objetivo:

- consolidar a visao holistica de produto para operador nao tecnico;
- cobrir onboarding, operacao, manutencao, reset e recuperacao em campo;
- tratar rotacao, troca de ambiente e setup como jornada de produto, nao como
  comandos de bancada;
- separar camadas de recuperacao: automatica, operador, reset local fisico e
  restauracao de sistema;
- orientar MVP funcional e V1 final sem substituir homologacao.

Subfases propostas:

- C8.1 - setup minimo funcional sem Wi-Fi real, mock/local em `/tmp`;
- C8.1.1 - handoff setup minimo -> contrato C5.1;
- C8.2 - selecao de ambiente mock/local;
- C8.3 - rotacao mock/local, funcional/mock local;
- C8.4.0 - manutencao minima mock/local e contrato de acoes;
- C8.4 - reset leve e reiniciar player, ainda pendente de acao real aprovada;
- C8.5.0 - preflight setup -> writer/config, local/offline em `/tmp`;
- C8.5.1 - origem de valores privados e candidata real-sintetica em `/tmp`;
- C8.5.2 - `station_id` opcional e fora do caminho critico;
- C8.5 - integracao com writer/config;
- C8.6 - handoff real controlado, ainda sem escrita real;
- C8.6.1 - limpeza segura da candidata privada temporaria;
- C8.7 - gate operacional final antes da escrita real;
- C8.8 - primeira escrita real integrada, sem start do player;
- C8.9 - start controlado pos-escrita real, smoke curto;
- C8.10 - reboot/autoboot controlado com config real;
- C9.0 - acesso temporario ao setup pela rede local existente.
- C9.1 - setup local na propria plaquinha, tela HDMI + teclado USB.
- C9.1.1 - validacao humana do wizard local HDMI com teclado USB.
- C9.1.2 - diagnostico de proporcao visual pos-restauracao.

Validacao:

- nenhuma acao executa shell arbitrario;
- player nao e interrompido sem estado publico claro;
- diagnostico segue sanitizado;
- reset preserva ou apaga dados conforme escopo aprovado.

Limites:

- C8 documental nao altera NetworkManager, hotspot, portal, launcher,
  renderer, `systemd` ou `kiosky-player`;
- C8 documental nao escreve config real;
- C8 documental nao executa reset real;
- C8.1 pode ser validada na placa somente por smoke seguro em `/tmp`, sem
  servicos, sem rede operacional e sem player.

### C9.0 - acesso temporario ao setup pela rede local existente

Status: executado em desenvolvimento. Nao e servico permanente.

Objetivos:

- rodar o setup C8 temporariamente na placa;
- expor o setup em uma porta definida na rede local de bancada existente;
- permitir validacao humana da UX pelo navegador, fora do terminal;
- gerar candidata apenas em `/tmp`;
- encerrar o servidor ao final;
- preservar evidencia sanitizada.

Fora de escopo:

- Wi-Fi real;
- hotspot;
- portal definitivo;
- NetworkManager ou `nmcli`;
- writer/config real;
- `/data/config/config.json`;
- backups;
- parada/start de `kiosky-player.service`;
- alteracao do repo `kiosky-player`;
- producao.

### C9.1 - setup local na propria plaquinha

Status: implementado em desenvolvimento. Nao e producao.

Objetivos:

- provar o caminho obrigatorio de setup pela propria tela HDMI do totem;
- operar com teclado USB, sem Chromium, desktop, compositor ou shell livre;
- selecionar ambiente mock/local;
- selecionar orientacao da tela;
- revisar antes de gerar candidata;
- gerar candidata apenas em `/tmp`;
- validar C5.1 `allow-mock`;
- confirmar falha esperada de C5.1 `real-dry-run` por placeholders;
- preservar status/summary sanitizados.

Fora de escopo:

- writer/config real;
- `/data/config/config.json`;
- backups;
- parada/start de `kiosky-player.service`;
- player/MPV;
- NetworkManager, `nmcli`, Wi-Fi real, hotspot ou QR;
- backend;
- producao.

### C9.1.1 - validacao humana do wizard local HDMI

Status: passou tecnicamente com ressalvas de UX e warning visual
pos-restauracao. Nao e producao.

Objetivos:

- rodar o wizard local na placa com HDMI e teclado USB;
- validar legibilidade, navegacao e entendimento do fluxo por humano;
- gerar candidata somente em `/tmp`;
- preservar evidencia sanitizada;
- restaurar estado combinado se houver parada temporaria autorizada do player.

Fora de escopo:

- integracao com launcher;
- chamada automatica em `config_missing`;
- writer/config real;
- `/data/config/config.json`;
- backups;
- mudanca permanente de servico/player;
- NetworkManager, `nmcli`, Wi-Fi real, hotspot ou QR;
- backend;
- producao.

### C9.1.2 - diagnostico de proporcao visual pos-restauracao

Status: concluido como diagnostico controlado. Nao e producao.

Objetivos:

- separar stop/start do servico, wizard/openvt e modo de video como causas
  possiveis da percepcao de midia esticada;
- coletar snapshots sanitizados de servico, processos, TTY, framebuffer, DRM e
  propriedades MPV allowlisted;
- manter config real, writer, player repo, rede e Wi-Fi intocados.

Resultado:

- Fase A read-only mostrou que a midia ja parecia esticada;
- Fase B stop/start controlado nao mudou a percepcao;
- servico terminou `active/enabled`, `NRestarts=0`, player=1, MPV=1,
  renderer=0;
- modos HDMI observados nao incluiam Full HD;
- permanece recomendada uma frente futura de contrato visual/seletor por tipo
  de tela.

Fora de escopo:

- mudar resolucao;
- alterar flags MPV;
- alterar config real;
- rodar writer;
- repetir wizard/openvt sem nova autorizacao;
- liberar producao.

### C9 - Wi-Fi/portal/hotspot

Status: planejada.

Objetivo:

- retomar os gates C4 de Wi-Fi antes de transformar conectividade em produto;
- implementar Wi-Fi setup, portal local e/ou hotspot somente depois de adapter
  seguro, politica de credenciais, rollback e evidencia sanitizada;
- manter credenciais fora do Codex, logs, status publico e diagnostico;
- separar Wi-Fi local, internet e backend nas mensagens ao operador.

Validacao:

- falhas controladas de senha, rede ausente, timeout e conexao limitada;
- rede anterior preservada ate nova conexao passar, quando aplicavel;
- Ethernet preservada em bancada;
- nenhum SSID, senha, IP, hostname, MAC, BSSID, gateway ou DNS real em
  evidencia.

### C10 - manutencao/reset avancado

Status: planejada.

Objetivo:

- implementar manutencao protegida, factory reset, hard reset local, rollback
  de app e restauracao avancada;
- escolher metodo fisico de hard reset;
- impedir que reset vire shell;
- preservar ou exportar diagnostico sanitizado antes de apagamentos
  destrutivos, conforme politica;
- integrar com update/rollback e recovery image quando essas fases estiverem
  prontas.

Validacao:

- matriz de reset aprovada antes de implementacao;
- confirmacao forte em reset destrutivo;
- factory reset retorna para setup sem expor segredo;
- hard reset local e acionavel em campo e dificil de disparar por acidente;
- rollback/restauracao tem healthcheck publico e caminho de retorno.

## Fase F - monitoramento/telemetria

Objetivo:

- reportar estado online;
- uptime;
- temperatura;
- disco;
- versao app;
- versao imagem;
- ultimo erro;
- `display_missing`.

Arquivos provaveis:

- agregador de status do appliance;
- contrato de payload de telemetria;
- spool opcional em `/data/spool/totem`;
- extensao do diagnostico sanitizado;
- config de telemetria sem token hardcoded.

Validacao minima:

- payload nao contem secrets, URLs privadas ou paths reais de midia;
- sem internet, telemetria falha sem afetar player;
- retorno da internet retoma envio;
- `display_missing`, disco cheio, temperatura alta e ultimo erro aparecem no
  estado agregado.

Riscos:

- vazamento de dados privados;
- telemetria gerar escrita excessiva;
- token de telemetria mal provisionado;
- backend interpretar estados de forma diferente do totem.

Criterios de aceite:

- dashboard/backend consegue distinguir online, offline, sem HDMI, sem config e
  erro de player;
- falha de telemetria nao reinicia player.

Criterio de rollback:

- desligar telemetria do appliance por config e manter status local/diagnostico.

## Fase G - update/rollback

Objetivo:

- armazenar releases em `/opt/totem/releases`;
- usar symlink ativo;
- permitir rollback.

Arquivos provaveis:

- `/opt/totem/releases/<versao>`;
- `/opt/totem/current`;
- unit apontando para symlink ativo;
- comando de update controlado;
- manifesto de release;
- estado de rollback em `/data/state/totem`.

Validacao minima:

- instalar nova release sem alterar `/data/config`;
- healthcheck pos-update passa antes de confirmar;
- rollback volta a release anterior;
- falha no boot retorna para release anterior ou entra em manutencao.

Riscos:

- symlink quebrado deixar player fora;
- update parcial em queda de energia;
- incompatibilidade entre config antiga e app novo;
- falta de espaco em `/opt` ou `/data`.

Criterios de aceite:

- update e rollback funcionam sem terminal;
- versao app/imagem aparecem no status;
- corte de energia durante update nao corrompe release ativa.

Criterio de rollback:

- apontar symlink ativo para release anterior validada e reiniciar servico.

## Fase H - root read-only/corte seco

Objetivo:

- ativar root read-only depois de logs, cache e config estabilizados;
- validar corte seco em condicoes controladas.

Arquivos provaveis:

- overlay/customizacao da imagem;
- ajustes de `/var/log`, `/tmp` e `/data`;
- units de montagem;
- documentacao de teste de corte seco;
- politicas de log/cache.

Validacao minima:

- boot normal com root protegido;
- player grava somente em `/data` e `/tmp`;
- diagnostico confirma ausencia de escrita inesperada em root;
- ciclos de desligamento abrupto nao causam erro EXT4, remount read-only ou
  perda de config;
- factory reset continua funcionando.

Riscos:

- caminho mutavel esquecido em root;
- diagnostico/logs insuficientes para suporte;
- reset/update incompatibilizar com root read-only;
- teste de corte seco antes da hora mascarar causa de falha.

Criterios de aceite:

- sistema volta a operar apos cortes repetidos;
- `/data` contem todo estado mutavel necessario;
- rollback/update/reset continuam testados.

Criterio de rollback:

- voltar imagem para root gravavel de bancada e corrigir paths mutaveis antes de
  repetir corte seco.


Atualizacao C11.3.2: 2026-05-06. C11.3.2 recuperou a dev offline depois de uma
falha contaminada por alimentacao via USB da TV (`POWER_SUPPLY_CONFOUNDED`) e
repetiu o enablement com fonte dedicada. O SSH voltou, o player permaneceu
`player_running`/`playing`, mas `overlayroot` nao ativou: `read_only_enabled=false`
e `overlay_active=false`. Rollback final deixou a dev em modo normal. C11.4
continua bloqueado; a proxima estrategia de read-only deve ser testada em cartao
separado ou na imagem/base C12.

Atualizacao C11.3.3: 2026-05-06. C11.3.3 preservou a dev e usou a placa teste
como laboratorio de `overlayroot`. O prerequisito foi instalado na teste apos
dry-run seguro (`would_upgrade_count=0`, `would_remove_count=0`, pacotes
kernel/DTB/U-Boot/BSP intocados). O enable e reboot na teste voltaram por SSH,
mas `read_only_enabled=false` e `overlay_active=false`; a causa sanitizada foi
`initramfs_log_driver_lookup_failed=true`. Rollback executado. C11.4 permanece
bloqueado; a proxima estrategia de read-only deve ser investigada em laboratorio
ou em imagem/base C12, nao na dev funcional.

Atualizacao C11.3.4: 2026-05-06. C11.3.4 nao alterou as placas e registrou a
ADR-0011. A decisao e mover o proximo experimento para C12.0-prep:
`root_read_only_mechanism_decision=c12_image_integrated_overlay_lab_required`.
Read-only, C11.4 e corte seco continuam bloqueados.

Atualizacao C12.0-prep: 2026-05-06. C12.0-prep criou o plano de imagem-lab com
read-only integrado ao build, em vez de enablement pos-instalacao. Status:
`image_built=false`, `card_written=false`, `boards_touched=false`,
`ready_for_c12_1_build=true`, `ready_for_c12_2_board_validation=false` e
`ready_for_c11_4=false`.

Atualizacao C12.1: 2026-05-06. C12.1 preparou Armbian Build v25.11 em
`e172058`, versionou userpatches C12 e gerou a imagem-lab
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img`.
O build confirmou `overlayroot_included=true` e
`initramfs_generated_after_overlayroot=true`. O proximo passo permitido e C12.2:
gravar cartao de teste e validar boot/read-only na placa teste.

Atualizacao C12.1.1: 2026-05-07. O artefato C12.1 foi revalidado no caminho
esperado com SHA256
`1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2`. O incidente
fisico no cartao dev bloqueia uso da dev como alvo imediato; C12.2 deve preparar
cartao de teste seguro e usar a placa teste.

Atualizacao C12.1.2: 2026-05-07. A imagem-lab foi reconstruida com os fixes de
sessao F10, firstboot gate e read-only assertion. A nova imagem e
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img`,
SHA256 `a398399c139c3fee1b05860b216db7facfddd0ae1a57f681b229228390b7abd9`.
Ela substitui a C12.1 para a proxima gravacao C12.2.1; nenhuma placa foi tocada
e nenhum cartao foi gravado nesta rodada.

Atualizacao C12.3.13: 2026-05-08. A imagem C12.1.10 foi diagnosticada na placa
lab com um unico reboot de initramfs. O hook temporario foi removido por
rollback. Read-only continua bloqueado: `read_only_enabled=false`,
`overlay_active=false`, `root_write_blocked=false`. A causa foi refinada para
`OVERLAY_MODULE_EMPTY_OR_STUB_IN_INITRAMFS`: o path dinamico encontrou um
`overlay.ko`, mas o artefato no initramfs estava vazio e `modules.dep` nao
referenciava `overlay`. A tela preta `config_missing` foi observada durante o
diagnostico, mas depois foi identificada pelo operador como problema de hardware
da tela e resolvida fora do software. C12.4 permanece bloqueado pelo read-only;
o proximo passo e C12.1.11 para rebuild do modulo overlay no initramfs.

Atualizacao C12.3.14: 2026-05-08. Antes de novo build completo, a placa lab
descartavel foi usada para testar empacotamento real do modulo `overlay` no
initramfs. H1 (`manual_add_modules overlay`) e H2 (copia explicita dinamica do
modulo real e metadata) passaram na validacao pre-boot:
`overlay_module_nonempty_in_initramfs=true`,
`modules_dep_references_overlay=true` e `uinitrd_regenerated=true`. Ambas
falharam apos reboot: `read_only_enabled=false`, `overlay_active=false`,
`root_write_blocked=false`, root `ext4`. Rollback foi executado em cada ciclo.
A classificacao atual e
`OVERLAY_MODULE_PACKAGING_FIXED_BUT_LOAD_STILL_FAILS`. C12.4 segue bloqueado, e
o proximo passo recomendado e diagnosticar a falha de carregamento com modulo
nao vazio antes de qualquer rebuild C12.1.11.

Atualizacao C12.3.15: 2026-05-08. O hook temporario confirmou que o modulo
`overlay` real esta presente e nao vazio no initramfs, sem dependencias
declaradas e com `vermagic` compativel no ambiente pos-boot. No runtime do
initramfs, `modprobe overlay` retorna zero mas nao registra `overlay` em
`/proc/filesystems`, e `insmod overlay.ko` retorna nonzero sem stderr/dmesg
categorizavel. Root segue `ext4` gravavel e `systemctl_failed_count=0`.
Classificacao: `INITRAMFS_MODULE_LOADING_UNSUPPORTED`. C12.4 e C12.1.11 ficam
bloqueados; o proximo passo e reabrir a decisao do mecanismo read-only em ADR,
avaliando kernel/base com overlay built-in ou mecanismo alternativo.

Atualizacao C12.3.16: 2026-05-08. A decisao read-only foi atualizada pela
ADR-0012: encerrar a linha `overlayroot` via `overlay.ko` carregado como modulo
no initramfs e manter `overlayroot` com o proximo experimento em kernel
`CONFIG_OVERLAY_FS=y` built-in. O build C12.1.11 deve gerar userpatch completo
`linux-sunxi64-current.config` a partir da config Armbian e alterar
`CONFIG_OVERLAY_FS` para `y`. Os criterios de validacao tambem mudam: o root
aparente pode ser gravavel sob overlayroot, entao sucesso exige `overlay_active`
e prova de persistencia correta: escrita fora de `/data` nao persiste apos
reboot, enquanto escrita em `/data` persiste. C12.4 continua bloqueado.

Atualizacao C12.1.11: 2026-05-08. O pre-flight do build com
`CONFIG_OVERLAY_FS=y` passou, usando config completa `linux-sunxi64-current` e
modo `private_disposable_lab` para permitir validacao SSH futura sem publicar o
conteudo do firstboot privado. O kernel `6.12.58-sunxi64` compilou e foi
empacotado, mas a geracao da imagem falhou na fase de rootfs/image por erro de
memoria no `apt-get update` dentro do chroot da imagem
(`BUILD_HOST_CHROOT_APT_MEMORY_ERROR`). Nao houve imagem, checksum ou manifest
final C12.1.11. Nenhuma placa foi tocada, nenhum cartao foi gravado e nenhum
writer/config real foi usado. C12.2.7 e C12.4 continuam bloqueados ate repetir
o build e obter artefato validado offline.

Atualizacao C12.1.12: 2026-05-08. O retry preservou caches e reaproveitou os
pacotes de kernel ja compilados com `CONFIG_OVERLAY_FS=y`; nao houve
recompilacao longa do kernel. O blocker de `apt-get update` no chroot foi
superado e a imagem C12.1.12 foi gerada:
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-12_minimal.img`.
SHA256:
`1220aab2272b5e6fa3430b6aab1c180624441104ab6b4ab7a1a1932fc8373a81`.
A validacao offline passou com `overlayroot_included=true`,
`kernel_config_overlayfs_builtin=true`, `overlay_module_required=false`,
`uinitrd_nonempty=true`, `effective_boot_initramfs_valid=true` e hooks antigos
de fallback/diagnostico ausentes. Nenhuma placa foi tocada e nenhum cartao foi
gravado. C12.2.7 pode gravar cartao de teste; C12.4 continua bloqueado ate boot
real provar a semantica read-only.

Atualizacao C12.3.17: 2026-05-08. A imagem C12.1.12 foi gravada e bootada em
placa lab, e o inspect remoto foi executado. O kernel em runtime confirma
`CONFIG_OVERLAY_FS=y`, `overlay` aparece em `/proc/filesystems` e
`overlayroot=tmpfs` chega ao cmdline/config. Mesmo assim, o root ainda monta
como `ext4` em device fisico, com `overlay_active=false`. Por isso nenhum
marcador de persistencia foi criado e nenhum reboot foi executado. C12.4
continua bloqueado; o proximo passo e diagnosticar o fluxo
`overlayroot`/initramfs/boot com overlayfs built-in, nao voltar para a linha de
modulo `overlay.ko`.

Atualizacao C13.1.2: 2026-05-08. Sem reabrir a frente read-only, foi adicionado
suporte a seed privada de homologacao para imagem-lab privada. O build agora
aceita `C13_EMBED_HOMOLOG_PRIVATE_VALUES=1`,
`C13_HOMOLOG_PRIVATE_VALUES=<arquivo fora do repo>` e
`C13_CONFIRM_PRIVATE_HOMOLOG_IMAGE=1`, validando permissao/categorias sem
publicar valores e instalando a seed em
`/data/state/totem-settings/private-values.seed.json` com modo `0600`. O F10
passa a ativar automaticamente policy real-write quando a seed existe; sem seed,
permanece candidate-only. O hotfix foi validado na placa lab com seed privada
fora do repo: `writer_called=true`, `real_config_written=true`,
`public_state=player_running` e `playback=playing`, sem publicar segredos. A
imagem privada de homologacao ainda nao foi gerada neste commit; status:
`ready_for_c13_1_2_private_image_build=true`, `final_image=false`,
`artifact_private=true`, `c12_4_blocked=true`.

Atualizacao C13.1.3: 2026-05-08. Foi gerada a imagem privada de homologacao
`Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c13-1-3-homolog-private_minimal.img`,
com SHA256
`3a76d51880d944fe5430782ad2cf84866573c219cdf6a719c004e38c5c2fe6eb`.
A seed privada foi embutida somente no artefato privado, em
`/data/state/totem-settings/private-values.seed.json`, com modo `0600`, sem
publicar conteudo. `totem-open-settings.service` nao depende mais de arquivo
manual em `/tmp` para homologacao; a policy runtime vem da seed aprovada. A
validacao offline passou com `artifact_private=true`, `final_image=false`,
`not_for_production=true`, `not_for_distribution=true`,
`tmp_private_values_dependency=false`, `card_written=false`,
`boards_touched=false` e `ready_for_multi_card_homologation=true`. C12
read-only e C12.4 continuam bloqueados.

Atualizacao C14.1.1: 2026-05-11. C14.1.1 entregou o MVP de pull deploy via
GitHub Releases para o app `kiosky-player`, sem `git pull` na placa e sem
Mender/RAUC/SWUpdate. Builder gera `tar.gz` + manifest `dadooh.totem.update.v1`
e publica como prerelease com `gh CLI`; placa baixa via HTTPS (Python stdlib),
valida SHA256, extrai em `/data/apps/kiosky-player/releases/<v>/`, troca symlink
`current` atomicamente, reinicia `kiosky-player.service` e faz health check com
auto-rollback. Rollback manual testado fim-a-fim (apply v2, rollback para v1,
servico `active`). `totem-update-agent.timer` instalado mas `disabled` por
decisao. Nenhum `apt`/`pip`/kernel/u-boot/dtb/bsp/rootfs tocado. Status:
`c14_1_1_status=passed`, `device_bootstrapped=true`, `rollback_tested=true`,
`secrets_published=false`, `c12_readonly_blocked=true`, `c12_4_blocked=true`.
Detalhes em `docs/product/135_C14_1_1_GITHUB_RELEASES_PULL_DEPLOY_MVP.md`.

Atualizacao C14.2.1: 2026-05-11. Imagem privada de homologacao de despacho
que embute o updater C14.1.1 e habilita `totem-update-agent.timer` na propria
imagem, para evitar bootstrap SSH por placa em gravacao de lote. Diff em
relacao a C13.1.3 e exclusivamente adicao de
`/opt/totem/bin/totem-updatectl`, `/opt/totem/bin/totem-kiosky-launcher.sh`,
drop-in `kiosky-player.service.d/20-dadooh-launcher.conf`,
`totem-update-agent.service` (static), `totem-update-agent.timer` (enabled,
`OnBootSec=10min`/`OnUnitActiveSec=6h`/`RandomizedDelaySec=10min`) e dirs
`/data/apps/kiosky-player/{releases,}` e `/data/updates/incoming/`.
Sem mudanca em kernel/U-Boot/DTB/BSP/rootfs base. Build reaproveita cache
do Armbian Build (sem recompilar kernel). Seed privada continua em
`/data/state/totem-settings/private-values.seed.json` 0600 root:root.
Rollback nao retestado (provado em C14.1.1). Status:
`artifact_private=true`, `final_image=false`, `homologation_shipping_image=true`,
`not_for_production=true`, `not_for_distribution=true`,
`pull_updater_embedded=true`, `pull_update_timer_enabled=true`,
`c12_readonly_blocked=true`, `c12_4_blocked=true`. Detalhes em
`docs/product/136_C14_2_1_SHIPPING_HOMOLOGATION_IMAGE_WITH_PULL_UPDATER.md`.

Atualizacao C15.1.1: 2026-05-12. Estabilizacao minima e reversivel do
wizard F10 + auditoria do player sem refatoracao. Causa-raiz do "wizard
volta para config_missing" classificada como
`service_race_with_config_missing`: o wait de 30s em
`totem_open_settings_session.sh` por drenagem de `kiosk.py`/`mpv`/launcher
falhava ocasionalmente nas primeiras tentativas, disparando
`exit 42 hdmi_not_free_after_player_pause` antes do wizard renderizar.
Hotfix: escalonar para SIGKILL apos o grace period antes do `exit 42`
final. Causa do "terminal aparece" no primeiro boot classificada como
`renderer_starts_too_late` (printf cru em `/dev/tty2` no
`totem_firstboot_gate.sh` antes do splash python; janela curta apos
`openvt` antes do `tty.setraw` do wizard). Hotfix aplicado em
`/opt/totem/bin/totem_open_settings_session.sh` da placa lab (tmpfs
overlay, sem reboot) com sha256 verificado. Player audit: classificacoes
de `player_timing_suspect=default_duration_used,sync_resync_conflict,mpv_ipc_loadfile_failure`,
sem alterar `kiosk.py` ou `/data/config/config.json`. Proxima rodada
recomendada: C16.1.1 (player scheduler/sync). Nenhum
`apt`/`pip`/kernel/u-boot/dtb/bsp/wifi alterado. Nenhum poweroff/corte
seco. Nenhum secret publicado. Status: `c15_1_1_status=in-progress`
(awaiting on-board F10 confirmation), `wizard_hotfix_deployed=true`,
`image_rebuild_required=true` (para persistir alem de reboot),
`player_code_changed=false`, `c12_readonly_blocked=true`,
`c12_4_blocked=true`. Detalhes em
`docs/product/137_C15_1_1_WIZARD_FIRSTBOOT_AND_PLAYER_TIMING_AUDIT.md`.

Confirmacao C15.1.1: 2026-05-13. Teste fisico #1 (10:03Z) falhou com
`Main process exited, code=killed, status=15/TERM` sem rastro suficiente
para atribuir o SIGTERM a um subsistema especifico. Aplicado hotfix v2
de instrumentacao em `totem_open_settings_session.sh` (helper `c15_trace`
gravando em `/tmp/c15-session.trace`; traps separados `on_term`/`on_int`/
`on_hup` para registrar qual sinal chegou). Sem mudanca de comportamento.
Teste fisico #2 (10:25Z) passou fim-a-fim: 6 telas (orientation,
orientation-confirm, 02-connection, 03-environment, 05-review,
06-complete) renderizadas, `writer_called=true writer_rc=0
writer_result=passed real_config_written=true backup_created=true`,
`setup_cancelled=false`, `linux_prompt_visible=false`, player restaurado
ao final. session.sh agora em sha256
`8484338d9d5a9abbab7ab6e80ad92d1a00dff83d938908edfda04c1cbf93d3f8` na
placa (tmpfs overlay) e no repo. **C15.1.1 NAO esta fechado**: 1 de 2
testes passou, causa de SIGTERM do #1 segue nao classificada, hotfix v1
(SIGKILL escalation) nao foi exercitado em nenhuma das duas execucoes
(player drenou em 2s nas duas). Status real:
`c15_1_1_status=partial-validated`, `c15_1_1_closure=pending_C15_1_2`,
`wizard_hotfix_deployed=true`, `wizard_instrumentation_deployed=true`,
`on_device_tests=1_of_2_passed`, `unclassified_failures=1`,
`image_rebuild_required=true` (somente apos C15.1.2 fechar).
`secrets_published=false`, `apt_update_executed=false`,
`apt_upgrade_executed=false`, `pip_install_executed=false`,
`poweroff_executed=false`, `power_cut_tested=false`,
`c12_readonly_blocked=true`, `c12_4_blocked=true`. Proximo cartao
permitido: `C15.1.2 — wizard reliability battery on lab board` (5 F10
consecutivos com intervalos mistos, criterio de fechamento 5/5 sem
`code=killed` ou falha classificavel via trace). C16 (player) segue
bloqueado ate C15.1.2 fechar — disciplina tematica entre cartoes.

Atualizacao C15.1.2: 2026-05-13. Bateria fisica de 5 F10 executada na placa
lab ja ligada, com intervalos mistos. O fluxo warm-runtime do wizard passou
5/5 por trace:
`openvt_exited`, `WIZARD_RC=8`, `writer_called=true`, `writer_rc=0`,
`writer_result=passed`, `real_config_written=true`, `backup_created=true`,
lock limpo e `kiosky-player.service` restaurado em todas as tentativas. O
SIGTERM de C15.1.1 nao voltou, `config_missing` nao retomou durante o wizard e
terminal/login nao apareceu.
Foi removido o `printf` cru do `totem_firstboot_gate.sh` para `/dev/tty2` e o
hotfix foi aplicado na placa sem reboot; cold boot nao foi validado nesta
rodada. Porem C15.1.2 fica **bloqueado**, nao `passed`: o operador confirmou
que pressionar F10 ainda mostra caracteres de teclado sobre o SVG antes do
refresh limpar a tela. O operador tambem esclareceu que os sintomas originais
de sair sozinho, aparecer login ou voltar para `config_missing` sao percebidos
com mais frequencia imediatamente apos ligar a placa; esse contexto de cold
boot/primeira tentativa nao foi exercitado nesta rodada. Classificacao:
`keyboard_echo_persisted=true`, `cold_boot_context_tested=false`,
`unclassified_failures=0`.
Status:
`c15_1_2_status=blocked`, `all_tests_passed=false`,
`warm_runtime_f10_battery_passed=true`, `ready_for_image_rebuild=false`,
`ready_for_c16_player_audit=false`,
`c15_1_1_status=partial-validated`, `c16_started=false`,
`player_code_changed=false`, `secrets_published=false`,
`apt_update_executed=false`, `apt_upgrade_executed=false`,
`pip_install_executed=false`, `poweroff_executed=false`,
`power_cut_tested=false`, `c12_readonly_blocked=true`, `c12_4_blocked=true`.
Detalhes em
`docs/product/138_C15_1_2_WIZARD_RELIABILITY_BATTERY.md`.

Atualizacao C15.1.3: 2026-05-13. Corrigido o eco de teclado do F10 e validada
a primeira tentativa fisica apos um reboot controlado autorizado. A causa foi
classificada como `tty_echo_enabled_before_f10_hold`: a VT visual estava ativa,
mas com `echo` ligado antes do operador segurar F10. A correcao adiciona
`totem-visual-tty-guard.service`, iniciado antes do player, trigger e
open-settings, mantendo `tty1` e `tty2` abertos com `-echo -icanon` via
`totem_visual_tty_guard.sh --hold`. Uma variante intermediaria que reaplicava o
guard periodicamente foi rejeitada por causar piscada continua do SVG; a versao
final nao reescreve estado de terminal enquanto o wizard esta dono da VT.
Validacao warm pos-fix: sem caracteres, sem terminal/login, sem piscada
continua, sem saida antes da tela final e sem retorno para `config_missing`;
trace com `openvt_exited`, `WIZARD_RC=8`, writer `passed`, lock limpo e player
restaurado. Foi executado exatamente um `systemctl reboot`; apos o SSH voltar,
o primeiro F10 fisico passou com 8 telas incluindo `06-complete`, writer
`passed`, lock limpo, player restaurado e confirmacao visual do operador
(`funcionou`). Status: `c15_1_3_status=passed`,
`ready_for_image_rebuild=true`, `ready_for_c16_player_audit=true`,
`c16_started=false`, `player_code_changed=false`, `apt_update_executed=false`,
`apt_upgrade_executed=false`, `pip_install_executed=false`,
`poweroff_executed=false`, `power_cut_tested=false`,
`secrets_published=false`. C16/player fica liberado para abrir em cartao
seguinte, mas nao foi iniciado nesta rodada. Detalhes em
`docs/product/139_C15_1_3_F10_KEYBOARD_ECHO_AND_FIRST_REBOOT_VALIDATION.md`.

Atualizacao C15.1.4: 2026-05-13. Antes do rebuild C15.2.1, a tela Wi-Fi do
wizard visual recebeu uma melhoria focada de UX: lista paginada/navegavel,
refresh automatico a cada 10s, refresh manual por `R`, ordenacao por sinal,
agrupamento de SSID duplicado pelo melhor sinal, ocultacao de redes sem SSID,
percentual numerico de sinal, barras e bucket textual. A senha Wi-Fi permanece
oculta por padrao e agora pode ser alternada localmente por `F2` ou `V`; `V` foi
mantido como fallback para consoles que nao entregam F2 consistentemente. O
adapter recebeu apenas allowlist read-only para listagem Wi-Fi com rescan; ele
nao conecta, desconecta, reinicia NetworkManager ou altera perfil por si so.
Self-tests locais e na placa passaram, preview sintetico foi gerado e a evidencia
publica permaneceu sanitizada. No teste fisico, o operador confirmou 10 redes em
2 paginas, percentual de intensidade visivel e toggle de senha funcionando apos
hotfix. O wizard foi concluido pelo fluxo normal, Wi-Fi real foi aplicado pelo
wizard, writer `passed`, config real escrita, lock limpo e player restaurado,
sem publicar SSID/senha. Status: `c15_1_4_status=passed`,
`ready_for_image_rebuild=true`, `ready_for_c16_player_audit=true`,
`c16_started=false`, `player_code_changed=false`, `apt_update_executed=false`,
`apt_upgrade_executed=false`, `pip_install_executed=false`,
`poweroff_executed=false`, `power_cut_tested=false`, `secrets_published=false`.
Problemas legados observados mas nao misturados ao aceite: wizard poluido por
texto e piscada por backlog ao segurar Backspace. Detalhes em
`docs/product/140_C15_1_4_WIFI_SETUP_UX_REFRESH.md`.

Atualizacao C15.1.5: 2026-05-13. Antes do rebuild C15.2.1, C15.1.5 tratou os
follow-ups de UX deixados por C15.1.4: textos do wizard foram encurtados,
painel visual limitado a 3 itens, subtitulos limitados a uma linha e campos de
texto passaram a coalescer repeticoes rapidas de Backspace/digitacao com
debounce de render, mantendo `F2/V`, `Ctrl+B`, `Ctrl+U`, `Esc`, `Enter`, senha
oculta e sanitizacao. O splash existente foi reaproveitado para feedback em
`boot`, `player`, `setup`, `saving` e `config_pending`. Durante a validacao, uma
regressao de hotfix foi encontrada e corrigida: status de splash escrito
diretamente sob `/tmp` alterava a permissao do diretorio pai para privada,
quebrando o runtime MPV do usuario `totem`; a correcao moveu status para
`/tmp/dadooh-splash/...`, impediu chmod em `/tmp`, restaurou `/tmp` para `1777`
e recuperou o player/MPV. Self-tests, previews e hotfix na placa passaram; o
trace fisico teve `openvt_exited`, sem `trap_signal`, writer `passed`, lock
limpo e player restaurado. O operador confirmou que Backspace melhorou e para
imediatamente ao soltar; a interface ficou melhor, ainda que nao final. Durante
o retorno ao player, foi observada uma regressao de orientacao no ultimo splash
`Inicializando player`; ela foi corrigida no repo antes do commit removendo
renders duplicados de player splash: a sessao F10 fica responsavel pelo splash
com a rotacao selecionada, o unit do player nao desenha outro splash, o launcher
pula uma vez quando a sessao ja renderizou e o cleanup nao desenha sobre player
ja ativo. Depois que o SSH voltou, o patch final tambem foi aplicado na placa;
sanity runtime confirmou unit efetivo sem `totem_visual_splash.py player` em
`ExecStartPre`, player ativo, MPV presente, `/tmp=1777` e lock ausente. Status:
`c15_1_5_status=passed`, `ready_for_image_rebuild=true`,
`ready_for_c16_player_audit=true`, `c16_started=false`,
`player_code_changed=false`, `apt_update_executed=false`,
`apt_upgrade_executed=false`, `pip_install_executed=false`,
`poweroff_executed=false`, `power_cut_tested=false`, `secrets_published=false`.
Fica como follow-up separado um PDCA visual do wizard completo, orientado a
validacao real de uso, nao do splash.
Detalhes em
`docs/product/141_C15_1_5_WIZARD_UX_REDRAW_AND_STARTUP_FEEDBACK.md`.

Atualizacao C15.1.6: 2026-05-13. Antes do rebuild C15.2.1, C15.1.6 executou
uma revisao UI/UX assistida por IA sem interacao manual: nao houve F10, HDMI,
reboot, writer, alteracao de Wi-Fi, NetworkManager, player, read-only, kernel,
apt, pip, poweroff ou corte seco. Foi criado
`scripts/qa/generate_ui_ux_gallery.py`, que gera galeria sintetica de 27 telas
com splashes e estados do wizard, inventario de telas/funcoes, metricas de
texto/acoes/feedback, rubrica heuristica, stress automatico de input/paginacao
e backlog P0/P1/P2/P3. A rodada nao afirma revisao visual por pixels:
`ai_visual_review_performed=false`, `heuristic_review_performed=true`,
`human_review_required=true` e
`hdmi_capture_required_for_final_perception=true`. Resultado:
`p0_items_count=0`, `major_ui_blockers_found=false`,
`ready_for_image_rebuild=true`, `ready_for_c16_player_audit=true`,
`c16_started=false`. PNG nao foi gerado porque o conversor disponivel nao
rasterizou os SVGs sem instalar pacotes. Detalhes em
`docs/product/142_C15_1_6_AI_ASSISTED_UI_UX_REVIEW.md`.

Atualizacao C15.2.1/C15.2.2: 2026-05-13. A imagem privada C15.2.1 foi gerada
como derivacao offline da C14.2.1 validada, consolidando os fixes C15.1.3,
C15.1.4 e C15.1.5, preservando o pull updater C14.2.1 e mantendo os artefatos
de QA C15.1.6 fora do appliance. SHA256:
`ed6b74a37dd4213143ff456959a3a9ddb47d9a66046768131872932930dbf053`.
A validacao offline passou, mas a placa limpa bloqueou durante o primeiro
wizard: depois de conectar Wi-Fi, a entrada de ambiente foi interrompida e a
tela voltou para `config_missing`. A causa foi classificada em C15.2.2 como
`service_timeout` por uso de relogio de parede no deadline do `openvt`; a
correcao passou a usar uptime monotonic de `/proc/uptime`. C15.2.2 tambem
removeu `V/v` como atalho de mostrar senha, mantendo `v` e `V` digitaveis e F2
como toggle anunciado, com Ctrl+P como fallback nao imprimivel. O reteste F10
sobreviveu a entrada de ambiente e o writer passou, mas apos concluir houve tela
preta e perda de SSH; a recuperacao exigiu corte fisico. Portanto C15.2.1 e
C15.2.2 ficam bloqueados para lote/despacho/C16:
`ready_for_batch_flash=false`, `ready_for_dispatch=false`,
`ready_for_c16_player_audit=false`, `power_cut_tested=true`,
`c16_started=false`. Proximo passo: classificar a janela pos-wizard de tela
preta/perda de rede antes de gerar nova imagem. Detalhes em
`docs/product/143_C15_2_1_IMAGE_UI_UX_FIXES_CLEAN_BOARD_VALIDATION.md` e
`docs/product/144_C15_2_2_CLEAN_BOARD_WIZARD_SETUP_INTERRUPTION_FIX.md`.

Atualizacao C15.2.3: 2026-05-13. A janela pos-wizard de tela preta/perda de SSH
foi retestada com monitor persistente em `/data/state/totem-debug/c15-2-3`,
mais fases sanitizadas no wrapper de sessao e no wizard. O reteste F10 com
writer ativo nao reproduziu a falha: `writer_rc=0`, `writer_result=passed`,
`player_restore_done=true`, `post_restore_t+30s` mostrou player ativo e
`playing`, `session_done=true`, SSH e NetworkManager permaneceram ativos,
`failed_units_count=0`, sem reboot espontaneo, OOM ou kernel panic detectado.
A causa fica classificada como `not_reproduced_in_monitored_retest`. C15.2.3
fica `passed` para classificacao e libera nova tentativa de rebuild de imagem:
`ready_for_image_rebuild=true`. Lote/despacho/C16 continuam bloqueados ate a
proxima imagem passar em placa limpa:
`ready_for_batch_flash=false`, `ready_for_dispatch=false`,
`ready_for_c16_player_audit=false`, `c16_started=false`. Detalhes em
`docs/product/145_C15_2_3_POST_WIZARD_BLACK_SCREEN_SSH_LOSS_CLASSIFICATION.md`.

Atualizacao C15.2.4: 2026-05-13. A imagem privada
`c15-2-4-homolog-clean-board-fixes` foi gerada a partir da C14.2.1 validada,
reaproveitando kernel/U-Boot/DTB/BSP e substituindo apenas a camada appliance
do manifest. SHA256:
`e36b86004c75663fd4c3d14d8ed8b6186f102c8b644e7dbc4351ca734036dca9`.
A validacao offline confirmou updater C14, TTY guard, Wi-Fi UX, debounce,
splashes, timeout monotonic do `openvt`, correcao de senha `V/v`, seed privada
sem publicacao de conteudo e ausencia de artefatos QA/evidencia na rootfs. Uma
placa limpa foi gravada manualmente e passou no primeiro F10/full setup:
`wizard_rc=8`, `writer_rc=0`, `writer_result=passed`,
`real_config_written=true`, lock limpo, SSH e NetworkManager ativos, player
restaurado e playback `playing`. Houve intervalo preto transitorio ao entrar no
player apos o primeiro setup, sem queda de SSH e sem recuperacao; fica como
follow-up de player/startup para C16. `console-setup.service` apareceu failed
com erro sanitizado de setupcon/tmpkbd, sem bloquear teclado, wizard, SSH,
NetworkManager, player ou playback. C15.2.4 fica `passed`:
`ready_for_batch_flash=true`, `ready_for_dispatch=true`,
`ready_for_c16_player_audit=true`, `c16_started=false`. Detalhes em
`docs/product/146_C15_2_4_CLEAN_BOARD_IMAGE_VALIDATION.md`.
