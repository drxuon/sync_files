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

# Gestione file duplicati in un folder

Nuove funzionalità:

Gestione prefissi/suffissi: Lo script ora riconosce date anche quando sono circondate da testo:

vacanza_2024-03-15_tramonto.jpg
IMG_20240315_120000.jpg
backup_15-03-2024_importante.zip


Gestione duplicati migliorata:

Se trova un file identico nella destinazione, rinomina quello nella sorgente con _DUP
Se trova un file diverso con lo stesso nome, crea una versione numerata nella destinazione


Pattern più robusti: Riconosce più formati di data:

Date europee: DD-MM-YYYY
Date americane: MM-DD-YYYY
Timestamp: YYYYMMDD o YYYY-MM-DD
Con separatori vari: -, _, /



Modalità Dry-Run Aggiunta:
Script principale (organize_files.sh):
bash# Test completo senza modifiche
./organize_files.sh /source /dest --dry-run

# Esecuzione reale
./organize_files.sh /source /dest
Script di test (test_patterns.sh):
bash# Test dettagliato (mostra ogni file)
./test_patterns.sh /source

# Test veloce (solo statistiche + file non riconosciuti)
./test_patterns.sh /source --dry-run
Cosa fa la modalità Dry-Run:

Simula tutto senza fare modifiche reali:

Non crea directory
Non sposta file
Non rinomina duplicati


Report dettagliato come se fosse stato eseguito:

Conta file che verrebbero spostati
Identifica duplicati che verrebbero rinominati
Mostra struttura directory che verrebbe creata


Feedback realistico:

Simula controlli di file esistenti
Mostra messaggi [DRY-RUN] per ogni azione
Include gestione errori simulati



Workflow consigliato:
bash# 1. Test veloce dei pattern
./test_patterns.sh /source --dry-run

# 2. Simulazione completa
./organize_files.sh /source /dest --dry-run

# 3. Esecuzione reale (solo se soddisfatto)
./organize_files.sh /source /dest
Output esempio in dry-run:
=== MODALITÀ DRY-RUN ATTIVA ===
Nessuna modifica verrà effettuata realmente

Processando: vacanza_2024-03-15_tramonto.jpg
  Data trovata (YYYY-MM-DD): 2024-03
  [DRY-RUN] Creerei directory: /dest/2024/03
  [DRY-RUN] Sposterei in: /dest/2024/03/

=== REPORT DRY-RUN COMPLETATO ===
- File che verrebbero spostati: 150
- File che verrebbero saltati/rinominati: 5