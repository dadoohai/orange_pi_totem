# C16.1 Prioritized UX/Product Backlog

## P0

None identified in C16.1.

## P1

### P1-001 - loading_content/player_error

- journey: I/G/T
- problem: A espera por API/cache precisa de teste negativo automatizado antes de ser considerada madura.
- user_hypothesis: Se o backend ou cache falhar, o usuario precisa distinguir espera valida de falha.
- impact: reduz ansiedade e chamados
- effort: medio
- technical_risk: baixo
- requires_core: true
- requires_kiosky_player: true
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: true
- expected_test: simular API indisponivel e sem cache com status publico
- recommendation: schedule_c16_2_or_c17_validation_gate

### P1-002 - wifi_password/wifi_list

- journey: E/F
- problem: Cenarios negativos de Wi-Fi ainda dependem de observacao fisica.
- user_hypothesis: Senha errada e sinal fraco sao erros comuns de instalacao.
- impact: evita loop de suporte no primeiro setup
- effort: medio
- technical_risk: medio
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: true
- expected_test: teste de senha invalida e rede fraca com evidencia sanitizada
- recommendation: schedule_before_or_during_c17_validation

### P1-003 - update_applying/update_failed

- journey: M/N
- problem: O update remoto tem engenharia validada, mas a percepcao visual de update/falha ainda nao tem jornada testada.
- user_hypothesis: Cliente pode interpretar update como travamento.
- impact: aumenta confianca operacional
- effort: medio
- technical_risk: medio
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: true
- expected_test: scenario runner de update check/apply/fail sem aplicar release real
- recommendation: schedule_c16_3_runtime_probe

### P1-004 - boot/saving/starting_player/loading_content

- journey: A/O/H/I
- problem: Flicker/tela preta final exige captura HDMI/camera para decisao perceptiva final.
- user_hypothesis: SSH/timeline nao ve o que o usuario realmente percebe no HDMI.
- impact: fecha lacuna de percepcao antes de despacho amplo
- effort: alto
- technical_risk: baixo
- requires_core: false
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: false
- requires_hdmi_camera: true
- expected_test: metodologia HDMI/camera com checklist e limites
- recommendation: optional_before_c17_required_before_scale

### P1-005 - wizard

- journey: C/L
- problem: O wizard melhorou, mas ainda precisa de avaliacao de consistencia visual por galeria e rubrica por tela.
- user_hypothesis: Fluxo funciona, mas pode parecer ferramenta tecnica em alguns passos.
- impact: melhora profissionalismo sem tocar runtime critico
- effort: baixo
- technical_risk: baixo
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: gallery diff + rubric score minimo 4 para telas criticas
- recommendation: schedule_c16_2_offline_visual_qa

## P2

### P2-001 - wizard_orientation

- journey: C
- problem: Refinar composicao visual do wizard completo.
- user_hypothesis: Instalador confia mais em telas menos densas e mais consistentes.
- impact: polish
- effort: medio
- technical_risk: baixo
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: comparar galeria antes/depois
- recommendation: defer_post_c17_or_remote_update

### P2-002 - config_pending/loading_content/player_error

- journey: B/I/K
- problem: Criar linguagem visual consistente para estados de espera e erro.
- user_hypothesis: O mesmo padrao reduz interpretacao de travamento.
- impact: polish e confianca
- effort: medio
- technical_risk: baixo
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: rubrica por familia de telas
- recommendation: defer_unless_low_risk

### P2-003 - maintenance_support

- journey: Q/P
- problem: Formalizar runbook visual de suporte remoto.
- user_hypothesis: Suporte precisa orientar sem ver HDMI.
- impact: menor tempo de diagnostico
- effort: baixo
- technical_risk: baixo
- requires_core: false
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: status observer + roteiro
- recommendation: defer

### P2-004 - playing

- journey: J
- problem: Separar C18 para timing/sync/looping e percepcao de transicoes entre midias.
- user_hypothesis: Qualidade do playback depende de estabilidade temporal.
- impact: qualidade de produto
- effort: alto
- technical_risk: alto
- requires_core: false
- requires_kiosky_player: true
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: true
- expected_test: C18 dedicated playback audit
- recommendation: defer_to_c18

### P2-005 - offline/cache/no_cache

- journey: R/S/T
- problem: Criar matriz offline/cache sem dados reais.
- user_hypothesis: Sem internet deve parecer estado previsto, nao falha misteriosa.
- impact: robustez percebida
- effort: medio
- technical_risk: medio
- requires_core: true
- requires_kiosky_player: true
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: simulacoes offline com status publico
- recommendation: defer_or_bundle_c16_3

## P3

### P3-001 - design_system

- journey: all
- problem: Criar design system visual do appliance.
- user_hypothesis: Consistencia visual aumenta percepcao premium.
- impact: aspiracional
- effort: alto
- technical_risk: baixo
- requires_core: true
- requires_kiosky_player: false
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: false
- expected_test: tokens, tipografia, grid, estados
- recommendation: defer

### P3-002 - motion

- journey: all
- problem: Microinteracoes e motion design leve.
- user_hypothesis: Transicoes suaves parecem mais profissionais.
- impact: aspiracional
- effort: alto
- technical_risk: medio
- requires_core: true
- requires_kiosky_player: true
- requires_image: false
- remote_update_possible: true
- requires_hdmi_camera: true
- expected_test: camera QA de flicker e fps percebido
- recommendation: defer
