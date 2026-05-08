# C13.1.2 - Homologation Private Seed

Data: 2026-05-08

## Contexto

C12.3.17 permanece bloqueado para read-only:

- `CONFIG_OVERLAY_FS=y` confirmado em runtime;
- `overlay` aparece em `/proc/filesystems`;
- `overlayroot=tmpfs` esta presente;
- root ainda monta como `ext4`;
- `overlay_active=false`;
- `readonly_semantics_valid=false`;
- C12.4 continua bloqueado.

Esta rodada nao altera a estrategia read-only. O objetivo foi reduzir atrito de
homologacao: placas de bancada nao devem exigir criacao manual de
`private-values.json` por SSH depois de gravar a imagem.

## Decisao

Foi adicionado suporte a uma seed privada de homologacao embutivel apenas em
imagem-lab privada:

```text
final_image=false
artifact_private=true
homologation_private_values_embedded=true
not_for_production=true
not_for_distribution=true
c12_readonly_blocked=true
c12_4_blocked=true
```

A seed nunca entra no Git e seu conteudo nao deve aparecer em logs, docs,
manifest ou evidencia.

## Build

O build passa a aceitar:

```text
C13_EMBED_HOMOLOG_PRIVATE_VALUES=1
C13_HOMOLOG_PRIVATE_VALUES=/caminho/fora/do/repo/private-values.json
C13_CONFIRM_PRIVATE_HOMOLOG_IMAGE=1
```

O build falha antes de gerar imagem se:

- a confirmacao privada nao foi dada;
- o arquivo nao existe;
- o arquivo esta dentro do repo;
- o arquivo ou diretorio pai tem permissoes permissivas;
- o JSON nao contem as categorias `api_key` e `api_url`;
- a validacao offline nao consegue provar a seed no rootfs final sem publicar
  valores.

Quando habilitada, a seed e instalada em:

```text
/data/state/totem-settings/private-values.seed.json
```

com modo `0600`, e o marcador nao sensivel:

```text
/data/state/totem-settings/homologation-seed.enabled
```

## Runtime

`totem-open-settings.service` agora executa antes do wizard:

```text
totem_settings_lab_apply_policy.sh --enable-from-homologation-seed-if-present
```

Se a seed existir, o helper cria uma policy temporaria em
`/run/dadooh-settings/apply-policy.json` apontando para a seed e marcando o modo
como homologacao. Se a seed nao existir, o wizard continua em candidate-only.

O wizard exibe mensagem simples de homologacao, sem mostrar `api_url`,
`api_key`, SSID, senha ou identificadores privados.

## Teste na Placa Lab

O hotfix foi aplicado na placa lab ja bootada, sem reboot, poweroff, corte seco
ou apt. Primeiro uma seed sintetica validou que o fluxo sai de `config_missing`
quando ha config real, mas pode ficar sem midia se endpoint/chave nao forem
validos.

Depois, uma seed privada real fornecida fora do repo foi validada por categoria
e permissao sem imprimir valores, copiada para a seed da placa e aplicada pelo
writer real controlado.

Resultado sanitizado:

```text
seed_source_outside_repo=true
seed_permissions_ok=true
seed_content_published=false
wizard_auto_policy_enabled=true
writer_called=true
real_config_written=true
config_real_present=true
public_state_after_apply=player_running
playback_after_apply=playing
poweroff_executed=false
power_cut_tested=false
apt_upgrade_executed=false
secrets_published=false
```

## Status

O suporte de codigo e a validacao em placa passaram. A imagem privada de
homologacao ainda deve ser gerada em rodada propria usando as variaveis C13
acima, para evitar qualquer confusao entre artefato privado descartavel e imagem
final.

```text
c13_1_2_code_support=passed
c13_1_2_board_hotfix=passed
c13_1_2_private_image_built=false
ready_for_c13_1_2_private_image_build=true
c12_4_blocked=true
```

C13.1.3 gerou a imagem privada de homologacao com a seed embutida e validacao
offline passada. A imagem e artefato privado descartavel, nao final e nao
distribuivel.

## Revogacao

Para revogar ou substituir a chave temporaria:

1. remover a seed privada da placa ou gerar nova imagem-lab privada;
2. substituir o arquivo privado fora do repo;
3. reconstruir a imagem privada de homologacao;
4. nunca promover esse artefato para producao.

Para voltar ao modo sem secrets, gerar imagem-lab sem
`C13_EMBED_HOMOLOG_PRIVATE_VALUES=1`. Nesse modo, o wizard permanece
candidate-only ate receber uma policy privada externa.
