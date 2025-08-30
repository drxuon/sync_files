🔄 Gestione Interruzioni e Ripresa
Funzionamento automatico:

Rilevamento interruzioni: Lo script rileva automaticamente sincronizzazioni incomplete
Ripresa interattiva: Chiede se vuoi riprendere la sincronizzazione interrotta
Skip intelligente: Salta tutti i file già elaborati con successo
Salvataggio progresso: Ogni 10 file processati il progresso viene salvato

Controlli duplicati avanzati:

Verifica per percorso file
Verifica per hash MD5 (anche se il file è stato spostato)
Cache dei file già processati per performance ottimali

🛠️ Nuove Opzioni CLI
bash# Ripresa automatica (chiede conferma)
python nextcloud_sync.py --nextcloud-host server --local-source /path --nextcloud-dest /dest

# Forza nuova sincronizzazione ignorando quelle incomplete  
python nextcloud_sync.py --force-new --nextcloud-host server --local-source /path --nextcloud-dest /dest

# Riprendi sincronizzazione specifica dal database
python nextcloud_sync.py --resume 15 --nextcloud-host server --local-source /path --nextcloud-dest /dest

# Mostra report con info su riprese
python nextcloud_sync.py --show-reports
📊 Database Migliorato
Nuove colonne e tabelle:

already_processed: conta file skippati perché già elaborati
resumed_from_id: traccia da quale sync si è ripreso
processing_status: COMPLETED, INTERRUPTED, ecc.

🚨 Gestione Interruzioni
Ctrl+C durante l'esecuzione:

Salva il progresso attuale
Marca la sync come INTERRUPTED
Mostra ID della sessione per ripresa
Pulisce le connessioni SSH

Esempi di scenari:
bash# Prima esecuzione - si interrompe
python nextcloud_sync.py --nextcloud-host 192.168.1.200 --local-source /home/pi/photos --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos
# Output: "Sincronizzazione interrotta. Progresso salvato (ID: 23)"

# Seconda esecuzione - ripresa automatica
python nextcloud_sync.py --nextcloud-host 192.168.1.200 --local-source /home/pi/photos --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos  
# Output: "Trovata sincronizzazione incompleta (ID: 23). Vuoi riprenderla? (y/n): y"
📈 Report Migliorati
Il report ora include:

File già elaborati (skippati)
Info su riprese da sincronizzazioni precedenti
Stima file rimanenti durante ripresa
ID delle sessioni collegate