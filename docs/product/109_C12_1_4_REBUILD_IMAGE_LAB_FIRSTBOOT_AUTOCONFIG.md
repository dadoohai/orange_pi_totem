# C12.1.4 - Rebuild Image-Lab com Firstboot Autoconfig

Data: 2026-05-07

## Objetivo

Gerar uma nova imagem-lab bootavel em laboratorio com `firstboot.conf` privado
fora do Git, garantindo caminho de SSH/rede/diagnostico no primeiro boot e
evitando o bloqueio de tela preta/console cru observado em C12.3.2.

## Resultado

C12.1.4 ficou bloqueada antes da geracao da imagem.

O arquivo privado foi validado sem imprimir valores:

- `file_exists=true`;
- `file_secure=true`;
- `parent_secure=true`;
- `owner_current_user=true`;
- `is_symlink=false`;
- `outside_repo=true`;
- `placeholders_present=false`;
- `required_fields_present=true`;
- `network_path_present=true`;
- `can_build_with_lab_firstboot=true`.

O build foi tentado com:

```text
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF=/tmp/dadooh-c12-lab-firstboot/firstboot.conf
```

Mas o ambiente atual nao tem Docker disponivel:

```text
blocker=docker_missing
```

## Classificacao

```text
C12_1_4_BLOCKED_BUILD_ENV_DOCKER_MISSING
```

Nao e falha do `firstboot.conf` privado. Tambem nao e falha de placa, cartao,
Wi-Fi, wizard, writer ou read-only em runtime.

## C12.1.2

A imagem C12.1.2 continua bloqueada/superseded por C12.3.2:

```text
firstboot_bootstrap_missing_or_invalid
```

Ela nao deve ser reutilizada para boot validation.

## Guardrails

- nenhuma placa foi tocada;
- nenhum cartao foi gravado;
- nenhum secret foi publicado;
- o conteudo do `firstboot.conf` privado nao foi impresso;
- config real do player nao foi embutida;
- writer nao foi chamado;
- Wi-Fi/NetworkManager de placa nao foram alterados.

## Proximo Passo

Antes de C12.1.4 gerar imagem, restaurar/preparar o ambiente de build com
Docker disponivel, sem instalar pacotes nas placas e sem rodar upgrades amplos.

Quando Docker estiver disponivel, repetir:

```text
C12_REQUIRE_LAB_FIRSTBOOT_CONF=1
C12_LAB_FIRSTBOOT_CONF=/tmp/dadooh-c12-lab-firstboot/firstboot.conf
scripts/build/run_c12_1_build_image_lab_readonly.sh --build-image
```

Depois validar artefatos e atualizar o manifest com a imagem C12.1.4 real.
