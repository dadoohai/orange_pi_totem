# C20.15 / C21.13 - Board E2E

## Alvo

- versao: `c21.13-wizard-retained-status-20260714T231059Z-81d64ee`
- componente: `totem-core`
- canal: `homologation`
- source commit: `81d64ee9752ade6af53e0a7acc9cb4a83911a50d`
- payload SHA-256: `b6a4ee0f33e0ded8247d4096dab890ef10e0f230548eefcf675ed577945a6132`

## Resultado

`passed=true`. A rodada fechou os tres itens previstos:

1. hora local de Sao Paulo correta no wizard, mantendo o sistema em UTC;
2. resumo com estados confirmado, pendente e bloqueado visualmente distintos;
3. reentrada preserva ambiente e Wi-Fi somente quando o estado ativo e
   comprovado.

O release gate passou `84/84`. O sandbox validou apply, bloqueio durante
settings e rollback. Na placa, apply, rollback e reaplicacao governados
passaram, os hashes de configuracao/contexto/policy foram preservados e o
player nao reiniciou. O E2E visual abriu o wizard real, exibiu a hora correta,
marcou Wi-Fi pendente em amarelo, manteve o ambiente atual em verde, cancelou e
retornou ao player. O deep-health final passou com um MPV, HW decode esperado,
frames avancando e zero restart.

## Limite Honesto

A placa nao tinha perfil Wi-Fi dedicado ativo. O ensaio vivo comprovou que a
ausencia falha fechada e nao cria um falso estado conectado. A retencao positiva
de Wi-Fi ativo foi coberta por self-test, replay e auditoria independente, mas
nao por esta configuracao fisica. A retencao do ambiente foi observada na placa.

C21.13 e uma candidata validada de homologacao. Este registro nao promove
`stable`, nao publica release, nao altera `player-runtime`, kernel, imagem ou
politica publica de OTA. `prod14` + C25B + C21.12 continua sendo a referencia de
distribuicao e rollback.

## Conteudo

- `package/`: identidade exata do pacote;
- `gates/`: release gate e sandbox;
- `board/transaction/`: apply, rollback, reaplicacao e invariantes;
- `board/visual/`: capturas e fluxo real do wizard;
- `board/health/`: saude final do player;
- `board/negative-probe/`: primeira tentativa negativa e sua RCA;
- `offline-visual/`: estados visuais de apoio;
- `audits/`: sintese das auditorias independentes.
