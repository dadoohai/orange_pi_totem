# C20.14 Settings Stop Hardening - Board E2E

O pacote exato C20.14 de `totem-core` foi aplicado de forma governada na placa
prod12, exercitado em uma parada real da sessao de configuracao, cancelamento
normal, rollback, reaplicacao e reboot limpo.

## Identidade

- Versao: `c20.14-settings-stop-hardening-20260714T034217Z-22bd473`
- Source commit: `22bd473d2e3e1d026647d6e174f7d9da880c4e8f`
- Payload SHA256: `0653f62863420dcbcdaf051a744484f6a3986850b3da23903311fe2b30056761`
- Manifest SHA256: `0ce5f59c6f4b1d2add98c614c2ee744add9eefe596f3e73a0e6fc8815fc17b73`
- Canal: `homologation`
- Release gate: verde, `84/84`
- Sandbox `totem-core`: verde, incluindo apply, lock guard e rollback

## Resultado Na Placa

1. Com a sessao de configuracao ativa, `systemctl stop` terminou em `8467 ms`,
   abaixo do limite de `15000 ms`, com `Result=success`, `ExecMainStatus=0` e
   sem timeout ou `SIGKILL`.
2. O cleanup encerrou e reaproveitou o filho `openvt`, pulou apenas a espera
   longa incompativel com o stop do systemd, restaurou recursos e enfileirou o
   retorno do player.
3. O cancelamento normal manteve o caminho completo de espera e preservou hash,
   metadados da configuracao ativa e contexto auxiliar.
4. O rollback tornou C20.13 corrente; a reaplicacao restaurou o pacote exato
   C20.14. A policy `stable` original voltou byte a byte.
5. Depois de reboot limpo, C20.14 permaneceu corrente, o player voltou ativo
   com um unico MPV e a coleta final passou com 45 amostras e cinco episodios
   de midia em movimento, sem restart, falha de midia, GPU, MMC ou ext4.

## Negativos Preservados

- A coleta anterior ao reboot ficou vermelha somente porque o boot ainda
  continha dois faults Panfrost historicos, originados na falha C20.13 das
  `03:17:26Z`. Os logs antes/depois de cada exercicio C20.14 sao identicos:
  delta de fault zero.
- A primeira coleta pos-reboot nao conseguiu provar progresso em dois
  episodios curtos na borda de amostragem. A tentativa exploratoria de `0.5 s`
  falhou o limite expresso em numero de amostras para alinhamento status/MPV.
  Nenhuma das duas foi promovida a evidencia positiva.
- A repeticao canonica final passou integralmente e e a evidencia positiva da
  saude apos reboot.

## Mapa De Evidencia

- `package/`: identidade e hash do pacote exato.
- `gates/`: release gate integral e sandbox do componente.
- `board/service-stop/`: precondicoes, tempo, resultado systemd, trace e prova
  de preservacao de configuracao/contexto.
- `board/normal-cancel/`: caminho normal, preservacao de estado e delta GPU.
- `board/rollback-reapply/`: troca reversivel, status e restauracao da policy.
- `board/pre-reboot-health-negative-historic-gpu.json`: negativo historico,
  mantido para nao esconder o fault anterior.
- `board/post-reboot/`: identidade prod12, servicos, dois negativos explicados
  e a coleta final verde.
- `SHA256SUMS`: vinculo de todos os artefatos deste conjunto.

## Non-Claims

- Nao promove C20.14 para `stable` nem habilita publicacao/auto-pull remoto.
- Nao declara prod13 construida ou aceita; C20.14 esta validada para entrar
  nessa proxima imagem de referencia.
- Nao altera nem revalida `player-runtime`, MPV, ffmpeg, kernel, DTB ou U-Boot.
- A placa prod12 e a base fisica desta prova; este conjunto isolado nao substitui
  o aceite integral da futura imagem prod13 gravada do zero.
- Nao inclui config, credencial, token, SSID, URL de midia ou identidade de
  cliente.
