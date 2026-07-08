# Prioritized UI/UX backlog

## P0

No items.

## P1

- C15.1.6-P1-001 - Expandir preview padrao de splash para todos os modos publicos
  - severidade=medium esforco=small risco=low recomendacao=defer
  - impacto=Evita lacuna entre modos reais e galeria QA.
  - arquivos_provaveis=scripts/board/totem_visual_splash.py
  - exige_placa=false exige_imagem=false update_remoto=true
- C15.1.6-P1-002 - Adicionar snapshot heuristico de copy/acoes ao self-test do wizard
  - severidade=medium esforco=small risco=low recomendacao=defer
  - impacto=Mantem limite de densidade textual durante ajustes futuros.
  - arquivos_provaveis=scripts/board/totem_setup_visual_wizard.py, scripts/qa/generate_ui_ux_gallery.py
  - exige_placa=false exige_imagem=false update_remoto=true
- C15.1.6-P1-003 - Definir feedback publico para espera de midia/cache/API no player
  - severidade=medium esforco=small risco=medium recomendacao=defer
  - impacto=Reduz risco de tela parecer parada antes do primeiro conteudo.
  - arquivos_provaveis=scripts/board/kiosky_service_launcher.sh, scripts/board/totem_visual_splash.py
  - exige_placa=true exige_imagem=false update_remoto=true
- C15.1.6-P1-004 - Padronizar footers longos em Wi-Fi e senha
  - severidade=low esforco=small risco=low recomendacao=defer
  - impacto=Deixa a UI menos tecnica sem mudar fluxo.
  - arquivos_provaveis=scripts/board/totem_setup_visual_wizard.py
  - exige_placa=false exige_imagem=false update_remoto=true

## P2

- C15.1.6-P2-001 - Criar design system visual do wizard completo
  - severidade=medium esforco=medium risco=medium recomendacao=defer
  - impacto=Evolui de wizard funcional para experiencia mais profissional.
  - arquivos_provaveis=scripts/board/totem_setup_visual_wizard.py
  - exige_placa=false exige_imagem=false update_remoto=true
- C15.1.6-P2-002 - Adicionar QA por captura HDMI ou camera para flicker/transicoes
  - severidade=medium esforco=medium risco=low recomendacao=needs_hardware_capture
  - impacto=Mede percepcao real que SVG offline e SSH nao conseguem provar.
  - arquivos_provaveis=docs/product/142_C15_1_6_AI_ASSISTED_UI_UX_REVIEW.md
  - exige_placa=true exige_imagem=false update_remoto=false

## P3

- C15.1.6-P3-001 - Motion design e microinteracoes premium
  - severidade=low esforco=large risco=medium recomendacao=defer
  - impacto=Aumenta percepcao de produto acabado quando o fluxo base estiver congelado.
  - arquivos_provaveis=scripts/board/totem_setup_visual_wizard.py, scripts/board/totem_visual_splash.py
  - exige_placa=true exige_imagem=false update_remoto=true
