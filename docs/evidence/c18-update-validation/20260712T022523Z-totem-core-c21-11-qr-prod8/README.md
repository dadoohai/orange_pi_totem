# C21.11 QR pairing - local board validation

Status em 2026-07-12: candidata validada localmente e restaurada; ainda nao
publicada.

## Resultado

- pacote stable: `c21.11-qr-pairing-20260712T021729Z-4068839`;
- source commit: `4068839c6e82545c0ad8805653c277787ace6da6`;
- payload SHA256: `8cb669b75ac446f5992da5237c981473dbd3dddc823beea326da2c53063ce27c`;
- apply-local na imagem `c18-hwdecode-prod-8`: passou;
- self-tests do wizard e QR na placa: passaram;
- segunda aplicacao do mesmo pacote: no-op;
- rollback para C21.10: passou;
- player permaneceu ativo, sem restart, e player-runtime continuou congelado
  com rc=44;
- placa terminou novamente em C21.10, como estava antes da operacao.

## Limite

Esta rodada prova o pacote e o rollback local. Ela nao prova o download pelo
timer porque C21.11 ainda nao foi publicada. O gate de timer deve ser executado
somente depois da publicacao e do apply remoto.

## Dependencias externas antes da publicacao

- Home Dadooh na EC2 precisa estar em `5ca00bb` e aceitar URL apenas com
  `code`;
- a autenticacao do Firebase CLI precisa ser renovada;
- o backend `bf4065c` deve ser implantado como candidata sem trafego, auditado
  e promovido somente depois do Home.

