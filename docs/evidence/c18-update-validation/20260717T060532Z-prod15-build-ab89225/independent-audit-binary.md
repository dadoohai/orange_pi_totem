# Auditoria independente - imagem binaria

Veredito: nenhum blocker para exatamente uma gravacao controlada; nao e
aprovacao de baseline ou distribuicao.

Confirmado diretamente nas imagens prod14 e prod15:

- tamanho, MBR, tabela de particoes e primeiros 4 MiB preservados;
- ext4 limpo nas duas imagens;
- kernel, U-Boot, DTB, modulos, MPV/FFmpeg e pilha de video preservados;
- player C25B, politica, timers e alvo exato preservados;
- C21.24 e avaliador de playback correspondem ao source esperado;
- apenas marker, core, avaliador e segredo rotacionado mudaram como previsto;
- machine-id vazio e nenhuma SSH host key embutida.

O auditor nao repetiu `zerofree` porque o binario nao estava disponivel em seu
ambiente; o build independente registrou `0/58392/480256` e o filesystem passou
em `e2fsck` novamente.
