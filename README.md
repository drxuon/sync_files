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

Aggiornamenti al test_patterns.sh:
1. Logica identica di riconoscimento:

Stessi pattern regex di organize_files.sh
Stessa validazione date (anni 1990-corrente)
Stesso fallback per metadati/data modifica
Stessi tipi di file supportati

2. Output migliorato:
Modalità normale:
bash./test_patterns.sh /source

Mostra dettagli per ogni file
Lista file non riconosciuti
Anteprima struttura directory con conteggi
Percentuali di successo

Modalità dry-run:
bash./test_patterns.sh /source --dry-run

Solo statistiche essenziali
Lista file problematici
Output veloce per grandi directory

3. Report dettagliato:
RIEPILOGO:
File totali testati: 1,234
File con data riconosciuta: 1,180
File senza data riconosciuta: 54
Percentuale riconoscimento: 95%

FILE NON RICONOSCIUTI:
✗ documento_senza_data.pdf
✗ file_strano_nome.txt

ANTEPRIMA STRUTTURA DIRECTORY:
2024/03/                 (847 files)
2024/01/                 (156 files)
2023/12/                 (89 files)
...
4. Workflow ottimale:
bash# 1. Test veloce per vedere problemi
./test_patterns.sh /source --dry-run

# 2. Test dettagliato se necessario
./test_patterns.sh /source

# 3. Simulazione organizzazione
./organize_files.sh /source /dest --dry-run

# 4. Esecuzione reale
./organize_files.sh /source /dest
# 5. Suggerimenti automatici:
Lo script ora fornisce consigli per migliorare il riconoscimento quando trova file problematici, suggerendo formati supportati e possibili soluzioni.

