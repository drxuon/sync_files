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

# Nuove funzionalità versione 8 
Gestione Interruzioni:
Trap per segnali:

Ctrl+C (SIGINT) e SIGTERM vengono catturati
Pulizia ordinata con statistiche parziali
Lista dei file duplicati già processati

Cleanup automatico:
INTERRUZIONE RILEVATA - PULIZIA IN CORSO
==========================================
Operazione interrotta dall'utente

STATISTICHE PARZIALI:
- File processati: 127
- File spostati: 98
- Duplicati rinominati: 5
- Errori: 1
📊 Gestione Duplicati Separata:
Contatori indipendenti:

MOVED: File spostati con successo
SKIPPED: File saltati (date non valide)
DUPLICATES_FOUND: File duplicati rinominati con _DUP
ERRORS: Errori durante l'operazione

Tracciamento duplicati:

Array DUPLICATE_FILES[] tiene traccia di ogni file rinominato
Report finale mostra tutti i duplicati trovati
I duplicati non vengono contati come "saltati"

📈 Progresso e Monitoring:
Indicatore di progresso:

Mostra progresso ogni 50 file processati
Utile per directory con migliaia di file

Report finale dettagliato:
ORGANIZZAZIONE COMPLETATA CON SUCCESSO!
==========================================

STATISTICHE FINALI:
- File spostati con successo: 1,234
- File saltati (data non valida): 45
- File duplicati rinominati: 12
- Errori verificatisi: 0
- Totale file processati: 1,291

FILE DUPLICATI RINOMINATI CON _DUP:
  • photo_2024-03-15_DUP.jpg
  • video_2024-01-20_DUP.mp4
🚨 Gestione Errori Migliorata:
Messaggi informativi:

Avvisi se nessun file viene spostato
Spiegazione possibili cause di problemi
Suggerimenti per risolvere errori

Sicurezza dati:

I duplicati rimangono nella directory sorgente
Nessun file viene mai sovrascritto
Operazioni atomiche per evitare corruzioni

Utilizzo consigliato:
bash# 1. Test rapido
./organize_files.sh /source /dest --dry-run

# 2. Esecuzione (può essere interrotta safely con Ctrl+C)
./organize_files.sh /source /dest

# 3. Se interrotto, rilancia per continuare
./organize_files.sh /source /dest


# Nuove funzionalità versione 9

Sistema di Restart Intelligente:
Checkpoint automatici:

Salvataggio continuo: Dopo ogni file processato
File di stato: /tmp/organize_files_checkpoint_$$
Log processati: /tmp/organize_files_processed_$$

Caricamento automatico:
bash# Prima esecuzione
./organize_files.sh /source /dest

# Interruzione con Ctrl+C
^C
INTERRUZIONE RILEVATA - SALVATAGGIO STATO
📁 Checkpoint salvato in: /tmp/organize_files_checkpoint_12345

# Restart automatico (riprende dal punto esatto)
./organize_files.sh /source /dest
CHECKPOINT TROVATO - CARICAMENTO DATI
Caricati dati sessione precedente:
- File già spostati: 234
- Duplicati già trovati: 5
- File già processati: 239
Riprendendo l'elaborazione...
📊 Gestione Intelligente:
File già processati vengono saltati:

Nessun riprocessamento inutile
Continuità perfetta dall'interruzione
Statistiche cumulative corrette

Salvataggio incrementale:

Checkpoint aggiornato dopo ogni file
Resistente a interruzioni improvvise
Nessuna perdita di progresso

🛠️ Gestore Checkpoint Separato:
bash# Elenca checkpoint attivi
./manage_checkpoints.sh list

# Mostra dettagli specifici  
./manage_checkpoints.sh info 12345

# Pulisce tutto per ricominciare da capo
./manage_checkpoints.sh clean
Output esempio:
CHECKPOINT ATTIVI:
==================
📁 Checkpoint PID: 12345
   File: /tmp/organize_files_checkpoint_12345
   File processati: 234
   Statistiche: 200 spostati, 5 duplicati, 0 errori
🎯 Workflow Completo:
Esecuzione normale:
bash# 1. Test
./organize_files.sh /source /dest --dry-run

# 2. Esecuzione (può essere interrotta)
./organize_files.sh /source /dest

# 3. Se interrotto, riprende automaticamente
./organize_files.sh /source /dest
Gestione manuale:
bash# Controlla stato checkpoint
./manage_checkpoints.sh list

# Ricomincia da capo (opzionale)
./manage_checkpoints.sh clean
./organize_files.sh /source /dest
✨ Vantaggi:

Zero duplicazione: File già processati vengono saltati
Resistente a crash: Salvataggio continuo dello stato
Trasparente: Restart automatico senza configurazione
Sicuro: Checkpoint puliti al completamento
Monitorabile: Tools per ispezionare lo stato

# Nuove funzionalità versione 10

 Funzionalità Complete:
1. Riconoscimento Date Avanzato:

Pattern con prefissi/suffissi: vacanza_2024-03-15_sera.jpg
Formati multipli: DD-MM-YYYY, MM-DD-YYYY, YYYYMMDD
Fallback EXIF e data modifica file
Fix bug ottali (08, 09 ora funzionano)

2. Gestione Duplicati Intelligente:

✅ File già al posto giusto: "File già nella posizione corretta, saltato"
✅ Veri duplicati: Rinomina sorgente con _DUP
✅ File diversi stesso nome: Numerazione destinazione _1, _2

3. Sistema Checkpoint Completo:

Restart automatico dopo interruzione
Nessun file riprocessato due volte
Statistiche cumulative corrette
Cleanup automatico al completamento

4. Modalità Dry-Run:

Simulazione completa senza modifiche
Preview struttura directory
Statistiche dettagliate

5. Gestione Interruzioni:

Ctrl+C sicuro con salvataggio stato
Istruzioni per restart
Cleanup ordinato

🚀 Utilizzo:
bash# 1. Rendi eseguibile
chmod +x organize_files.sh

# 2. Test simulazione
./organize_files.sh /source /dest --dry-run

# 3. Esecuzione reale (interrompibile con Ctrl+C)
./organize_files.sh /source /dest

# 4. Se interrotto, riprende automaticamente
./organize_files.sh /source /dest

📁 File Aggiuntivi:

 gestore checkpoint separato (manage_checkpoints.sh) per:

Visualizzare checkpoint attivi
Pulire checkpoint per ricominciare
Ispezionare dettagli specifici
