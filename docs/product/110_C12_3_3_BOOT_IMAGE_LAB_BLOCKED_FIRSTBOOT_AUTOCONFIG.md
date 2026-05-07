# C12.3.3 - Boot Image-Lab Bloqueado por Autoconfig Firstboot

Data: 2026-05-07

## Resultado Observado

A imagem C12.1.4 foi gravada em cartao e bootada em placa de teste.

O boot mostrou uma tela Dadooh com fallback visual:

```text
Bootstrap tecnico pendente
```

Isso confirma duas coisas:

- a imagem nao ficou muda;
- a autoconfig privada de laboratorio nao foi efetiva dentro do boot.

## Classificacao

```text
lab_firstboot_autoconfig_not_effective
```

A C12.1.4 nao deve ser reutilizada como imagem boot-validavel.

## Impacto

Nao houve validacao de:

- SSH/rede de laboratorio;
- wizard;
- F10;
- read-only/overlay;
- player;
- config real.

Nao foi feito:

- provisionamento de config real;
- chamada de writer;
- alteracao de Wi-Fi/NetworkManager em placa;
- nova tentativa read-only pos-instalacao;
- corte seco.

## Proximo Passo

C12.1.5 deve inspecionar a imagem C12.1.4 offline e endurecer o build para que
o proximo artefato prove autoconfig no rootfs real, nao apenas por flags de
manifest.
