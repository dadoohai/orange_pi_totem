# Auditoria independente - operacao

Veredito: aprovar exatamente uma gravacao controlada; nao aprovar baseline nem
distribuicao antes da placa.

O health vermelho observado na prod14 apos o ultimo reboot foi explicado pelo
HDMI fisicamente desconectado: o launcher permaneceu em `display_missing`, sem
restart do servico ou evidencia de regressao do OTA.

Aceite pos-flash minimo: HDMI conectado antes do boot, wizard funcional,
player/deep-health verde, C21.24 presente, C25B exato e congelado, no-op,
rollback, restauracao, reboot e zero unidades systemd falhas.
