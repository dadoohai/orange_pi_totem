# C18 production image prod12 build

Build offline e quatro revisoes independentes do artefato real que corrige a
dupla regeneracao de identidade SSH encontrada no prod11.

## Resultado

- imagem: `c18-hwdecode-prod-12` / `c18.image-prod.12`;
- commit: `cb894852c81d82ecad9320bb24accac81f1827b6`;
- SHA256: `4bef1f398635f66202c280b33206c4f7e84503c9d0f8734888a5821bae9d8262`;
- bytes: `1971322880`;
- release gate: `82/82`;
- validacao offline: `66/66`;
- auditorias independentes: quatro aprovacoes, zero blockers.

As revisoes recomputaram a cadeia de hashes, inspecionaram o ext4 real,
compararam 35.573 caminhos entre prod11 e prod12 e confirmaram que a unica
mudanca funcional de boot e desativar a regeneracao SSH redundante do Armbian.
O inicializador Dadooh continua sendo o unico dono efetivo das host keys, o SSH
espera por ele, o restante do firstrun foi preservado e a expansao automatica do
rootfs continua habilitada. Escopos, sessoes revisoras e achados estao
preservados em `independent-audit-report.json` e vinculados por hash na decisao.

## Escopo

Esta evidencia autoriza **um unico flash controlado** do hash acima. Ela nao
promove prod12 a referencia de distribuicao. O aceite ainda depende do boot
fisico, expansao do rootfs, fingerprint SSH estavel apos segundo reboot, fluxo
wizard/QR/configuracao, playback/C25 e auto-pull/no-op/rollback dos alvos exatos.
Prod8 continua sendo a referencia vigente ate essas provas terminarem.
