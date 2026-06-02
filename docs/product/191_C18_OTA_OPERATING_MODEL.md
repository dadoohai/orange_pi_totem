# 191 - C18 OTA Operating Model

Documento operacional curto para OTA C18 futuro. Complementa o gate tecnico de
`189_C18_OTA_READINESS_GATE.md` e a orientacao de producao de
`190_C18_PROD_ORIENTATION.md`; nao substitui nenhum gate deles.

## Regra principal

OTA C18 e um fluxo manual, acionado por operador, para `totem-core` somente.
Ele serve para evoluir wizard, splash, status, validadores e helpers do core sem
trocar a baseline de playback/hwdecode ja validada. Auto-pull continua fora de
escopo ate hardening explicito.

Uma imagem C18 antiga pode aplicar uma release futura de `totem-core` apenas se
a release continuar compativel com o updater e com os wrappers ja embutidos na
imagem. A release futura nao pode depender de novo updater, nova unit systemd,
novo pacote do sistema, mudanca de kernel/BSP/DTB/U-Boot, mudanca de MPV,
mudanca de `/opt/totem/hwdecode` ou mudanca em `kiosky-player`. Se depender, o
caminho correto e nova imagem, nao OTA.

Regra de longevidade: manifests C18 novos devem declarar `requires.device_track`
e `requires.updater_features`. Imagens antigas rejeitam track errado, feature
desconhecida e chaves novas em `requires`. Isso e intencional: daqui a anos, se
uma release precisar de capacidade que o updater antigo nao possui, a falha
correta e "nao aplicar", nao aplicar parcialmente. Para destravar esse caso,
fazer imagem nova ou uma release ponte que continue dentro do contrato antigo.

## Canais

Politica conservadora de canal exato:

| Canal do device | Canal aceito no manifest | Publicacao |
| --- | --- | --- |
| `lab` | `lab` | Preferir pacote local; release remota so com autorizacao explicita. |
| `homologation` | `homologation` | Pre-release para placas de teste/homologacao. |
| `stable` | `stable` | Release normal somente depois de homologacao fisica e gates de producao. |

Nao ha heranca entre canais. Promocao e sempre explicita:
`lab -> homologation -> stable`.

## Policy e allowed_components

A policy C18 deve existir em `/data/updates/policy.json` e falhar fechada.
Para C18, o valor operacional permitido e:

```json
{
  "schema": "dadooh.totem.update.policy.v1",
  "device_track": "c18-hwdecode",
  "allowed_components": ["totem-core"],
  "allow_downgrade": false
}
```

`device_channel` e `allow_prerelease` variam por canal. O ponto fixo e
`allowed_components=["totem-core"]`. Nao ampliar para `kiosky-player` durante
C18.

## Freeze de kiosky-player

`kiosky-player`, MPV e hwdecode ficam congelados fora do OTA C18. O freeze vale
mesmo que uma release, manifest ou policy tente aplicar `kiosky-player`.

Qualquer mudanca em duracao, playlist, sync, decode, wrapper de MPV, flags de
MPV, panfrost, path de player, service do player ou fallback `/opt` exige frente
separada e imagem/homologacao apropriadas.

## Publicacao de totem-core

Antes de publicar:

1. Gerar pacote a partir de commit limpo e rastreavel.
2. Manifest deve declarar `component=totem-core`, `channel` correto, versao
   unica, commit de origem, payload, SHA256, `requires.device_track` e
   `requires.updater_features`.
3. `lab` e `homologation` nao podem ser publicadas como stable.
4. Release notes e evidencias devem ser sanitizadas: sem valores privados,
   dados de acesso, identificadores de ambiente, enderecos de conteudo ou logs
   brutos.
5. Publicar no proximo canal so depois dos gates do canal anterior.

Nao reaproveitar tag/versao para payload diferente. Se houver hotfix, publicar
nova versao.

O script de publish chama o gate C18 antes de criar a release. Publicacao que
nao passa no gate deve ser tratada como bloqueada, nao como aviso.

## Dry-run obrigatorio

Antes de qualquer apply real, rodar dry-run do mesmo comando que seria aplicado:

```sh
totem-updatectl apply-github-latest --component totem-core --repo <repo-do-projeto> --dry-run
```

O dry-run precisa selecionar exatamente a release esperada e nao pode alterar
`current`, `previous` ou `state.json`. Se selecionar outra release, nenhuma
release, canal errado, componente errado, prerelease indevida ou manifest
invalido, parar.

## Apply manual

O apply real so acontece depois do dry-run aprovado e com janela de rollback
definida. Antes do apply, confirmar:

- policy presente e canal esperado;
- `allowed_components` restrito a `totem-core`;
- timer de update desabilitado/inativo;
- nenhuma sessao de settings em andamento;
- player saudavel antes do update;
- fallback/current/previous conhecidos;
- evidencias publicaveis sem valores privados.

Depois do apply, validar wrapper apontando para `totem-core` novo, health checks
do core, wizard/F10 quando aplicavel, player ainda ativo e sem restart causado
pelo update.

## Rollback

Rollback nao e plano opcional; e pre-condicao do apply. Antes de aplicar, o
operador deve saber qual versao anterior sera restaurada e como validar o retorno.

Acionar rollback se ocorrer qualquer um destes casos:

- health check do core falha;
- wizard, splash, settings ou validadores ficam indisponiveis;
- player reinicia, para ou muda de fonte inesperadamente;
- policy/canal/componente ficam inconsistentes;
- apply parcial, symlink suspeito ou estado de `current`/`previous` incerto;
- evidencia sugere dependencia que deveria ser imagem, nao OTA.

Rollback aprovado precisa terminar com core anterior ativo, fallback funcional,
player saudavel e registro sanitizado do motivo.

## Quando NAO usar OTA

Nao usar OTA C18 para:

- atualizar `kiosky-player`, MPV, hwdecode, kernel, U-Boot, DTB, BSP ou pacotes
  do sistema;
- trocar unit systemd, timer, updater, permissao global de sistema ou layout de
  boot;
- alterar rede, NetworkManager, dados operacionais privados, seeds, conteudo ou
  dados de ambiente;
- corrigir problema de cartao, boot, energia, HDMI, GPU, temperatura ou storage;
- mudar policy para permitir outro componente;
- aplicar mudanca que exige reboot para ser verdadeira;
- promover para stable sem homologacao fisica, dry-run, rollback e gates de
  producao.

Se a mudanca toca essas areas, abrir frente propria e gerar imagem/homologacao.

## Gates obrigatorios

Antes de merge/publicacao:

- `PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py --json`;
- auditoria de privacidade das evidencias.

Antes de publicar um pacote especifico:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/qa/c18_ota_release_gate.py \
  --package-manifest <release-dir>/dadooh-totem-core-<version>.manifest.json \
  --json
```

Esse gate inclui `py_compile`, sintaxe dos scripts de release, policy/service,
freeze/downgrade/GC, governanca de canais, permissao de release, sandbox local,
`git diff --check`, validacao do manifest/payload/tar e scan de padroes de
segredo de alta confianca.

Antes de apply em placa:

- dry-run aprovado na propria policy/canal alvo;
- rollback testavel e operador presente;
- player saudavel antes/depois;
- `kiosky-player` continua bloqueado para OTA;
- timer continua desligado enquanto auto-pull estiver fora de escopo.

Antes de `stable` ou batch:

- promocao passou por `lab` e `homologation`;
- homologacao fisica passou;
- gates de producao aplicaveis de C18 permanecem obrigatorios, incluindo soak
  quando a frente for promover imagem/batch;
- se a mudanca exigir nova baseline de imagem, seguir o fluxo de imagem, nao OTA.
