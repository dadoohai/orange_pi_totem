# RCA - Primeira Tentativa Visual

## Sintoma

O primeiro probe nao observou o wizard e encerrou negativo antes de qualquer
interacao de usuario.

## Causa Verificada

O proprio harness criava os diretorios temporarios da sessao com modo `0755`.
O launcher endurecido exige diretorios privados `0700` e recusou corretamente a
sessao. Nao houve falha do wizard nem regressao do produto; houve
incompatibilidade entre o probe antigo e a protecao atual.

## Correcao

O harness passou a criar os diretorios com `install -d -m 0700` e a aguardar a
finalizacao real do servico de settings. O ensaio seguinte abriu o wizard,
navegou ate a revisao, cancelou, restaurou o player e terminou verde.

Os artefatos negativos foram preservados neste diretorio para manter a trilha
honesta da campanha.
