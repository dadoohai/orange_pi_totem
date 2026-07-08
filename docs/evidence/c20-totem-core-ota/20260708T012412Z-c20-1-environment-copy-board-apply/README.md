# C20.1 Totem-Core Board Apply

## Resultado

C20.1 foi aplicado na placa por `totem-updatectl apply-local` com `rc=0`.

- Pacote: `c20.1.environment-copy-20260708T011500Z-7a29d1a`
- Payload SHA256: `8c363a44c5c3536453c28ab00297c2e25ecb8244f425173fabd1f056fba4ef31`
- Antes: `releases/c20.visual-settings-20260708T003000Z-4e3a13d`
- Depois: `releases/c20.1.environment-copy-20260708T011500Z-7a29d1a`
- `kiosky-player.service`: ativo antes e depois
- `totem-open-settings.service`: inativo antes e depois
- Wizard instalado: `self-test: ok`

## Evidencia Visual

Captura real do framebuffer da placa:

- `captures/environment-framebuffer-bgr.jpg`

A conversao usa BGR ignorando o quarto byte do framebuffer, porque a captura raw
vem com esse byte zerado e conversoes com alpha produzem imagem branca.

## Escopo

Esta rodada corrige a tela Ambiente e simplifica a orientacao de teclado. A
navegacao livre pelo menu superior fica planejada para uma rodada propria com
estado centralizado (`confirmado`, `default`, `pendente`, `nao_validado`,
`aviso`).
