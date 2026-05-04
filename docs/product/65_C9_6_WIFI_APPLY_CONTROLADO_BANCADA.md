# C9.6 - Wi-Fi apply controlado em bancada

Status: implementado com apply real gateado. Apply nao deve ser executado sem
preflight limpo, credencial temporaria segura e confirmacao humana explicita.

Data: 2026-05-04

## Objetivo

Permitir o primeiro teste real de NetworkManager em bancada sem hotspot, portal,
wizard, writer, config real, player, MPV ou reboot.

## Implementado

- `totem_wifi_nm_adapter.py` mantem `--self-test`, `--read-only` e `--plan`;
- adiciona `--preflight-apply`, `--apply` e `--rollback-last`;
- `--apply` exige `--enable-real-apply`, frase exata, arquivo de credenciais
  restrito sob `/tmp`, perfil dedicado permitido e timeout;
- `--apply` usa somente perfil `dadooh-c9-6-*` ou `dadooh-product-wifi-*`;
- rollback limitado toca apenas o perfil dedicado;
- artefatos sanitizados ficam em `/tmp/dadooh-c9-6-wifi-apply` com `0700/0600`;
- runner remoto `run_c9_6_wifi_apply_controlled.sh` usa o novo IP da placa e
  nao para servico nem altera player.

## Modos

- `--read-only`: mede estado agregado, sem alterar rede;
- `--plan`: descreve apply futuro, sem credencial e sem rede real;
- `--preflight-apply`: decide se apply seria permitido, sem alterar rede;
- `--apply`: aplica apenas com gates explicitos;
- `--rollback-last`: tenta remover/desativar somente o perfil dedicado.

## Credenciais

Credenciais entram somente por arquivo JSON temporario:

```json
{
  "ssid": "...",
  "psk": "..."
}
```

O arquivo deve estar sob `/tmp`, nao ser symlink, ter permissao `0600` e pai
`0700`. O valor nao e impresso, nao entra em summary/status/evidencia e nao e
aceito por argumento de linha de comando.

## Rollback

O rollback de C9.6 e limitado ao perfil dedicado do produto. Ele nao remove
conexoes antigas, nao modifica Ethernet e nao tenta publicar nome real de
conexao, IP, MAC, gateway ou DNS.

## Validacao

Local:

```bash
python3 scripts/board/totem_wifi_nm_adapter.py --self-test
python3 scripts/board/totem_wifi_nm_adapter.py --read-only
python3 scripts/board/totem_wifi_nm_adapter.py --plan
python3 scripts/board/totem_wifi_nm_adapter.py --preflight-apply
```

Remoto seguro:

```bash
scripts/remote/run_c9_6_wifi_apply_controlled.sh root@192.168.1.147 --prepare-only
scripts/remote/run_c9_6_wifi_apply_controlled.sh root@192.168.1.147 --preflight-apply
```

Apply real fica bloqueado se o preflight nao classificar o caminho SSH como
seguro, se a credencial temporaria nao for restrita, se o perfil nao for
dedicado ou se a confirmacao textual nao bater exatamente.

## Nao Implementado

- hotspot;
- portal;
- integracao ao wizard C9.4;
- writer/config real;
- alteracao de player, MPV, renderer ou `kiosky-player`;
- reboot;
- persistencia/autoconnect como default de produto.

## Criterios Para C9.7

- executar apply real em bancada apenas com preflight limpo;
- confirmar rollback-after-test e acesso SSH preservado;
- decidir como o resultado agregado sera consumido pelo wizard;
- continuar sem hotspot/portal ate a frente separada ser aberta.
