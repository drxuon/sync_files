Funzionalità dello script:
🔄 Sincronizzazione intelligente:

Connessione SSH al Raspberry Pi per recuperare i file
Mantiene la struttura delle directory (anno/mese)
Trasferisce solo file multimediali (immagini, video, audio)

🔍 Gestione duplicati:

Calcola hash MD5 per identificare duplicati
Rinomina i duplicati aggiungendo _DUP prima dell'estensione
Evita sovrascritture accidentali

📊 Report dettagliato:

Numero di file trasferiti
Duplicati trovati e rinominati
Dimensione totale trasferita
Errori eventuali
Durata dell'operazione

Installazione dipendenze:
bashpip install paramiko scp
Utilizzo esempio:
bash# Con chiave SSH
python nextcloud_sync.py \
  --source-host 192.168.1.100 \
  --source-user pi \
  --source-path /home/pi/media \
  --dest-path /mnt/nextcloud/media \
  --ssh-key ~/.ssh/id_rsa

# Con password (verrà richiesta)
python nextcloud_sync.py \
  --source-host raspberry.local \
  --source-user pi \
  --source-path /home/pi/photos \
  --dest-path /var/www/nextcloud/data/user/files/Photos
Personalizzazioni possibili:

Estensioni custom: --extensions .jpg .png .mp4
Log dettagliati: salvati in nextcloud_sync.log
Interruzione sicura: i file vengono trasferiti temporaneamente e poi rinominati