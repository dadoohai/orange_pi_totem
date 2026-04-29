# Changelog

## 2026-04-28

### Adicionado

- Documentação inicial da decisão técnica para Orange Pi Zero 3.
- Registro da geração da imagem Candidato A.
- Evidências de boot inicial, reboots curtos e baseline de rede.
- Resultado do teste `stress-ng` de 30 minutos.
- Política explícita de atualização: proibição de `apt upgrade` livre em produção.
- ADRs iniciais para base Armbian, política de update e futura separação `/data` + root read-only.

### Estado

- Candidato A aprovado em triagem inicial.
- Ainda pendente: Wi-Fi real, `/data`, player, vídeo Full HD, root read-only, teste de corte seco e homologação 24h/72h.
