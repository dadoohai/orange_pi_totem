# ADR-0004 - Runtime MPV do kiosky-player no appliance

## Status

Candidata. Ainda nao homologada para producao.

## Contexto

O Candidato A ja aprovou MPV manual via DRM/KMS direto e o `kiosky-player`
manual como usuario `totem`. As rodadas recentes separaram dois problemas:

- IPC/watchdog/loadfile foi estabilizado por `mpv_query_uses_fresh_ipc=true`.
- A falta de progressao de alguns videos foi isolada no perfil de flags MPV do
  app, nao nos arquivos, no DRM/KMS basico nem no watchdog.

A matriz `20260430-125237-mpv-remaining-flags-matrix` mostrou que adicionar
explicitamente a saida MPV abaixo ao perfil do app fez os aliases problematicos
avancarem e manteve o alias que ja funcionava:

```text
--vo=gpu --gpu-context=drm --ao=null
```

## Decisao candidata

Usar no appliance:

- MPV direto via DRM/KMS.
- Sem desktop, Xorg, Wayland, compositor ou Chromium nesta fase.
- `mpv_query_uses_fresh_ipc=true` para consultas de watchdog/estado.
- Saida MPV explicita no comando do app:

```text
--vo=gpu --gpu-context=drm --ao=null
```

Manter `systemd` da aplicacao bloqueado ate a validacao manual da mudanca.

## Validacao exigida

Antes de aceitar esta ADR:

1. Aplicar a saida explicita no `kiosky-player`.
2. Repetir o observer do app real por 300s, sem `systemd`.
3. Confirmar IPC/watchdog/loadfile estaveis:
   - `MPV IPC command timeout=0`
   - `MPV IPC ping failed=0`
   - `Restarting MPV=0`
   - `Failed to load media=0`
4. Confirmar progressao de `time-pos` e frame nos aliases problematicos.
5. Confirmar `systemctl --failed=0` e filtro critico de kernel limpo.
6. Depois disso, rodar teste manual mais longo antes de liberar qualquer unit
   `systemd`.

## Consequencias

- Mantem a arquitetura simples, sem desktop/compositor.
- Reduz ambiguidade de autodeteccao de saida do MPV no ambiente DRM/KMS.
- Preserva o caminho que ja funcionou nos testes MPV diretos.
- Mantem a liberacao de `systemd`, root read-only e corte seco dependente de
  evidencias posteriores.
