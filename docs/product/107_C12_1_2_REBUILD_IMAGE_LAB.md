# C12.1.2 - Rebuild Image-Lab

Data: 2026-05-07

## Objetivo

Regerar a image-lab read-only com os fixes C12.3.1 incorporados, sem tocar
placas e sem gravar cartao.

## Resultado

A nova imagem foi gerada com identificador C12.1.2:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab-c12-1-2_minimal.img
```

SHA256:

```text
a398399c139c3fee1b05860b216db7facfddd0ae1a57f681b229228390b7abd9
```

Artefatos:

- checksum: imagem `.sha256`;
- build log: `log-build-eef4830c-29a1-4a82-bd74-81ff23b65894.log`;
- package manifest: `releases/image-lab-readonly/package-manifest-c12-1-2.txt`;
- integration manifest:
  `releases/image-lab-readonly/read-only-integration-manifest-c12-1-2.txt`.

## Fixes Incluidos

- `totem-open-settings.service` com cleanup pos-falha;
- `totem_open_settings_cleanup.sh`;
- trigger F10 com limpeza de `session.lock` stale;
- `totem-firstboot-gate.service`;
- `totem_firstboot_gate.sh`;
- gate de firstboot enquanto `/root/.not_logged_in_yet` existir;
- suporte opcional a `C12_LAB_FIRSTBOOT_CONF` privado fora do Git;
- validacao com assert explicito de read-only.

## Read-only

O build inclui `overlayroot` e o initrd selecionado contem os hooks do
`overlayroot`. Nesta rodada houve `initrd cache hit`; por isso, a evidencia
classifica a fonte como:

```text
initramfs_source=cache_hit_with_overlayroot_hooks
```

Isso preserva o gate: a proxima validacao em placa deve provar
`read_only_enabled=true`, `overlay_active=true`, root protegido e `/data`,
`/tmp` e `/run` gravaveis. Se root aparecer como ext4 `rw`, o resultado deve
ser `IMAGE_LAB_READ_ONLY_NOT_ACTIVE`.

## Guardrails

- placa dev nao tocada;
- placa teste nao tocada;
- nenhum cartao gravado;
- imagem final de producao ainda bloqueada;
- nenhum secret, config real, SSID/senha ou media cache embutido.

## Proximo Passo

C12.2.1 pode gravar esta imagem em cartao novo/descartavel. Depois, C12.3.2
deve revalidar boot, firstboot gate, F10 open/cancel e read-only assertion.
