# C13.1.3 - Build Homologation Private Image

Data: 2026-05-08

## Contexto

C13.1.2 adicionou suporte de codigo e validou em placa lab o fluxo de
homologacao: seed privada fora do repo, policy automatica, wizard em modo
homologacao, writer real chamado e produto saindo de `config_missing`.

C13.1.3 gera o artefato privado para reduzir atrito operacional: cada cartao de
homologacao gravado com esta imagem ja contem a seed temporaria no caminho
aprovado, sem exigir criacao manual por SSH em cada placa.

## Artefato

```text
image_version=c13.1.3
image_file=/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c13-1-3-homolog-private_minimal.img
sha256=3a76d51880d944fe5430782ad2cf84866573c219cdf6a719c004e38c5c2fe6eb
artifact_private=true
final_image=false
not_for_production=true
not_for_distribution=true
homologation_private_values_embedded=true
c12_readonly_blocked=true
c12_4_blocked=true
```

Esta imagem nao e final, nao e producao e nao deve ser distribuida. Ela existe
apenas para homologacao controlada.

## Seed Privada

A seed foi lida de arquivo privado fora do repo e instalada na imagem em:

```text
/data/state/totem-settings/private-values.seed.json
```

Validacao offline:

```text
seed_source_outside_repo=true
seed_permissions_ok=true
seed_mode=0600
seed_parent_mode=0700
seed_content_published=false
```

O marcador nao sensivel tambem foi instalado em:

```text
/data/state/totem-settings/homologation-seed.enabled
```

## Fluxo F10/Wizard

`totem-open-settings.service` nao depende mais de arquivo manual em `/tmp` para
homologacao. O servico executa o helper de policy antes do wizard; se a seed
embutida existir, a policy runtime e criada em:

```text
/run/dadooh-settings/apply-policy.json
```

Se a seed nao existir, o wizard permanece em candidate-only.

## Build

O build reaproveitou artefatos locais de kernel/U-Boot/BSP e gerou a imagem via
Armbian Build. Durante a rodada, o `apt-get update` em chroot arm64 emulado
falhou repetidamente ao ler listas de `bookworm-backports`. Como a imagem de
homologacao nao depende de backports, o build image-lab remove essa suite antes
dos updates finais da imagem, evitando o blocker de memoria em QEMU/WSL.

## Validacao

```text
image_built=true
checksum_created=true
offline_validation_passed=true
homologation_private_values_embedded=true
tmp_private_values_dependency=false
firstboot_conf_committed=false
firstboot_conf_contents_published=false
modular_overlay_fallback_hooks_present=false
diagnostic_initramfs_hooks_present=false
card_written=false
boards_touched=false
ssh_used=false
writer_called=false
poweroff_executed=false
power_cut_tested=false
apt_upgrade_executed=false
secrets_published=false
ready_for_multi_card_homologation=true
```

## Revogacao

Para revogar ou substituir a chave temporaria de homologacao:

1. substituir o arquivo privado fora do repo;
2. reconstruir nova imagem privada de homologacao;
3. descartar cartoes gravados com a seed antiga;
4. nunca promover este artefato para producao.

Para voltar ao modo sem secrets, gerar a imagem-lab sem
`C13_EMBED_HOMOLOG_PRIVATE_VALUES=1`.

## Proximo Passo

Gravar um cartao novo com a imagem C13.1.3 e validar first boot, F10, aplicacao
do wizard e playback em ambiente controlado.

C12 read-only permanece bloqueado; C12.4 continua bloqueado.
