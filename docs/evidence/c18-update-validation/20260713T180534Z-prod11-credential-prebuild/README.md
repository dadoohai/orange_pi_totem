# C18 prod11 - governanca da credencial de suporte

Este checkpoint registra somente o processo de geracao. A credencial e seu
hash de verificacao permanecem fora do Git e de evidencias publicas.

O gerador usa 48 bytes do CSPRNG do sistema via `python secrets`, acrescenta
caracteres que garantem as quatro classes e grava credencial e proveniencia em
arquivos separados, ambos `0600`, sob diretorio privado do usuario de build.
O gerador recusa destino dentro do repositorio. O derivador recusa ausencia,
permissao aberta, symlink, hardlink, mudanca durante a leitura, padrao
repetitivo, distribuicao fraca, campos extras ou proveniencia divergente.
