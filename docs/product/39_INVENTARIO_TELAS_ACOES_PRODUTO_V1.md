# Inventario de telas e acoes - Produto V1

Status: inventario de produto. Nao implementa UI funcional.

Data: 2026-05-03

## 1. Objetivo

Este inventario lista telas e acoes esperadas para Produto V1, com objetivo,
usuario, texto, acoes, dados exibidos, dados proibidos, estado tecnico, fase e
recuperacao relacionada.

O inventario orienta prototipos e desenvolvimento futuro. Ele nao cria portal,
nao altera rede, nao escreve config real e nao executa comandos operacionais.

## 2. Dados proibidos globais

Nenhuma tela, acao, evidencia ou diagnostico deve exibir:

- token/API, segredo, header, cookie ou senha;
- URL privada, payload ou resposta bruta de backend;
- `environment_id` real, `station_id` real ou identificador interno real;
- SSID, senha Wi-Fi, IP, hostname, MAC, BSSID, gateway ou DNS real;
- path privado, nome real de midia/campanha/arquivo ou conteudo de config;
- log bruto, stack trace ou comando shell.

Quando a tabela diz "lista global", esses dados continuam proibidos naquela
tela. Telas locais de entrada podem mostrar temporariamente o dado que o
operador esta digitando, mas esse dado nao deve ir para status publico,
diagnostico, screenshot de evidencia ou log.

## 3. Inventario

| Nome | Objetivo | Usuario | Texto principal | Acao primaria | Acao secundaria | Dados exibidos | Dados proibidos | Estado tecnico | Fase | Recuperacao |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Inicializando | Sinalizar que o produto esta subindo. | Todos | "Dadooh / inicializando" | Aguardar | Nenhuma | Marca, estado publico, indicador simples | Lista global | `booting` | MVP/V1 | Nivel 1 |
| Sem HDMI | Registrar ausencia de display. | Operador local, suporte | "Tela nao detectada" | Verificar cabo/tela | Diagnostico local futuro | Codigo publico `DISPLAY_MISSING`, acao curta | Lista global e qualquer detalhe bruto de DRM | `display_missing` | MVP/V1 | Nivel 1/2 |
| Configuracao pendente | Explicar que player esta bloqueado por falta de config valida. | Operador de instalacao | "Configuracao pendente" | Iniciar configuracao | Abrir manutencao autorizada | Estado publico, codigo `CONFIG_MISSING` | Lista global e conteudo de config | `config_missing` | MVP/V1 | Nivel 2 |
| Iniciar configuracao | Entrada para setup guiado. | Operador de instalacao | "Iniciar configuracao" | Comecar | Voltar/aguardar | Etapas previstas sem dados reais | Lista global | `setup_start` | MVP/V1 | Nivel 2 |
| Conexao | Explicar etapa de conectividade. | Operador de instalacao | "Conectar o totem" | Escolher conexao | Pular apenas em mock autorizado | Opcoes genericas: cabo, Wi-Fi, setup futuro | Lista global | `network_setup` | MVP mock/V1 | Nivel 2 |
| Wi-Fi | Selecionar rede em fase futura. | Operador de instalacao | "Escolha a rede" | Selecionar rede | Atualizar lista/voltar | Redes ficticias no prototipo; lista local controlada no futuro | Lista global; SSID real fora de evidencia | `wifi_select` | V1 final | Nivel 2 |
| Testando conexao | Mostrar progresso de teste. | Operador de instalacao | "Testando conexao" | Aguardar | Cancelar/voltar se permitido | Estado agregado de teste | Lista global, erro bruto de rede, IP, DNS, URL | `wifi_testing` | V1 final | Nivel 1/2 |
| Conexao limitada | Tratar rede sem internet/backend. | Operador local | "Conexao limitada" | Tentar novamente | Trocar rede | Codigo publico, estado agregado | Lista global, endpoint, DNS, gateway, erro bruto | `network_limited` | V1 final | Nivel 2 |
| Ativacao | Autorizar/provisionar totem. | Operador de instalacao | "Ativar totem" | Inserir codigo/login futuro | Tentar novamente/chamar suporte | Codigo publico, instrucoes curtas | Lista global; token/API nunca visivel | `activation_pending` | V1 final | Nivel 2 |
| Login/codigo futuro | Capturar autorizacao humana. | Operador de instalacao/admin | "Entre ou informe o codigo" | Continuar | Voltar | Codigo temporario mascarado ou login publico futuro | Lista global, senha em evidencia, token emitido | `activation_pending` | V1 final | Nivel 2 |
| Selecao de ambiente | Escolher destino operacional. | Operador de instalacao | "Selecione o ambiente" | Confirmar ambiente | Voltar | Nomes publicos autorizados ou placeholders | Lista global; IDs reais fora de evidencia | `environment_select` | V1 final | Nivel 2 |
| Ambiente manual temporario | Permitir MVP sem backend/lista. | Operador de instalacao | "Informe o ambiente" | Validar | Voltar | Placeholder ou valor local temporario | Lista global; valor real fora de docs/evidencia | `environment_input` | MVP | Nivel 2 |
| Rotacao de tela | Ajustar orientacao fisica. | Operador de instalacao | "Orientacao da tela" | Confirmar orientacao | Voltar | 0/90/180/270 ou retrato/paisagem | Lista global | `rotation_select` | MVP mock/V1 | Nivel 2 |
| Revisao | Confirmar antes de salvar. | Operador de instalacao | "Revisar configuracao" | Salvar | Voltar | Resumo sem segredo: conexao ok, ambiente publico/mock, orientacao | Lista global; token, URL, ID real, senha | `review` | MVP/V1 | Nivel 2 |
| Salvando configuracao | Mostrar progresso de escrita. | Operador de instalacao | "Salvando configuracao" | Aguardar | Cancelar apenas antes do ponto seguro | Progresso publico | Lista global, JSON, paths reais, output do writer | `config_saving` | MVP/V1 | Nivel 1 |
| Iniciando exibicao | Transicao entre setup e player. | Todos | "Iniciando exibicao" | Aguardar | Nenhuma | Estado publico | Lista global | `starting_player` | MVP/V1 | Nivel 1 |
| Player rodando | Estado normal de operacao. | Operador local | "Exibicao em andamento" | Nenhuma | Manutencao autorizada | Conteudo do player e, se necessario, estado publico minimo | Lista global no status/overlay | `player_running` | MVP/V1 | Nivel 1 |
| Erro do player | Tornar falha recuperavel. | Operador local, suporte | "Exibicao temporariamente indisponivel" | Tentar novamente | Diagnostico/manutencao | Codigo publico como `PLAYER_EXITED` | Lista global, log bruto, path de midia | `player_error` | V1 final | Nivel 1/2 |
| Manutencao | Acesso a acoes limitadas. | Operador autorizado, suporte | "Manutencao" | Ver diagnostico | Sair/voltar a exibicao | Estado publico, acoes permitidas | Lista global, shell, comandos livres | `maintenance` | V1 final | Nivel 2/3 |
| Diagnostico | Gerar resumo seguro. | Suporte, operador orientado | "Diagnostico" | Gerar/mostrar codigo | Voltar | Snapshot sanitizado, versoes publicas, codigos | Lista global, config, status bruto, journal bruto | `diagnostics` | V1 final | Nivel 2 |
| Trocar ambiente | Alterar ambiente apos instalacao. | Operador autorizado, suporte | "Trocar ambiente" | Selecionar novo ambiente | Cancelar | Ambientes publicos autorizados | Lista global; IDs reais fora de evidencia | `environment_change` | V1 final | Nivel 2 |
| Trocar rede | Corrigir conectividade. | Operador autorizado | "Trocar rede" | Configurar nova rede | Cancelar | Estado agregado de rede | Lista global; SSID real em evidencia, senha | `network_change` | V1 final | Nivel 2 |
| Reiniciar exibicao | Reiniciar player sem apagar dados. | Operador local, suporte | "Reiniciar exibicao" | Confirmar reinicio | Cancelar | Impacto: exibicao pausada brevemente | Lista global | `restarting_player` | MVP/V1 | Nivel 2 |
| Reset de configuracao | Voltar setup removendo config operacional. | Operador autorizado, suporte | "Limpar configuracao" | Confirmar | Cancelar | O que sera apagado/preservado | Lista global, conteudo da config/backup | `config_reset_confirm` | MVP doc/V1 | Nivel 2 |
| Reset de rede | Remover credencial/perfil do produto. | Operador autorizado, suporte | "Limpar rede" | Confirmar | Cancelar | Impacto: sera necessario conectar de novo | Lista global, SSID/senha/perfil real | `network_reset_confirm` | V1 final | Nivel 2 |
| Limpar cache | Remover conteudo local baixado. | Suporte, operador autorizado | "Limpar cache" | Confirmar | Cancelar | Impacto: conteudo sera baixado novamente | Lista global, nomes/paths de midia | `cache_reset_confirm` | V1 final | Nivel 2 |
| Factory reset | Voltar produto para setup inicial. | Suporte autorizado | "Factory reset" | Confirmar fortemente | Cancelar/exportar diagnostico | Escopo de limpeza em linguagem simples | Lista global, shell, config/backup bruto | `factory_reset_confirm` | V1 final | Nivel 3/4 |
| Hard reset local | Recuperar quando UI/rede falham. | Suporte presencial, operador treinado | "Modo de recuperacao" | Acionar metodo fisico aprovado | Cancelar quando possivel | Instrucoes publicas e codigo de estado | Lista global, comandos internos | `hard_reset_requested` | V1 final | Nivel 3 |
| Restaurar sistema/app | Recuperar app/sistema apos falha de update. | Suporte presencial/avancado | "Restaurar sistema" | Restaurar release/imagem | Factory reset se necessario | Versao publica atual/anterior, healthcheck publico | Lista global, paths privados, logs brutos | `recovery`/`app_rollback` | V1 final | Nivel 4 |

## 4. Lacunas antes de implementacao

- Entrada segura em manutencao.
- Metodo fisico de hard reset.
- Contrato final de telas de rotacao.
- Politica de nomes publicos de ambiente.
- Escopo exato de cada reset.
- Exportacao de diagnostico sem dados sensiveis.
- Aplicacao tecnica de rotacao.
- Integracao real com writer/config sem player e setup disputarem tela.
