# C21.11 QR pairing - local board validation

Status em 2026-07-12: fechado. Pacote, Home, backend, pareamento real,
publicacao stable e auto-pull validados.

## Resultado

- pacote stable: `c21.11-qr-pairing-20260712T021729Z-4068839`;
- source commit: `4068839c6e82545c0ad8805653c277787ace6da6`;
- payload SHA256: `8cb669b75ac446f5992da5237c981473dbd3dddc823beea326da2c53063ce27c`;
- apply-local na imagem `c18-hwdecode-prod-8`: passou;
- self-tests do wizard e QR na placa: passaram;
- segunda aplicacao do mesmo pacote: no-op;
- rollback para C21.10: passou;
- Home Dadooh aceitou entrada manual, URL somente com `code` e URL legada;
- backend integrado ao `main` foi implantado em `api-00481-naf`;
- source generation implantado bateu com o Git e nao conteve `.env`;
- captura real do framebuffer foi decodificada como
  `https://home.dadooh.ai/totem/activate?code=8SC6Z9JM`;
- autorizacao foi consumida pela placa com resultado publico sanitizado e
  credencial somente em arquivo privado 0600;
- player permaneceu ativo, sem restart, e player-runtime continuou congelado
  com rc=44;
- C21.11 foi reaplicada localmente para a prova real.
- GitHub Release C21.11 foi publicada como `latest`, sem draft/prerelease;
- timer selecionou C21.11 e fez no-op;
- rollback voltou a C21.10;
- timer baixou o payload remoto, verificou SHA256 e restaurou C21.11;
- no-op remoto final e gate de evidencia do timer passaram sem blockers.

## Limite

Esta rodada prova o pacote, rollback local, pareamento real e download pelo
timer. Ela nao muda player-runtime, media-system ou imagem base.

O HDMI estava desconectado. O framebuffer foi usado como evidencia tecnica,
mas nao substitui observacao fisica. O wizard nao salvou configuracao final:
a revisao mostrou Wi-Fi pendente enquanto a placa usava Ethernet, e a sessao
foi cancelada de forma limpa.

## Restante nao bloqueante

- repetir a observacao visual fisica quando o HDMI estiver disponivel;
- o salvamento final do wizard nao foi repetido nesta rodada porque a revisao
  exigiu Wi-Fi e a placa estava somente em Ethernet;
- atualizar Node.js 20 antes da data de desativacao de deploy informada pelo
  Firebase (2026-10-30).
