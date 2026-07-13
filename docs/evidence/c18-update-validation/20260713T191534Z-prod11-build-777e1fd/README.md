# C18 prod11 - candidato bloqueado antes do flash

O prod11 corrigiu a credencial root herdada e passou a composicao offline, mas
nao deve ser gravado. Auditoria independente da imagem encontrou dois geradores
de identidade SSH no primeiro boot: o inicializador Dadooh cria as chaves antes
do SSH, e o `armbian-firstrun` estava configurado para apaga-las e recria-las
depois que o SSH ja iniciou.

Nenhuma placa recebeu o prod11. A expansao automatica do rootfs foi confirmada e
nao e blocker. A sucessora prod12 deve desativar pela configuracao oficial apenas
a regeneracao de host keys do Armbian, preservar as demais tarefas de primeiro
boot e repetir build e auditoria forense antes de qualquer flash.
