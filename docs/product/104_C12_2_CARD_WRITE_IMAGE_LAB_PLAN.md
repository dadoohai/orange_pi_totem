# C12.2 - Plano de Gravacao do Cartao Image-Lab

Data: 2026-05-07

## Objetivo

Gravar a imagem-lab C12.1 em um cartao seguro usando Armbian Imager no Windows.
A validacao de boot/read-only fica para C12.3, salvo autorizacao explicita
posterior. C12.2 ainda nao e imagem final, nao e corte seco e nao provisiona
secrets no primeiro boot.

## Cartao

Usar:

- cartao novo; ou
- cartao descartavel de bancada, explicitamente separado do cartao dev.

Nao usar:

- cartao dev que apresentou fumaca/aquecimento;
- cartao com historico desconhecido;
- cartao contendo config real que precise ser preservada.

## Ferramenta de Gravacao

Ferramenta padrao:

```text
Armbian Imager Windows
```

Procedimento:

1. selecionar imagem local/customizada;
2. selecionar o cartao novo ou descartavel correto;
3. aguardar flash;
4. aguardar verificacao do imager;
5. registrar apenas resultado sanitizado.

Se a imagem for copiada para o Windows, validar SHA256 tambem no destino antes
da gravacao.

## Alvo

Alvo preferencial futuro para C12.3:

```text
placa teste
```

A placa dev fica fora ate reteste fisico com cartao novo.

## Artefato

Imagem:

```text
/home/builder/totem-os/armbian-build-v25.11/output/images/Armbian-unofficial_25.11.1_Orangepizero3_bookworm_current_6.12.58-c12-ro-lab_minimal.img
```

SHA256 esperado:

```text
1b6f5573262d501ae2df6bc3338b56432c8994d4444308caf00347829df08fe2
```

Antes de gravar:

1. confirmar device do cartao de teste;
2. confirmar que nao e disco do computador;
3. confirmar que nao e cartao dev danificado;
4. verificar checksum da imagem;
5. pedir confirmacao humana explicita.

## Validacao Inicial C12.3

Depois de gravar e, apenas em rodada posterior, bootar:

- SSH volta;
- `read_only_enabled=true`;
- `overlay_active=true` ou mecanismo equivalente;
- escrita comum no root bloqueada;
- `/data`, `/tmp` e `/run` gravaveis;
- journald volatil;
- NetworkManager presente;
- player chega a `player_running`/`playing`, se a config permitir;
- F10 abre Configuracoes e cancelar volta ao player, se o appliance estiver
  operacional;
- nenhum segredo e provisionado no primeiro boot.

## Bloqueios Mantidos

- nao fazer corte seco;
- nao usar placa dev;
- nao usar cartao danificado;
- nao provisionar config real no primeiro boot;
- nao publicar secrets;
- nao chamar writer;
- nao alterar Wi-Fi real sem rodada propria.
