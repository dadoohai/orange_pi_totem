# C25A - Evidencia Visual Off-Board Final

Gerada em `2026-07-13T00:00:44Z` a partir do worktree C25 pre-commit.

Comando reproduzivel:

```bash
python3 scripts/qa/generate_ui_ux_gallery.py \
  --out-dir /tmp/c25-visible-state-gallery \
  --clean-output
```

Resultado:

- 76 SVGs e 76 PNGs, sem falha de raster;
- 18 variantes de estado runtime, paisagem e retrato;
- confirmacao final do wizard em paisagem e retrato;
- saving, sucesso e rejeicao do writer visualmente distintos;
- zero P0 no gate heuristico;
- auditoria independente de geometria SVG e renderer PSF sem overflow.

Os contact sheets preservam as superficies mais relevantes. Os JSONs mantem o
inventario, transicoes, metricas e status de cada raster.

Limites:

- isto prova layout e copy off-board, nao pixels finais vistos pela TV;
- aceite HDMI, handoff sem flicker e rollback na placa ainda sao obrigatorios;
- estados dinamicos enquanto o processo do player possui DRM pertencem a C25B
  (`player-runtime`) e nao sao claim de C25A;
- esta evidencia nao autoriza promocao stable ou imagem de producao.
