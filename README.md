Database SQLite Locale
Tabelle create automaticamente:

sync_reports: report delle sincronizzazioni con statistiche complete
transferred_files: dettagli di ogni file trasferito con hash e dimensioni
sync_errors: log completo degli errori con timestamp

🔄 Funzionamento Corretto
Flusso operativo:

Script gira sul Raspberry Pi
Legge file locali (struttura anno/mese)
Si connette al server Nextcloud via SSH come root
Scansiona file esistenti sul server e calcola hash
Trasferisce file nuovi, rinomina duplicati
Esegue comandi post-sincronizzazione automaticamente

🛠️ Comandi Post-Sincronizzazione Automatici
Lo script esegue automaticamente:
bash# Permessi file
find /path/dest -type f -exec chmod 644 {} +
# Permessi directory
find /path/dest -type d -exec chmod 755 {} +
# Proprietà a www-data
chown -R www-data:www-data /path/dest
# Aggiornamento database Nextcloud
su -c "php /var/www/nextcloud/occ files:scan --all" www-data -s /bin/bash
📊 Utilizzo
bash# Sincronizzazione completa
python nextcloud_sync.py \
  --nextcloud-host 192.168.1.200 \
  --nextcloud-user root \
  --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos \
  --local-source /home/pi/photos \
  --ssh-key ~/.ssh/id_rsa

# Visualizza report recenti dal database
python nextcloud_sync.py --show-reports

# Con database personalizzato
python nextcloud_sync.py --db-path /home/pi/sync_history.db --show-reports
💾 Database Features

Tracking completo: ogni file trasferito viene registrato con hash, dimensione, timestamp
Gestione errori: tutti gli errori sono loggati con dettagli
Report storici: --show-reports mostra le sincronizzazioni passate
Statistiche: durata, dimensioni, duplicati tutto salvato

🔒 Sicurezza

Connessione SSH con chiave privata o password
Calcolo hash per rilevamento duplicati accurato
Transazioni database per consistenza dati
Log dettagliati per debugging