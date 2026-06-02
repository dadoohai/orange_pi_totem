# 135 — C14.1.1 — GitHub Releases pull deploy MVP

> Nota C18: este documento e historico. Nao usar os passos de
> publish/apply/timer daqui como contrato vigente sem conferir
> [docs/UPDATE_CONTRACT.md](../UPDATE_CONTRACT.md).

## Por que existe esta frente

A imagem privada de homologação C13.1.3 está rodando bem na placa. Precisamos
de uma forma simples de iterar no aplicativo `kiosky-player` sem refazer a
imagem inteira. C14.1.1 entrega o caminho mais curto possível:

- **fonte de verdade externa:** GitHub Releases — servidor de pacotes "de graça",
  já familiar para o time, controlável por permissão de repositório;
- **direção:** **pull** da placa para o GitHub — sem inbound, sem agentes
  proprietários, sem servidor próprio;
- **escopo:** **somente** o app (`kiosky-player`), **somente** em `/data`,
  trocando um symlink atômico.

## Decisões intencionalmente preservadas

- **Não usar git pull na placa.** A placa não precisa de Git, não precisa de
  credenciais Git, não precisa expor `.git` (que carrega histórico privado).
  A placa só fala HTTPS com `api.github.com` e `releases/download/...`.
- **Não usar Mender / RAUC / SWUpdate agora.** Eles atualizam imagens; nosso
  problema é atualizar **um app**. Trazê-los aqui teria custo de integração
  e ambiguidade de escopo (kernel vs DTB vs rootfs) sem ganho imediato.
- **Não atualizar OS / kernel / U-Boot / DTB / BSP / rootfs.** O imutável
  continua imutável. C12 read-only permanece bloqueado; **isto não desbloqueia
  C12** — apenas reduz a frequência com que precisaremos rebuildar imagem.
- **Não rodar apt/pip na placa.** A imagem-base C13.1.3 carrega o runtime
  Python que o app usa. Se uma release nova exigir um pacote Python novo,
  o updater **bloqueia** em vez de instalar.

## Como o sistema fica organizado

```
/opt/totem/                              (read-only ao app, conforme unit)
├── bin/
│   ├── kiosky_service_launcher.sh       (launcher original, agora lê KIOSKY_APP_DIR)
│   ├── totem-kiosky-launcher.sh         (NOVO — escolhe current vs fallback)
│   └── totem-updatectl                  (NOVO — updater Python stdlib)
└── kiosky-player/                       (versão "factory" que veio na imagem)
    └── kiosk.py

/etc/systemd/system/
├── kiosky-player.service.d/
│   └── 20-dadooh-launcher.conf          (NOVO — drop-in: redireciona ExecStart)
├── totem-update-agent.service           (NOVO — disabled by default)
└── totem-update-agent.timer             (NOVO — disabled by default)

/data/                                   (writable, sobrevive reflash do app)
├── apps/kiosky-player/
│   ├── releases/<version>/              (uma pasta por versão extraída)
│   ├── current   -> releases/<version>  (symlink atômico — versão ativa)
│   └── previous  -> releases/<version>  (versão anterior, para rollback)
├── updates/
│   ├── incoming/<version>/              (downloads em curso / verificados)
│   └── state.json                       (estado da última operação)
└── logs/totem-update.log                (auditoria sanitizada, com rotação a 1 MiB)
```

## Formato do pacote (`dadooh.totem.update.v1`)

Cada release tem **2 assets**:

1. `dadooh-kiosky-player-<version>.tar.gz` — árvore do app empacotada via
   `git archive HEAD` (somente arquivos versionados), com `--owner=0`,
   `--group=0`, `--numeric-owner`, `--sort=name` e `--mtime` do commit, para
   build determinístico.
2. `dadooh-kiosky-player-<version>.manifest.json` — metadados:

   ```json
   {
     "schema": "dadooh.totem.update.v1",
     "component": "kiosky-player",
     "version": "homolog-YYYYMMDD-HHMMSS-<commit-short>",
     "channel": "homologation",
     "source_repo": "dadoohai/kiosky-player",
     "source_branch": "appliance-v0.1",
     "source_commit": "<full sha>",
     "source_dirty": false,
     "payload": "dadooh-kiosky-player-<version>.tar.gz",
     "payload_sha256": "<hex>",
     "payload_bytes": 43455,
     "entrypoint": "kiosk.py",
     "requires": {
       "device": "orangepizero3",
       "base_image_min": "c13.1.3"
     },
     "created_at_utc": "..."
   }
   ```

Scan de pacote no builder rejeita:
- `.git`, `__pycache__`, `.pytest_cache`, `.venv`;
- `private-values.seed.json`, `config.json`, `.env`, `credentials.json`;
- chaves privadas (`-----BEGIN ... PRIVATE KEY-----`), AWS access keys,
  `ghp_*`, `gho_*`, `ghs_*`, `github_pat_*` (regex defensivo).

## Fluxo de **apply**

```
[builder]                                            [placa]
  build_kiosky_player_release_package.sh                .
  └─> releases/app-updates/<v>/                         .
  publish_kiosky_player_github_release.sh               .
  └─> gh release create  → GitHub Releases  ───┐        .
                                               └──> HTTPS pull
                                                     totem-updatectl apply-github-latest
                                                       1. GET api.github.com /releases (lista)
                                                       2. baixa manifest -> /data/updates/incoming/<v>/
                                                       3. valida schema + requires.device
                                                       4. baixa payload tar.gz, valida SHA256
                                                       5. extrai em /data/apps/kiosky-player/releases/<v>/
                                                       6. check requirements vs runtime atual
                                                       7. swap symlink current (atomic)
                                                          previous <- versão antiga
                                                       8. grava state.json (pending_health_check)
                                                       9. systemctl restart kiosky-player
                                                      10. health check (is-active + grace + NRestarts)
                                                      11. grava state.json (success | rolled_back)
```

Códigos de retorno do updater:
- `0` apply ok
- `6` falha no download do payload
- `7` falha na extração
- `8` entrypoint ausente após extração
- `9` requirements incompatíveis
- `10` apply falhou e foi feito rollback automático
- `11` apply falhou e **não havia previous** (placa fica como estava antes do swap)
- `20` `PRIVATE_RELEASE_REQUIRES_DEVICE_TOKEN` ou `GITHUB_RELEASE_ASSET_NOT_ACCESSIBLE_FROM_DEVICE`
- `21+` outros erros (HTTP, JSON, etc.)

## Fluxo de **rollback** (manual)

```
totem-updatectl rollback
  1. lê previous symlink
  2. swap atomically: current <- previous ;  previous <- (current antigo)
  3. systemctl restart kiosky-player
  4. health check
  5. atualiza state.json
```

Comportamento se não houver `previous`: retorna `rollback_not_available_no_previous`
sem mexer no estado.

## Como publicar uma release nova

No builder host (já autenticado em `gh`):

```bash
cd /home/builder/totem-os/orange_pi_totem

# 1. Empacota a árvore atual de /home/builder/kiosky-player (HEAD)
scripts/deploy/build_kiosky_player_release_package.sh --build-package
# (ou --prepare-only para só ver o plano)

# 2. Publica no GitHub Releases como prerelease
scripts/deploy/publish_kiosky_player_github_release.sh \
  --release-dir releases/app-updates/<version>/ --publish
# (ou --prepare-only para só ver o plano)
```

## Como aplicar manualmente

A partir do builder, sessão SSH única (operador digita senha):

```bash
bash scripts/remote/apply_c14_1_1_release_on_board.sh
```

Ou, direto na placa via SSH:

```bash
/opt/totem/bin/totem-updatectl check-github-latest --repo dadoohai/kiosky-player
/opt/totem/bin/totem-updatectl apply-github-latest  --repo dadoohai/kiosky-player
/opt/totem/bin/totem-updatectl status
```

## Como rollback manualmente

```bash
/opt/totem/bin/totem-updatectl rollback
```

ou a partir do builder:

```bash
bash scripts/remote/rollback_c14_1_1_on_board.sh
```

## Como habilitar timer automático depois

O timer está **instalado mas desabilitado** por design. Para ligar:

```bash
ssh root@<placa> 'systemctl enable --now totem-update-agent.timer'
```

Comportamento:
- `OnBootSec=5min` — primeira tentativa 5 min depois do boot;
- `OnUnitActiveSec=1h` — depois disso, uma checagem por hora;
- `RandomizedDelaySec=2min` — jitter contra "thundering herd";
- `Persistent=true` — se a placa estava desligada e perdeu o disparo, dispara
  uma vez no próximo boot;
- `RestartPreventExitStatus=10 20` — não fica em loop se `rolled_back` ou
  `PRIVATE_RELEASE_REQUIRES_DEVICE_TOKEN`.

Para desligar:

```bash
ssh root@<placa> 'systemctl disable --now totem-update-agent.timer'
```

## Riscos conhecidos

- **`current` aponta para `/data`, que NÃO é read-only.** Em tese, alguém com
  acesso root na placa pode trocar o symlink. Como o sistema é homologação e
  o `/data` já é writable em geral, é um trade-off aceito. Quando C12 voltar
  a andar, podemos pensar em verificar GPG do manifest antes de aceitar.
- **O updater confia que `payload_sha256` do manifest é íntegro.** O canal
  TLS do GitHub é a defesa em camada — a comunicação é HTTPS para
  `api.github.com` e `releases/download/...`, ambos terminados por GitHub.
  Não há assinatura GPG separada do manifest **ainda**.
- **Auto-rollback depende de `previous` existir.** Se a primeira release
  publicada já falhar o health check, o updater volta o symlink ao que tinha
  antes (que pode ser nada), retorna exit code 11, e o serviço pode ficar
  apontando para nada — mas a fallback do launcher continua a entregar o
  `/opt/totem/kiosky-player/kiosk.py` da imagem-base. Ou seja: o pior caso
  é "voltou para a versão da imagem", não "ficou sem player".
- **`requirements.txt` é checado por `import` em Python.** Heurística
  conservadora: pacotes que importam com nome diferente do que está no
  requirements ainda podem passar. Para essa rodada está OK porque o único
  requirement é `requests`, que já está na imagem.
- **`gh CLI` é usado SÓ no builder.** Se quisermos publicar de outro
  ambiente (ex.: CI), o publisher precisa de `gh auth login` separado.

## Riscos explicitamente fora de escopo

- read-only (C12);
- corte seco (C12.4);
- OTA de OS / kernel / U-Boot;
- onboarding de Wi-Fi via update;
- migração de schema do `state.json` (não há esquema prévio a migrar).

## Próximos passos sugeridos

1. **Assinatura GPG do manifest** — autenticidade independente do canal HTTPS
   do GitHub. Necessário antes de habilitar update agent automático em
   produção.
2. **Token de device opcional** — para repos privados, aceitar token em
   `/data/secrets/github-release-token` (já suportado no updater, falta criar
   o caminho de provisionamento seguro). A infraestrutura está pronta:
   se `/data/secrets/github-release-token` existir, o updater anexa
   `Authorization: Bearer <token>` aos requests HTTPS sem nunca logar o token.
3. **Detecção mais precisa de incompatibilidade Python** — usar nomes de
   distribuição via `importlib.metadata.distributions()` em vez de heurística
   por `import`.
4. **Canal `stable`** — hoje só publicamos prerelease (channel `homologation`).
   Quando uma versão for promovida, mudar `channel` no manifest e ajustar
   o filtro de `_gh_get_latest_release` no updater.
5. **Health check funcional** — além de `systemctl is-active`, opcionalmente
   bater no servidor HTTP local do `kiosk.py` e exigir que `public_state`
   não seja `config_missing`. Hoje a janela de health é só "service active
   sem grow em `NRestarts` por 12s".
6. **Integração com `totem_appliance_manifest.json`** — registrar
   `kiosky_player_active_version=<v>` no manifest da placa para ferramentas
   de inventário enxergarem.

## Relacionamento com outras frentes

- **C12 (read-only):** continua bloqueado, **não interfere**. O update grava
  só em `/data`. Quando C12 destravar, isto continua funcionando porque
  `/data` é writable.
- **C13.1.3 (homologation private image):** é a imagem base que esta frente
  pressupõe. O manifest declara `requires.base_image_min=c13.1.3`.
- **Mender/RAUC/SWUpdate:** descartados nesta rodada. Não fica nada para
  remover quando voltarmos a essa discussão — o updater app-only é
  ortogonal ao updater de OS.
