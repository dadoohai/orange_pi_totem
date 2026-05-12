# 136 — C14.2.1 — Shipping homologation image with C14 pull updater embedded

## Por que existe esta frente

C14.1.1 entregou o fluxo de atualização remota do `kiosky-player` via GitHub
Releases, mas o processo de bootstrap (instalar `/opt/totem/bin/totem-updatectl`,
`/opt/totem/bin/totem-kiosky-launcher.sh`, drop-in systemd e timer) ainda exige
acesso SSH por placa. Em despacho de lote isso vira gargalo manual.

C14.2.1 resolve esse atrito do jeito mais barato possível: **bake** os arquivos
do C14.1.1 dentro da imagem privada de homologação que já foi validada em
C13.1.3. Não muda kernel, não muda U-Boot, não muda BSP, não destrava read-only,
não traz Mender/RAUC. Apenas cada placa gravada com a C14.2.1 já vem com o
updater instalado e com `totem-update-agent.timer` **enabled**.

Resultado prático:

| Antes (C13.1.3) | Depois (C14.2.1) |
|---|---|
| grava cartão | grava cartão |
| boot | boot |
| `ssh` na placa, rodar bootstrap | (nada) |
| `apply-github-latest` manual | timer dispara sozinho 10 min após boot |
| atualizações futuras → SSH manual | timer dispara a cada 6h ± 10 min |

## Decisões intencionalmente preservadas

- **Sem hardening novo nesta frente.** Sem assinatura GPG do manifest. Sem
  quarentena. Sem mudança de protocolo. Tudo que C14.1.1 entregou continua
  como está.
- **Sem mudança em kernel/U-Boot/DTB/BSP/rootfs.** A imagem é o mesmo build
  que C13.1.3 produziu, com **apenas mais arquivos** no rootfs antes do
  `mksquashfs` final do Armbian Build.
- **Sem `apt`/`pip` durante o build do app** (o Armbian Build precisa de
  `apt` para montar o rootfs, mas isso é o pipeline base do Armbian — não
  é update do app).
- **`/data/secrets/github-release-token` continua não criado.** Repositório
  `dadoohai/kiosky-player` é público; updater pode buscar releases
  anonimamente. Token só viraria necessário se promovêssemos o canal para
  um repo privado.

## O que entra na imagem

A diff em relação à C13.1.3 é exclusivamente:

```
+ /opt/totem/bin/totem-updatectl                    (Python stdlib only)
+ /opt/totem/bin/totem-kiosky-launcher.sh           (wrapper)
~ /opt/totem/bin/kiosky_service_launcher.sh         (já em C14.1.1, agora KIOSKY_APP_DIR-aware)
+ /etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf
+ /etc/systemd/system/totem-update-agent.service    (static)
+ /etc/systemd/system/totem-update-agent.timer      (ENABLED)
+ /data/apps/                                       (dir)
+ /data/apps/kiosky-player/
+ /data/apps/kiosky-player/releases/
+ /data/updates/
+ /data/updates/incoming/
```

A seed privada de homologação **continua** embutida em
`/data/state/totem-settings/private-values.seed.json` (mode 0600, root:root),
exatamente como em C13.1.3. Conteúdo nunca publicado.

## Timer configurado para lote

Os intervalos do `totem-update-agent.timer` foram afrouxados em relação aos
defaults do C14.1.1 para reduzir pressão sobre GitHub Releases em frota:

```ini
[Timer]
OnBootSec=10min
OnUnitActiveSec=6h
RandomizedDelaySec=10min
Persistent=true
Unit=totem-update-agent.service
```

- **OnBootSec=10min** — deixa o player aquecer, telemetria estabilizar e a
  rede prender antes de qualquer pull.
- **OnUnitActiveSec=6h** — janela conservadora para homologação. Quando
  promovermos para um canal `stable`, podemos apertar.
- **RandomizedDelaySec=10min** — ± 10 min de jitter; uma frota de 50 placas
  não vai bater no GitHub no mesmo segundo.
- **Persistent=true** — se a placa estava desligada e perdeu a janela, dispara
  uma vez no próximo boot e depois retoma a cadência normal.

`RestartPreventExitStatus=10 20` na service segue do C14.1.1: não fica em
loop frenético em caso de rollback automático ou bloqueio de acesso ao
GitHub.

## Como a imagem é construída

```
scripts/build/run_c14_2_1_build_shipping_homolog_image.sh \
  --homolog-private-values /caminho/fora/do/repo/seed.json \
  --lab-firstboot-conf      /caminho/fora/do/repo/firstboot.conf \
  --confirm-private-homolog-image \
  --mode full
```

Esse wrapper:

1. Valida que os arquivos privados estão **fora** do repo e têm perms 0600
   com diretório-pai 0700.
2. Exporta variáveis `C13_*` que o runner C12.1 já entendia (a validação
   ocorreu em C13.1.3 — não estamos validando build de novo).
3. Sequencia as fases do runner C12.1:
   `check-build-env → clone-or-check-armbian-build → prepare-userpatches → build-image → collect-artifacts → summary`.
4. Reaproveita a árvore Armbian Build local (`armbian-build-v25.11/`),
   cache de kernel/BSP e `userpatches-c12-image-lab/`.

A diferença em relação ao C13.1.3 é apenas o `totem_appliance_manifest.json`,
que agora lista as binárias e units do C14.1.1; o `customize-image.sh` já
chama `install_totem_appliance.sh --apply`, que consome o manifest.

### Reaproveitamento de kernel

O wrapper **não** força `RECREATE_KERNEL=yes` nem `KERNEL_CONFIG_NAME`
diferente. O cache do Armbian Build é reutilizado integralmente. Se a
máquina builder mostrar sinais de recompilação de kernel, é responsabilidade
do operador interromper e investigar — o pipeline normal não deveria fazê-lo.

## Como checar a imagem antes de gravar

Validação offline contra o rootfs montado (sem ligar placa):

```bash
# (rodando dentro do scripts do repo, com mountp/owned-by-build root)
ls $ROOTFS/opt/totem/bin/totem-updatectl
ls $ROOTFS/opt/totem/bin/totem-kiosky-launcher.sh
test -f $ROOTFS/etc/systemd/system/kiosky-player.service.d/20-dadooh-launcher.conf
test -f $ROOTFS/etc/systemd/system/totem-update-agent.service
test -f $ROOTFS/etc/systemd/system/totem-update-agent.timer
test -L $ROOTFS/etc/systemd/system/timers.target.wants/totem-update-agent.timer   # enabled
grep -q OnBootSec=10min $ROOTFS/etc/systemd/system/totem-update-agent.timer
grep -q OnUnitActiveSec=6h $ROOTFS/etc/systemd/system/totem-update-agent.timer
grep -q RandomizedDelaySec=10min $ROOTFS/etc/systemd/system/totem-update-agent.timer
stat -c '%a %U:%G' $ROOTFS/data/state/totem-settings/private-values.seed.json
test -d $ROOTFS/data/apps/kiosky-player/releases
test -d $ROOTFS/data/updates/incoming
```

`releases/image-lab-readonly/manifest.md` é atualizado com o novo SHA256.

## Checklist de gravação em lote (operacional)

1. Confirmar SHA256 da imagem antes de gravar qualquer placa.
2. Gravar **uma placa** primeiro; rodar a validação por placa (próxima
   seção) inteira nela.
3. Só liberar gravação em lote se essa placa passar.
4. Cada placa nova só precisa de: gravação → boot → conectar Wi-Fi (via
   wizard padrão F10/seed) → esperar timer. Não precisa SSH.

## Checklist de validação por placa (primeira placa)

Via SSH (depois do firstboot da placa lab):

```text
systemctl is-active   kiosky-player.service          ; expect active
systemctl is-enabled  totem-update-agent.timer       ; expect enabled
systemctl is-active   totem-update-agent.timer       ; expect active
/opt/totem/bin/totem-updatectl status                ; expect schema OK
/opt/totem/bin/totem-updatectl self-test             ; expect self_test=true
test -d /data/apps/kiosky-player/releases            ; expect ok
test -d /data/updates/incoming                       ; expect ok
test -f /data/state/totem-settings/private-values.seed.json   ; expect ok
stat -c '%a %U:%G' /data/state/totem-settings/private-values.seed.json
                                                     ; expect 600 root:root
```

Manual smoke do flow de update:

```text
/opt/totem/bin/totem-updatectl apply-github-latest --repo dadoohai/kiosky-player
                                                     ; expect apply_success
readlink -f /data/apps/kiosky-player/current
                                                     ; expect path under releases/
```

Rollback **não** é testado em C14.2.1 (já foi testado fim-a-fim em
C14.1.1 — vide commit `30aaf36` e evidência
`docs/evidence/candidate-a/runs/20260511T203006Z-c14-1-1-...`).

## Riscos aceitos para despacho

- **Token de device ainda não provisionado.** OK enquanto o repo for público.
  Quando promovermos para canal `stable` (ou fechar o repo), o updater já
  suporta `/data/secrets/github-release-token` — só falta o caminho de
  provisionamento seguro.
- **Sem assinatura GPG do manifest.** Confiança ainda apoia-se no TLS do
  GitHub. Aceitável para homologação; recomendado endurecer antes de
  produção.
- **Sem read-only (C12).** A escrita em `/data` é o que permite o swap
  do symlink `current`. Quando C12 destravar, isto continua funcionando
  porque `/data` é a partição writable.
- **Timer pode disparar durante uma janela ruim.** Mitigação: jitter de
  10 min e auto-rollback do C14.1.1 em caso de health check falhando.

## Restrições mantidas em C14.2.1

- Não muda kernel.
- Não muda U-Boot.
- Não muda DTB.
- Não muda BSP.
- Não muda rootfs além dos arquivos C14.1.1 + dirs de /data.
- Não roda `apt update` / `apt upgrade` / `apt full-upgrade` /
  `armbian-upgrade` na placa.
- Não roda `pip install` na placa.
- Não toca Wi-Fi / NetworkManager.
- Não cria `/data/config/config.json` real.
- Não cria `/data/secrets/github-release-token`.
- Não imprime/persiste senhas, tokens, api_key, api_url, environment_id,
  SSID, ou conteúdo da seed.
- Não executa `poweroff` / corte seco.
- Não toca em C12.4.

## Promoção futura (não nesta rodada)

1. Endurecer canal: assinatura GPG do manifest, dispositivo verifica
   chave pública embutida na imagem.
2. Provisionamento seguro de token de device (se o repo precisar ficar
   privado).
3. Health check funcional — bater no HTTP local do kiosk.py e exigir que
   `public_state` não seja `config_missing` antes de dar apply como sucesso.
4. Canal `stable` separado de `homologation` + cadência mais apertada
   (ex.: 1h em vez de 6h).
5. Quando C12 read-only destravar: re-validar que `/data` continua
   writable; symlink swap continua funcionando.
