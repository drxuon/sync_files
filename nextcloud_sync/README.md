# ATTENZIONE!!!
Questo è un progetto personale a scopo di studio, non si garantisce in alcun modo il corretto funzionamento. Chi lo usa lo fa a proprio rischio.

# WARNING!!!
This is a personal project for study purposes; proper functioning is not guaranteed in any way. Use it at your own risk.

# Nextcloud Media Sync

Script avanzato per la sincronizzazione di file multimediali da Raspberry Pi a server Nextcloud con gestione intelligente dei duplicati, database SQLite locale, ripresa automatica e modalità dry-run.

## 🚀 Caratteristiche Principali

- **Sincronizzazione intelligente** con rilevamento duplicati tramite hash MD5
- **Database SQLite locale** per tracking completo di file e report
- **Ripresa automatica** dopo interruzioni con skip dei file già elaborati  
- **Modalità dry-run** per testare operazioni senza trasferimenti reali
- **Gestione automatica Nextcloud** con correzione cache e scan files
- **Report dettagliati** con statistiche complete
- **Architettura modulare** per facilità di manutenzione

## 📁 Struttura del Progetto

```
nextcloud_sync/
├── main.py                 # Script principale
├── database_manager.py     # Gestione database SQLite
├── report_manager.py       # Report e statistiche
├── file_utils.py          # Utilità file e hash
├── ssh_manager.py         # Gestione SSH e comandi Nextcloud
├── sync_manager.py        # Gestore principale sincronizzazione
├── requirements.txt       # Dipendenze Python
└── README.md             # Questa documentazione
```

## 🛠 Installazione

### Prerequisiti
- Python 3.7+
- Accesso SSH al server Nextcloud
- Permessi root sul server Nextcloud

### Setup
```bash
# Clona o scarica i file
git clone <repository> # o scarica i file manualmente

# Installa dipendenze
pip install -r requirements.txt

# Rendi eseguibile lo script principale
chmod +x main.py
```

## 📖 Utilizzo

### Comandi Base

```bash
# Sincronizzazione completa
python main.py \
  --nextcloud-host 192.168.1.200 \
  --nextcloud-user root \
  --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos \
  --local-source /home/pi/photos \
  --ssh-key ~/.ssh/id_rsa

# Test con dry-run (consigliato prima della prima esecuzione)
python main.py --dry-run \
  --nextcloud-host server.example.com \
  --local-source /home/pi/media \
  --nextcloud-dest /var/www/nextcloud/data/admin/files/Media
```

### Gestione Interruzioni

```bash
# Se la sincronizzazione si interrompe, al riavvio:
python main.py --nextcloud-host server --local-source /photos --nextcloud-dest /dest
# Output: "Trovata sincronizzazione incompleta (ID: 15). Vuoi riprenderla? (y/n):"

# Forza nuova sincronizzazione ignorando quelle incomplete
python main.py --force-new --nextcloud-host server --local-source /photos --nextcloud-dest /dest

# Riprendi una sincronizzazione specifica
python main.py --resume 15 --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

### Report e Monitoraggio

```bash
# Mostra report delle sincronizzazioni recenti
python main.py --show-reports

# Mostra dettagli di una sincronizzazione specifica
python main.py --show-detail 15

# Output più dettagliato
python main.py --verbose --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

## ⚙️ Opzioni Avanzate

### Estensioni Personalizzate
```bash
# Sincronizza solo immagini JPEG e PNG
python main.py --extensions .jpg .jpeg .png \
  --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

### Database Personalizzato
```bash
# Usa un database specifico
python main.py --db-path /home/pi/sync_history.db \
  --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

## 🗃 Database SQLite

Il database locale contiene tre tabelle principali:

### sync_reports
- ID e timestamp di ogni sincronizzazione
- Statistiche complete (file trasferiti, duplicati, errori)
- Status (RUNNING, COMPLETED, INTERRUPTED, DRY_RUN_COMPLETED)
- Link a sincronizzazioni riprese

### transferred_files
- Dettagli di ogni file trasferito
- Hash MD5 per rilevamento duplicati
- Status di elaborazione (COMPLETED, INTERRUPTED, DRY_RUN)

### sync_errors
- Log completo degli errori con timestamp
- Collegati alla sincronizzazione che li ha generati

## 🔄 Gestione Duplicati

Il sistema rileva duplicati tramite:
1. **Hash MD5**: Confronto del contenuto effettivo dei file
2. **Rinomina automatica**: I duplicati vengono salvati con suffisso `_DUP`
3. **Cache intelligente**: Evita ricalcoli di hash per file già processati

Esempio:
```
IMG001.jpg        # File originale
IMG001_DUP.jpg    # Primo duplicato
IMG001_DUP2.jpg   # Secondo duplicato
```

## 🛡️ Modalità Dry-Run

La modalità dry-run simula tutte le operazioni senza trasferire file:

- ✅ Testa connettività SSH
- ✅ Calcola hash e rileva duplicati
- ✅ Mostra percorsi di destinazione
- ✅ Simula comandi post-sincronizzazione
- ✅ Salva risultati nel database con status `DRY_RUN`

```bash
python main.py --dry-run --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

Output esempio:
```
[DRY-RUN] TRASFERIMENTO SIMULATO: /home/pi/photos/IMG001.jpg
[DRY-RUN] Destinazione: /var/www/nextcloud/data/admin/files/Photos/IMG001.jpg
[DRY-RUN] Dimensione: 2.34 MB  
[DRY-RUN] Hash MD5: a1b2c3d4e5f6...
[DRY-RUN] File unico, verrebbe trasferito normalmente
```

## 🔧 Comandi Post-Sincronizzazione

Lo script esegue automaticamente:

1. **Correzione cache APCu** se non disponibile
2. **Permessi file**: `chmod 644` su tutti i file
3. **Permessi directory**: `chmod 755` su tutte le directory  
4. **Proprietà**: `chown www-data:www-data` ricorsivo
5. **Scan Nextcloud**: `occ files:scan --all` per aggiornare il database

## 📊 Report e Statistiche

### Report Finale
```
REPORT SINCRONIZZAZIONE COMPLETATA
==========================================
Durata: 2.5m
File trasferiti: 1247
Duplicati trovati: 23
Duplicati rinominati: 23  
File già elaborati (skippati): 156
Dimensione totale trasferita: 2.34 GB
Database sync ID: 18
```

### Report Storici
```bash
python main.py --show-reports
```
```
REPORT SINCRONIZZAZIONI RECENTI
=====================================
ID: 18 | Data: 2024-01-15 10:30:00 | Status: COMPLETED
Percorso: /home/pi/photos -> /var/www/nextcloud/data/admin/files/Photos
File trasferiti: 1247 | Duplicati: 23 (23 rinominati)
Dimensione: 2.34 GB | Durata: 2.5m
```

## ⚠️ Gestione Errori

Lo script gestisce robustamente:

- **Interruzioni di rete**: Riconnessione automatica SSH
- **File corrotti**: Skip con log dell'errore  
- **Permessi insufficienti**: Tentativi di correzione automatica
- **Spazio insufficiente**: Rilevamento e report
- **Ctrl+C**: Salvataggio stato e ripresa pulita

Tutti gli errori vengono:
- Loggati nel database con dettagli
- Mostrati nel report finale
- Salvati in `nextcloud_sync.log`

## 🐛 Troubleshooting

### Errore: "Memcache OC\Memcache\APCu not available"
```bash
# Lo script corregge automaticamente, ma manualmente:
sudo apt update && sudo apt install php-apcu
sudo systemctl restart apache2
```

### Errore connessione SSH
```bash
# Verifica connessione manuale
ssh -i ~/.ssh/id_rsa root@192.168.1.200

# Controlla permessi chiave
chmod 600 ~/.ssh/id_rsa
```

### File non visibili in Nextcloud
```bash
# Forza scansione manuale
sudo -u www-data php /var/www/nextcloud/occ files:scan --all
```

## 📝 Log Files

- `nextcloud_sync.log`: Log dettagliato di tutte le operazioni
- `nextcloud_sync.db`: Database SQLite con storico completo

## 🔒 Sicurezza

- Usa sempre chiavi SSH invece di password
- Il database locale contiene hash MD5 (non reversibili)  
- Le connessioni SSH sono crittografate
- I permessi vengono impostati secondo best practice Nextcloud

## 🚦 Exit Codes

- `0`: Successo
- `1`: Errori durante sincronizzazione
- `130`: Interruzione manuale (Ctrl+C)

## 📈 Performance

- **Hash caching**: Evita ricalcoli per file già processati
- **Batch processing**: Salva progresso ogni 10 file
- **Connection pooling**: Riutilizza connessioni SSH
- **Memory efficient**: Processa file uno alla volta

---

## 💡 Suggerimenti

1. **Prima esecuzione**: Usa sempre `--dry-run` per testare
2. **Backup database**: Il file `.db` contiene tutto lo storico
3. **Monitoraggio**: Controlla i log per identificare pattern di errori
4. **Scheduling**: Usa cron per esecuzioni automatiche programmate
5. **Network**: Su reti lente, considera di aumentare i timeout SSH


## 🚀 Caratteristiche del Nuovo Main

### **🎨 UI/UX Migliorata**
- **Banner accattivante** con emoji e layout pulito
- **Argomenti raggruppati** logicamente (Connessione, Percorsi, Opzioni, etc.)
- **Output colorato** con emoji per facile comprensione
- **Conferma interattiva** per sincronizzazioni reali

### **🛡️ Validazioni Robuste**
- **Controllo percorsi** esistenti prima dell'avvio
- **Validazione chiavi SSH** e permessi
- **Verifica argomenti obbligatori** con messaggi chiari
- **Creazione automatica** directory database

### **📋 Configurazione Dettagliata**
```bash
python main.py --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

Output:
```
============================================================
🔄 NEXTCLOUD MEDIA SYNC
   Sincronizzazione intelligente file multimediali
============================================================

📋 CONFIGURAZIONE:
   🖥️  Server Nextcloud: root@192.168.1.200
   📂 Sorgente locale: /home/pi/photos
   📁 Destinazione: /var/www/nextcloud/data/admin/files/Photos
   🔑 Chiave SSH: ~/.ssh/id_rsa
   📄 Estensioni: Tutte le estensioni multimediali
   🗃️  Database: nextcloud_sync.db
   ⚡ Modalità: SINCRONIZZAZIONE REALE
```

### **🎛️ Controlli Avanzati**
- **Conferma utente** per sincronizzazioni reali
- **Gestione interruzioni** con messaggi chiari
- **Exit codes standard** per automazione
- **Modalità verbose** per debug dettagliato

### **📊 Report Integrati**
```bash
# Report recenti con output formattato
python main.py --show-reports

# Dettagli sincronizzazione specifica
python main.py --show-detail 15

# Solo comandi di lettura (senza connessione)
```

### **🔍 Esempi Pratici Integrati**
La help integrata (`--help`) include esempi reali:

```bash
python main.py --help
```

Mostra esempi per:
- 🔍 Test iniziale (DRY-RUN)
- ⚡ Sincronizzazione completa  
- 🔄 Gestione interruzioni
- 📊 Report e monitoraggio
- 🎯 Estensioni specifiche

### **🚦 Gestione Exit Codes**
- `0`: Successo completo
- `1`: Errori durante sincronizzazione
- `130`: Interruzione manuale (Ctrl+C)

### **🛠️ Utilizzo Completo**

```bash
# Test sicuro prima esecuzione
python main.py --dry-run --nextcloud-host server --local-source /photos --nextcloud-dest /dest

# Sincronizzazione completa  
python main.py --nextcloud-host 192.168.1.200 --nextcloud-user root \
               --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos \
               --local-source /home/pi/photos --ssh-key ~/.ssh/id_rsa

# Gestione avanzata
python main.py --verbose --resume 15 --nextcloud-host server --local-source /photos --nextcloud-dest /dest
python main.py --force-new --extensions .jpg .png --nextcloud-host server --local-source /photos --nextcloud-dest /dest
```

