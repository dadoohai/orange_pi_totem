# C10.6.1 - Gatilho persistente de Configuracoes

Data: 2026-05-05

## Objetivo

Fechar o acesso local V0 para abrir as Configuracoes do Totem com o player
rodando, sem depender de um runner remoto ativo.

## Comportamento de produto

O operador segura `F10` por 5 segundos no teclado local. O servico persistente
detecta apenas esse gesto, cria uma solicitacao sanitizada em `/run` e aciona a
sessao de Configuracoes. A tela exibida continua sendo o wizard visual existente.

Nao ha menu paralelo de manutencao, suporte, terminal, root, shell ou login
Linux na UI do operador.

## Servicos

- `totem-settings-trigger.service`: fica habilitado e ativo, monitora teclado
  local em modo read-only e detecta `F10` longo.
- `totem-open-settings.service`: oneshot, chamado pelo trigger para cobrir a
  HDMI com splash, pausar o player, abrir o wizard visual e restaurar o player.

`Ctrl+I` e `F12` nao sao o caminho principal. O trigger aceita esses atalhos
somente se flags de desenvolvimento forem habilitadas explicitamente.

## Privacidade

O trigger nao registra teclas digitadas, caracteres, SSID, senha, ambiente,
config privada, IP, MAC ou DNS. O request publico contem apenas:

- `schema_version`;
- `requested_at`;
- `trigger_type=keyboard_f10_hold`;
- `action=open_settings`.

## Validacao

Validar com:

```bash
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --prepare-only
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --install-trigger
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --status
scripts/remote/run_c10_6_1_persistent_settings_trigger.sh <host> --run-human-f10
```

O reboot-check exige confirmacao separada:

```text
CONFIRMO REBOOT C10.6.1 TRIGGER PERSISTENTE
```

## Fora do escopo

- PIN/senha local;
- Suporte Local V0;
- reboot/desligamento por UI;
- writer real;
- alteracao de config real;
- alteracao de Wi-Fi/NetworkManager;
- hotspot, portal, read-only e corte seco.

## Proximo passo

C10.6.2 fecha a aplicacao das Configuracoes abertas por `F10`: dry-run privado,
writer real controlado, atualizacao de `orientation.json` e reinicio do player.

PIN/senha local fica para uma etapa posterior. C10.7 fica separado para Suporte
Local V0.
