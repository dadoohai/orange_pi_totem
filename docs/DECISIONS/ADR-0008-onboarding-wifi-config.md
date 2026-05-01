# ADR-0008 - Onboarding Wi-Fi/configuracao

## Status

Proposta.

## Contexto

O totem ja tem uma base tecnica funcional para reproducao: MPV via DRM/KMS,
IPC/watchdog/loadfile estabilizados, launcher com `systemd` em desenvolvimento,
HDMI ausente/reconexao tratado e tela Dadooh para `config_missing`.

Ainda falta transformar isso em um fluxo de primeiro uso para operador nao
tecnico. Hoje a config privada e criada fora do Git e nao deve ser manipulada
por operador em campo. A proxima fase precisa planejar Wi-Fi, ativacao e
gravacao de config sem terminal, SSH ou edicao manual de JSON.

A homologacao `v0.1-rc1` segue separada. Esta ADR propoe direcao para
desenvolvimento futuro, nao producao.

## Decisao proposta

- Onboarding sera feito por celular.
- Hotspot e portal local ficam para fase futura, depois de C0.
- Ativacao sera por codigo curto.
- Operador nao digita secrets, `api_key`, IDs internos ou JSON.
- NetworkManager sera o backend de rede.
- Setup ficara separado do `kiosky-player`.
- Launcher orquestrara estados entre status/splash, setup e player.
- Config privada sera escrita futuramente por componente dedicado, com validacao
  e gravacao atomica em `/data/config`.

## Alternativas consideradas

### Terminal/SSH

Rapido para bancada, mas inadequado para operador nao tecnico e arriscado para
campo. Tambem aumenta chance de publicar ou digitar secrets incorretamente.

### Configurar JSON manualmente

Funciona em desenvolvimento, mas exige conhecimento interno, manipula secrets e
nao escala para instalacao assistida.

### Chromium local

Facilitaria UI rica no proprio totem, mas adiciona desktop/compositor ou stack
grafica ainda fora do caminho validado. Tambem aumenta consumo e superficie de
falha.

### App mobile dedicado

Pode dar boa UX, mas aumenta custo de distribuicao, compatibilidade e suporte.
Portal local por celular e mais simples para a primeira versao.

### Portal remoto apenas

Nao resolve primeiro boot sem internet, troca de Wi-Fi local ou ativacao em
ambiente sem conectividade inicial.

## Consequencias

- O player permanece desacoplado de Wi-Fi e ativacao.
- NetworkManager passa a precisar de adapter controlado, testado e reversivel.
- O fluxo deve tratar internet ausente, DNS falho, backend indisponivel e senha
  incorreta sem expor detalhes privados.
- Sera necessario contrato de estados publicos de setup.
- O config writer deve ser atomico e preservar ultima config valida quando
  aplicavel.
- Hotspot e portal local precisam de revisao de seguranca antes de qualquer
  uso em campo.

## Riscos

- Derrubar acesso de bancada ao alterar rede.
- Vazar senha Wi-Fi ou config privada em logs/status/diagnostico.
- Criar portal local com superficie de ataque indevida.
- Gerar config parcial e iniciar player em estado invalido.
- Depender de backend durante instalacao sem fallback claro.
- Misturar desenvolvimento pos-RC1 com homologacao `v0.1-rc1`.

## Proximos passos

1. Concluir C0 com documento de arquitetura e riscos.
2. Implementar C1 apenas com placeholder visual/texto de setup, sem QR
   funcional.
3. Implementar C2 com portal mock, sem mexer em rede.
4. Implementar C3 com diagnostico Wi-Fi read-only.
5. So depois planejar C4/C5 para alteracoes reais de NetworkManager e hotspot.
6. Tratar ativacao backend e config writer em C6/C7, com seguranca e rollback
   definidos antes do codigo.
