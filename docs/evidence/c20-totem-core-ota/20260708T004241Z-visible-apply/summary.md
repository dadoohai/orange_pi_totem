# C20 Totem-Core Visible Apply

Data: 2026-07-08.

Pacote:
`c20.visual-settings-20260708T003000Z-4e3a13d`.

Objetivo: aplicar o pacote C20 de `totem-core` na placa para inspecao visual
real do wizard/settings atualizado.

Resultado:

- pacote `totem-core` de homologacao gerado a partir de `4e3a13d`;
- gate C18 do manifest/payload passou;
- apply local governado passou;
- `current` da placa virou `c20.visual-settings-20260708T003000Z-4e3a13d`;
- self-test do updater passou;
- self-test do wizard passou;
- player seguiu funcional apos apply;
- captura framebuffer real foi registrada em
  `captures/c20-open-settings-visible.jpg`;
- placa ficou intencionalmente com C20 aplicado e settings aberto para inspecao
  humana.

Observacao de health:

- o deep-health com politica absoluta reprovou porque ja havia contador antigo
  de `panfrost_faults=2`;
- a coleta com politica delta ficou limpa para panfrost, sem restart, sem erro
  de midia, com HW decode esperado e playback progredindo;
- a coleta curta ainda reprovou `transitions_observed_when_required`, porque a
  janela de 10s nao pegou troca de midia. Para esta rodada visual isso nao
  bloqueia o apply C20.

Estado deixado para inspecao:

- `settings.visible-now.active`: `activating`;
- `player.visible-now.active`: `inactive`;
- `timer.visible-now.active`: `inactive`;
- o processo visual do wizard esta ativo em `tty2`.

Pendencia operacional:

- apos a inspeção humana, executar rollback/restauracao ou promover uma decisao
  explicita de manter C20 aplicado;
- consolidar C20 no pacote/update final e na proxima imagem de referencia.

Non-claims:

- nao publicou GitHub Release;
- nao promoveu C20 para `stable`;
- nao validou Wi-Fi real/persistente;
- nao alterou player-runtime, media-system, display/EDID, updater ou imagem.
