# C9.7 - Setup Wi-Fi Integrado ao Wizard

Status: implementado e validado em bancada com HDMI/teclado.

Data: 2026-05-04

## Objetivo

Integrar o apply Wi-Fi real controlado do C9.6.3 ao Setup Produto Local V0,
sem hotspot, sem portal, sem writer e sem escrita de config real.

## Implementado

- a etapa Conexao do wizard ganhou a opcao `Testar Wi-Fi agora`;
- credenciais sao digitadas apenas localmente no totem;
- o wizard cria secrets temporario sob `/tmp` com permissoes restritas;
- o apply usa perfil dedicado permitido e rollback-after-test por padrao;
- a candidata continua mock para backend/API e segue validavel por C5.1
  `--allow-mock`;
- o status publico do setup registra apenas resultado agregado do Wi-Fi;
- o runner C9.7 pausa/restaura `kiosky-player.service` para liberar HDMI.

## Etapa Conexao

Opcoes disponiveis:

- `Usar conexao atual`: leitura agregada, sem alteracao de rede;
- `Testar Wi-Fi agora`: apply real controlado com rollback;
- `Continuar em modo de bancada/mock`: sem verificacao real;
- `Configurar Wi-Fi futuramente, se necessario`: nao executa rede agora.

## Artefatos

O wizard grava apenas em `/tmp`:

- `config.candidate.json`;
- `setup-status.json`;
- `summary.txt`;
- subdiretorio privado do teste Wi-Fi, quando executado.

O status registra campos agregados como resultado de ativacao, rollback,
perfil dedicado final, credenciais coletadas e secrets removido. SSID, senha,
IP, MAC, DNS, gateway, hostname, BSSID, UUID, nomes reais de conexao e logs
brutos continuam proibidos.

## Validacao

Passou:

- self-tests locais C9.6/C9.7/C5.1;
- C9.7 scripted local;
- runner remoto `--prepare-only`;
- runner remoto `--run-wifi-test-scripted`.
- runner remoto `--run-cancel` com humano no HDMI;
- runner remoto `--run-complete-with-wifi-rollback-after-test` com humano no
  HDMI;
- Wi-Fi activation `success`;
- rollback-after-test `success`;
- candidata gerada;
- C5.1 `--allow-mock` passou;
- C5.1 `--real-dry-run` falhou como esperado;
- estado final tardio: servico `active/enabled`, `NRestarts=0`,
  `public_state=player_running`, playback `playing`, player/MPV ativos,
  renderer/setup ausentes e perfil dedicado ausente.

Observacao: uma tentativa completa expirou enquanto o operador digitava um
ambiente longo. O runner foi ajustado para janela maior e cleanup explicito do
wizard C9.7 em timeout; a repeticao passou.

## Fora de Escopo

- hotspot;
- portal cativo/local;
- backend/login;
- writer;
- leitura ou escrita de `/data/config/config.json`;
- persistencia permanente do perfil Wi-Fi;
- alteracao do `kiosky-player`.

## Proximos Passos

C9.8 deve manter perfil Wi-Fi dedicado persistente de forma controlada, ainda
sem writer/config real. C10 deve tratar writer/config real separadamente.
