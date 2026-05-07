# C12.3.2 - Boot Image-Lab Bloqueado por Firstboot

Data: 2026-05-07

## Resultado Observado

A imagem-lab C12.1.2 foi gravada e bootada em cartao de teste. O resultado nao
deve ser tratado como freeze do wizard:

- a tela ficou preta;
- F10 apareceu como sequencia de escape no console (`^[[21~`);
- o wizard nao abriu;
- nao havia Wi-Fi configurado;
- SSH nao ficou acessivel;
- nao foi possivel montar o cartao via WSL;
- nao havia Linux nativo disponivel para inspecao offline.

## Classificacao

Classificacao principal:

```text
firstboot_bootstrap_missing_or_invalid
```

O comportamento indica que o teclado estava caindo em console/TTY cru e que a
UI Dadooh nao assumiu. A hipotese principal e que o firstboot gate segurou os
servicos Dadooh enquanto o marcador tecnico Armbian ainda existia, mas a imagem
nao tinha um caminho valido de bootstrap de laboratorio para rede/SSH/UI.

## Decisao

C12.3.2 fica bloqueado. A imagem C12.1.2 nao deve ser reusada para nova
validacao em placa. Nao insistir nesse cartao agora sem SSH/mount e sem Linux
nativo.

Nao foi feito:

- provisionamento de config real;
- chamada de writer;
- alteracao de Wi-Fi/NetworkManager;
- nova tentativa read-only em placa instalada;
- corte seco.

## Estrategia C12.1.3

A estrategia escolhida para a proxima imagem-lab e:

```text
lab_autoconfig_required
```

Para imagem-lab, preferimos autoconfig privado de bancada porque C12 precisa de
SSH/rede no primeiro boot para diagnosticar read-only. A UI Dadooh de firstboot
fica para frente propria de produto, depois que a base lab estiver reprodutivel.

Regras da proxima imagem bootavel:

- build deve receber `C12_LAB_FIRSTBOOT_CONF=/path/privado/firstboot.conf`;
- para build de validacao em placa, usar `C12_REQUIRE_LAB_FIRSTBOOT_CONF=1`;
- o arquivo privado deve ficar fora do Git;
- nenhuma senha, SSID, chave privada, IP, API key, API URL ou environment_id
  real pode ser commitado;
- imagem sem autoconfig privado pode ser construida para auditoria, mas nao
  pode ser marcada como pronta para boot validation.

## Mudancas Preparadas

- o runner de build passa a defaultar a proxima imagem para `c12.1.4`;
- `C12_REQUIRE_LAB_FIRSTBOOT_CONF=1` bloqueia build sem arquivo privado;
- o template `firstboot.conf.template` inclui caminho de rede de laboratorio
  por Wi-Fi/Ethernet com placeholders seguros;
- a validacao de artefatos passa a exigir autoconfig privado para imagem
  bootavel;
- o firstboot gate recebeu fallback textual seguro para evitar tela totalmente
  preta quando o splash visual nao assume.

## Proximo Passo

C12.1.4 deve reconstruir a imagem-lab com arquivo privado de firstboot fora do
Git. Depois disso:

1. C12.2.2 grava um novo cartao;
2. C12.3.3 valida boot com SSH/rede disponivel;
3. somente entao read-only/overlay pode ser reavaliado.

## Atualizacao C12.1.4

O arquivo privado de firstboot foi validado corretamente e a imagem C12.1.4 foi
gerada com autoconfig de laboratorio:

```text
lab_firstboot_autoconfig=true
```

O bloqueio C12.3.2 permanece apenas para a imagem C12.1.2. A proxima acao e
C12.2.2: gravar a imagem C12.1.4 em cartao novo/descartavel.
