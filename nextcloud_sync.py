#!/usr/bin/env python3
"""
Script per sincronizzazione file multimediali da Raspberry Pi a Nextcloud
con gestione duplicati, database SQLite locale e comandi post-sync
"""

import os
import hashlib
import logging
import sqlite3
from pathlib import Path
from collections import defaultdict
import argparse
from datetime import datetime
import paramiko
from scp import SCPClient
import json

class DatabaseManager:
    def __init__(self, db_path="nextcloud_sync.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inizializza il database SQLite con le tabelle necessarie"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Tabella per i report di sincronizzazione
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    files_transferred INTEGER DEFAULT 0,
                    duplicates_found INTEGER DEFAULT 0,
                    duplicates_renamed INTEGER DEFAULT 0,
                    errors_count INTEGER DEFAULT 0,
                    skipped_files INTEGER DEFAULT 0,
                    already_processed INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0,
                    duration_seconds REAL,
                    source_path TEXT,
                    dest_path TEXT,
                    status TEXT,
                    resumed_from_id INTEGER
                )
            ''')
            
            # Tabella per i dettagli dei file trasferiti
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transferred_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_id INTEGER,
                    source_file TEXT,
                    dest_file TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    transfer_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_duplicate BOOLEAN DEFAULT FALSE,
                    processing_status TEXT DEFAULT 'COMPLETED',
                    FOREIGN KEY (sync_id) REFERENCES sync_reports (id)
                )
            ''')
            
            # Tabella per gli errori
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sync_errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_id INTEGER,
                    error_message TEXT,
                    file_path TEXT,
                    error_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (sync_id) REFERENCES sync_reports (id)
                )
            ''')
            
            conn.commit()
    
    def start_sync_session(self, source_path, dest_path, resumed_from=None):
        """Inizia una nuova sessione di sincronizzazione"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_reports (source_path, dest_path, status, resumed_from_id)
                VALUES (?, ?, 'RUNNING', ?)
            ''', (str(source_path), str(dest_path), resumed_from))
            return cursor.lastrowid
    
    def update_sync_report(self, sync_id, report, duration_seconds, status='COMPLETED'):
        """Aggiorna il report di sincronizzazione"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sync_reports SET
                    files_transferred = ?,
                    duplicates_found = ?,
                    duplicates_renamed = ?,
                    errors_count = ?,
                    skipped_files = ?,
                    already_processed = ?,
                    total_size_bytes = ?,
                    duration_seconds = ?,
                    status = ?
                WHERE id = ?
            ''', (
                report.files_transferred,
                report.duplicates_found, 
                report.duplicates_renamed,
                len(report.errors),
                report.skipped_files,
                report.already_processed,
                report.total_size_transferred,
                duration_seconds,
                status,
                sync_id
            ))
    
    def log_transferred_file(self, sync_id, source_file, dest_file, file_hash, file_size, is_duplicate=False, status='COMPLETED'):
        """Registra un file trasferito"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transferred_files 
                (sync_id, source_file, dest_file, file_hash, file_size, is_duplicate, processing_status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (sync_id, str(source_file), str(dest_file), file_hash, file_size, is_duplicate, status))
    
    def log_error(self, sync_id, error_message, file_path=None):
        """Registra un errore"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_errors (sync_id, error_message, file_path)
                VALUES (?, ?, ?)
            ''', (sync_id, error_message, str(file_path) if file_path else None))
    
    def get_recent_reports(self, limit=10):
        """Ottiene i report più recenti"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM sync_reports 
                ORDER BY sync_date DESC 
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
    
    def find_incomplete_sync(self, source_path, dest_path):
        """Trova una sincronizzazione incompleta per lo stesso percorso"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM sync_reports 
                WHERE source_path = ? AND dest_path = ? AND status IN ('RUNNING', 'INTERRUPTED')
                ORDER BY sync_date DESC LIMIT 1
            ''', (str(source_path), str(dest_path)))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_processed_files(self, sync_ids):
        """Ottiene i file già elaborati nelle sincronizzazioni precedenti"""
        if not sync_ids:
            return set()
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            placeholders = ','.join('?' * len(sync_ids))
            cursor.execute(f'''
                SELECT DISTINCT source_file FROM transferred_files 
                WHERE sync_id IN ({placeholders}) AND processing_status = 'COMPLETED'
            ''', sync_ids)
            return {row[0] for row in cursor.fetchall()}
    
    def mark_sync_interrupted(self, sync_id):
        """Marca una sincronizzazione come interrotta"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE sync_reports SET status = 'INTERRUPTED' WHERE id = ?
            ''', (sync_id,))
    
    def get_all_previous_processed_files(self, source_path, dest_path, exclude_sync_id=None):
        """Ottiene tutti i file già elaborati per questo percorso (da tutte le sync precedenti)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            query = '''
                SELECT DISTINCT tf.source_file, tf.file_hash 
                FROM transferred_files tf
                JOIN sync_reports sr ON tf.sync_id = sr.id
                WHERE sr.source_path = ? AND sr.dest_path = ? 
                AND tf.processing_status = 'COMPLETED'
            '''
            params = [str(source_path), str(dest_path)]
            
            if exclude_sync_id:
                query += ' AND tf.sync_id != ?'
                params.append(exclude_sync_id)
            
            cursor.execute(query, params)
            return {row[0]: row[1] for row in cursor.fetchall()}

class MediaSyncReport:
    def __init__(self):
        self.files_transferred = 0
        self.duplicates_found = 0
        self.duplicates_renamed = 0
        self.errors = []
        self.skipped_files = 0
        self.already_processed = 0
        self.total_size_transferred = 0
        
    def add_transferred(self, file_size):
        self.files_transferred += 1
        self.total_size_transferred += file_size
        
    def add_duplicate(self):
        self.duplicates_found += 1
        
    def add_renamed_duplicate(self):
        self.duplicates_renamed += 1
        
    def add_error(self, error_msg):
        self.errors.append(error_msg)
        
    def add_skipped(self):
        self.skipped_files += 1
    
    def add_already_processed(self):
        self.already_processed += 1

class NextcloudMediaSync:
    def __init__(self, nextcloud_host, nextcloud_user, nextcloud_dest_path, 
                 local_source_path, ssh_key_path=None, extensions=None, db_path=None, dry_run=False):
        """
        Inizializza il sincronizzatore
        
        Args:
            nextcloud_host: IP/hostname del server Nextcloud
            nextcloud_user: username SSH per il server Nextcloud (di solito root)
            nextcloud_dest_path: percorso di destinazione su Nextcloud
            local_source_path: percorso locale dei file sul Raspberry Pi
            ssh_key_path: percorso della chiave SSH (opzionale)
            extensions: lista delle estensioni da sincronizzare
            db_path: percorso del database SQLite
            dry_run: se True, simula le operazioni senza trasferire file
        """
        self.nextcloud_host = nextcloud_host
        self.nextcloud_user = nextcloud_user
        self.nextcloud_dest_path = Path(nextcloud_dest_path)
        self.local_source_path = Path(local_source_path)
        self.ssh_key_path = ssh_key_path
        self.dry_run = dry_run
        
        # Estensioni multimediali supportate
        self.extensions = extensions or [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Immagini
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',    # Video
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'            # Audio
        ]
        
        self.report = MediaSyncReport()
        self.remote_file_hashes = {}  # Cache degli hash dei file remoti
        self.processed_files = set()  # File già elaborati in precedenza
        
        # Database manager
        self.db = DatabaseManager(db_path or "nextcloud_sync.db")
        self.sync_id = None
        self.resumed_from_id = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('nextcloud_sync.log'),
                logging.StreamHandler()
            ]
        )
    def check_for_resume(self):
        """Controlla se esiste una sincronizzazione interrotta da riprendere"""
        incomplete_sync_id = self.db.find_incomplete_sync(self.local_source_path, self.nextcloud_dest_path)
        
        if incomplete_sync_id:
            response = input(f"Trovata sincronizzazione incompleta (ID: {incomplete_sync_id}). Vuoi riprenderla? (y/n): ")
            if response.lower() in ['y', 'yes', 's', 'si']:
                self.resumed_from_id = incomplete_sync_id
                # Carica i file già elaborati
                self.processed_files = self.db.get_all_previous_processed_files(
                    self.local_source_path, 
                    self.nextcloud_dest_path,
                    exclude_sync_id=incomplete_sync_id
                )
                
                # Includi anche i file della sessione interrotta se completati
                interrupted_files = self.db.get_processed_files([incomplete_sync_id])
                self.processed_files.update(interrupted_files)
                
                self.logger.info(f"Ripresa sincronizzazione: {len(self.processed_files)} file già elaborati verranno skippati")
                return True
            else:
                # Marca come interrotta definitivamente
                self.db.mark_sync_interrupted(incomplete_sync_id)
                
        return False
    
    def is_file_already_processed(self, file_path, file_hash=None):
        """Verifica se un file è già stato elaborato in precedenza"""
        file_path_str = str(file_path)
        
        # Controllo veloce per percorso
        if file_path_str in self.processed_files:
            return True
        
        # Se abbiamo l'hash, controlliamo anche quello
        if file_hash:
            processed_with_hash = self.db.get_all_previous_processed_files(
                self.local_source_path, 
                self.nextcloud_dest_path
            )
            for processed_path, processed_hash in processed_with_hash.items():
                if processed_hash == file_hash:
                    return True
        
        return False
        
    def calculate_file_hash(self, file_path, chunk_size=8192):
        """Calcola l'hash MD5 di un file locale"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Errore nel calcolo hash per {file_path}: {e}")
            return None
    
    def calculate_remote_file_hash(self, remote_path):
        """Calcola l'hash MD5 di un file remoto via SSH"""
        try:
            cmd = f"md5sum '{remote_path}' | cut -d' ' -f1"
            stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
            hash_result = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if error:
                self.logger.warning(f"Warning calcolo hash remoto {remote_path}: {error}")
                return None
                
            return hash_result if hash_result else None
            
        except Exception as e:
            self.logger.error(f"Errore calcolo hash remoto {remote_path}: {e}")
            return None
    
    def is_media_file(self, file_path):
        """Verifica se il file è multimediale"""
        return any(str(file_path).lower().endswith(ext) for ext in self.extensions)
    
    def generate_duplicate_name(self, remote_path):
        """Genera un nome per file duplicato aggiungendo _DUP prima dell'estensione"""
        path_obj = Path(remote_path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_DUP{counter if counter > 1 else ''}{suffix}"
            new_path = parent / new_name
            
            if self.dry_run:
                # In dry-run, simula che il file non esiste
                return new_path
            
            # Verifica se esiste sul server remoto
            check_cmd = f"test -f '{new_path}' && echo 'exists' || echo 'not_exists'"
            stdin, stdout, stderr = self.ssh_client.exec_command(check_cmd)
            result = stdout.read().decode().strip()
            
            if result == 'not_exists':
                return new_path
            counter += 1
    
    def scan_remote_files(self):
        """Scansiona i file esistenti sul server Nextcloud e calcola i loro hash"""
        self.logger.info("Scansione file esistenti sul server Nextcloud...")
        
        if self.dry_run:
            self.logger.info("[DRY-RUN] Simulando scansione file remoti...")
            # In dry-run, simula alcuni file esistenti per test
            return
        
        try:
            # Crea la directory di destinazione se non esiste
            mkdir_cmd = f"mkdir -p '{self.nextcloud_dest_path}'"
            self.ssh_client.exec_command(mkdir_cmd)
            
            # Trova tutti i file multimediali esistenti
            extensions_pattern = " -o ".join([f"-name '*.{ext[1:]}'" for ext in self.extensions])
            find_cmd = f"find '{self.nextcloud_dest_path}' -type f \\( {extensions_pattern} \\)"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(find_cmd)
            existing_files = stdout.read().decode().strip().split('\n')
            existing_files = [f for f in existing_files if f.strip()]
            
            self.logger.info(f"Trovati {len(existing_files)} file esistenti sul server")
            
            # Calcola hash per ogni file esistente
            for i, file_path in enumerate(existing_files, 1):
                if i % 50 == 0:  # Log progresso ogni 50 file
                    self.logger.info(f"Calcolando hash: {i}/{len(existing_files)}")
                    
                file_hash = self.calculate_remote_file_hash(file_path)
                if file_hash:
                    self.remote_file_hashes[file_hash] = file_path
                    
        except Exception as e:
            self.logger.error(f"Errore scansione file remoti: {e}")
            self.db.log_error(self.sync_id, f"Scansione file remoti: {e}")
    
    def connect_ssh(self):
        """Stabilisce connessione SSH al server Nextcloud"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.ssh_key_path:
                self.ssh_client.connect(
                    self.nextcloud_host, 
                    username=self.nextcloud_user, 
                    key_filename=self.ssh_key_path
                )
            else:
                password = input(f"Password per {self.nextcloud_user}@{self.nextcloud_host}: ")
                self.ssh_client.connect(
                    self.nextcloud_host, 
                    username=self.nextcloud_user, 
                    password=password
                )
                
            self.logger.info(f"Connessione SSH stabilita con {self.nextcloud_host}")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore connessione SSH: {e}")
            self.report.add_error(f"Connessione SSH fallita: {e}")
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Connessione SSH: {e}")
            return False
    
    def get_local_files(self):
        """Ottiene la lista dei file multimediali locali"""
        try:
            local_files = []
            for file_path in self.local_source_path.rglob('*'):
                if file_path.is_file() and self.is_media_file(file_path):
                    local_files.append(file_path)
            
            self.logger.info(f"Trovati {len(local_files)} file multimediali locali")
            return local_files
            
        except Exception as e:
            self.logger.error(f"Errore nel recupero file locali: {e}")
            self.report.add_error(f"Recupero file locali fallito: {e}")
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Recupero file locali: {e}")
            return []
    
    def transfer_file(self, local_file_path):
        """Trasferisce un singolo file al server Nextcloud"""
        try:
            # Controllo se file già elaborato
            if self.is_file_already_processed(local_file_path):
                self.report.add_already_processed()
                self.logger.info(f"File già elaborato, skipping: {local_file_path}")
                return True
            
            # Calcola hash del file locale prima del controllo duplicati più preciso
            file_hash = self.calculate_file_hash(local_file_path)
            if not file_hash:
                self.report.add_error(f"Impossibile calcolare hash per {local_file_path}")
                if self.sync_id:
                    self.db.log_error(self.sync_id, f"Calcolo hash fallito", local_file_path)
                return False
            
            # Controllo più accurato con hash
            if self.is_file_already_processed(local_file_path, file_hash):
                self.report.add_already_processed()
                self.logger.info(f"File già elaborato (hash match), skipping: {local_file_path}")
                return True
                
            # Calcola il percorso di destinazione mantenendo la struttura
            try:
                relative_path = local_file_path.relative_to(self.local_source_path)
            except ValueError:
                relative_path = local_file_path.name
            
            remote_dest_path = self.nextcloud_dest_path / relative_path
            
            # Statistiche del file
            file_size = local_file_path.stat().st_size
            
            if self.dry_run:
                # MODALITÀ DRY-RUN - Simula operazioni senza eseguirle
                self.logger.info(f"[DRY-RUN] TRASFERIMENTO SIMULATO: {local_file_path}")
                self.logger.info(f"[DRY-RUN] Destinazione: {remote_dest_path}")
                self.logger.info(f"[DRY-RUN] Dimensione: {self.format_size(file_size)}")
                self.logger.info(f"[DRY-RUN] Hash MD5: {file_hash}")
                
                # Simula controllo duplicati
                is_duplicate = file_hash in self.remote_file_hashes
                if is_duplicate:
                    existing_file = self.remote_file_hashes[file_hash]
                    self.logger.info(f"[DRY-RUN] DUPLICATO RILEVATO: esiste già come {existing_file}")
                    final_remote_path = self.generate_duplicate_name(remote_dest_path)
                    self.logger.info(f"[DRY-RUN] Sarebbe rinominato come: {final_remote_path}")
                    self.report.add_duplicate()
                    self.report.add_renamed_duplicate()
                else:
                    self.logger.info(f"[DRY-RUN] File unico, verrebbe trasferito normalmente")
                    self.report.add_transferred(file_size)
                
                # Simula aggiornamento cache
                self.remote_file_hashes[file_hash] = remote_dest_path
                
                # Log nel database in modalità dry-run
                if self.sync_id:
                    self.db.log_transferred_file(
                        self.sync_id, local_file_path, remote_dest_path, 
                        file_hash, file_size, is_duplicate, 'DRY_RUN'
                    )
                
                return True
            
            # MODALITÀ NORMALE - Esecuzione reale
            # Crea directory remote se necessario
            remote_parent = remote_dest_path.parent
            mkdir_cmd = f"mkdir -p '{remote_parent}'"
            self.ssh_client.exec_command(mkdir_cmd)
            
            # Controlla se è un duplicato sui file remoti correnti
            is_duplicate = file_hash in self.remote_file_hashes
            final_remote_path = remote_dest_path
            
            if is_duplicate:
                self.report.add_duplicate()
                existing_file = self.remote_file_hashes[file_hash]
                self.logger.info(f"Duplicato trovato: {local_file_path} -> {existing_file}")
                
                # Genera nome per duplicato
                final_remote_path = self.generate_duplicate_name(remote_dest_path)
                self.report.add_renamed_duplicate()
                self.logger.info(f"File sarà salvato come duplicato: {final_remote_path}")
            
            # Trasferimento via SCP
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(str(local_file_path), str(final_remote_path))
            
            # Aggiorna cache hash
            self.remote_file_hashes[file_hash] = final_remote_path
            
            # Statistiche
            if not is_duplicate:
                self.report.add_transferred(file_size)
            
            # Log nel database - file completato con successo
            if self.sync_id:
                self.db.log_transferred_file(
                    self.sync_id, local_file_path, final_remote_path, 
                    file_hash, file_size, is_duplicate, 'COMPLETED'
                )
            
            self.logger.info(f"Trasferito: {local_file_path} -> {final_remote_path}")
            return True
            
        except KeyboardInterrupt:
            self.logger.warning("Interruzione rilevata durante trasferimento")
            # Log file come interrotto
            if self.sync_id:
                self.db.log_transferred_file(
                    self.sync_id, local_file_path, '', 
                    file_hash if 'file_hash' in locals() else '', 0, False, 'INTERRUPTED'
                )
            raise
            
        except Exception as e:
            self.logger.error(f"Errore trasferimento {local_file_path}: {e}")
            self.report.add_error(f"Trasferimento fallito {local_file_path}: {e}")
            self.report.add_skipped()
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Trasferimento: {e}", local_file_path)
            return False
    
    def check_and_fix_nextcloud_cache(self):
        """Controlla e corregge problemi di cache di Nextcloud"""
        self.logger.info("Controllo configurazione cache Nextcloud...")
        
        try:
            # Verifica se APCu è installato
            check_apcu_cmd = "php -m | grep -i apcu"
            stdin, stdout, stderr = self.ssh_client.exec_command(check_apcu_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                self.logger.warning("APCu non trovato, tentativo installazione...")
                
                # Comandi per installare APCu
                install_commands = [
                    "apt update",
                    "apt install -y php-apcu",
                    "systemctl restart apache2 nginx php*-fpm || true"
                ]
                
                for cmd in install_commands:
                    self.logger.info(f"Eseguendo: {cmd}")
                    stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status != 0:
                        error = stderr.read().decode().strip()
                        self.logger.warning(f"Comando fallito: {cmd} - {error}")
            
            # Configura Nextcloud per usare file cache se APCu non funziona
            config_cmd = """
cd /var/www/nextcloud && sudo -u www-data php occ config:system:set memcache.local --value='\\OC\\Memcache\\ArrayCache' --type=string
"""
            self.logger.info("Configurando cache di fallback...")
            stdin, stdout, stderr = self.ssh_client.exec_command(config_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                self.logger.info("Cache configurata correttamente")
            else:
                error = stderr.read().decode().strip()
                self.logger.warning(f"Errore configurazione cache: {error}")
                
        except Exception as e:
            self.logger.error(f"Errore controllo cache: {e}")

    def execute_post_sync_commands(self):
        """Esegue i comandi post-sincronizzazione sul server Nextcloud"""
        self.logger.info("Esecuzione comandi post-sincronizzazione...")
        
        # Prima controlla e corregge problemi di cache
        self.check_and_fix_nextcloud_cache()
        
        commands = [
            # Permessi file
            f"find '{self.nextcloud_dest_path}' -type f -exec chmod 644 {{}} +",
            # Permessi directory  
            f"find '{self.nextclou
        
        for i, cmd in enumerate(commands, 1):
            try:
                self.logger.info(f"Eseguendo comando {i}/{len(commands)}: {cmd}")
                stdin, stdout, stderr = self.ssh_client.exec_command(cmd)
                
                # Aspetta completamento
                exit_status = stdout.channel.recv_exit_status()
                output = stdout.read().decode()
                error = stderr.read().decode()
                
                if exit_status == 0:
                    self.logger.info(f"Comando {i} completato con successo")
                    if output.strip():
                        self.logger.info(f"Output: {output.strip()}")
                else:
                    self.logger.error(f"Comando {i} fallito (exit code {exit_status})")
                    if error.strip():
                        self.logger.error(f"Errore: {error.strip()}")
                        
            except Exception as e:
                self.logger.error(f"Errore esecuzione comando {i}: {e}")
                if self.sync_id:
                    self.db.log_error(self.sync_id, f"Comando post-sync {i}: {e}")
    
    def sync_files(self):
        """Esegue la sincronizzazione completa"""
        start_time = datetime.now()
        
        if self.dry_run:
            self.logger.info("=== INIZIO DRY-RUN: SIMULAZIONE SINCRONIZZAZIONE ===")
        else:
            self.logger.info("Inizio sincronizzazione file multimediali")
        
        # Controlla se ci sono sincronizzazioni da riprendere (solo se non dry-run)
        resumed = False
        if not self.dry_run:
            resumed = self.check_for_resume()
        
        # Inizia sessione nel database
        self.sync_id = self.db.start_sync_session(
            self.local_source_path, 
            self.nextcloud_dest_path,
            self.resumed_from_id
        )
        
        if resumed:
            self.logger.info(f"Ripresa della sincronizzazione - ID sessione: {self.sync_id}")
        
        try:
            # Connessione SSH (anche in dry-run per verificare connettività)
            if not self.connect_ssh():
                self.db.update_sync_report(self.sync_id, self.report, 0, 'FAILED')
                return False
            
            # Scansiona file esistenti sul server (saltata in dry-run se resuming)
            if not resumed or not self.dry_run:
                self.scan_remote_files()
            else:
                self.logger.info("Ripresa: skipping scansione file remoti (usando cache precedente)")
            
            # Ottiene lista file locali
            local_files = self.get_local_files()
            if not local_files:
                self.logger.warning("Nessun file multimediale trovato localmente")
                self.db.update_sync_report(self.sync_id, self.report, 0, 'NO_FILES')
                return True
            
            self.logger.info(f"File da processare: {len(local_files)}")
            if resumed and not self.dry_run:
                estimated_remaining = len(local_files) - len(self.processed_files)
                self.logger.info(f"Stima file rimanenti: {estimated_remaining}")
            
            if self.dry_run:
                self.logger.info("=== INIZIO SIMULAZIONE TRASFERIMENTI ===")
            
            # Trasferisce ogni file
            try:
                for i, local_file in enumerate(local_files, 1):
                    if self.dry_run:
                        self.logger.info(f"[DRY-RUN] Processando file {i}/{len(local_files)}: {local_file}")
                    else:
                        self.logger.info(f"Processando file {i}/{len(local_files)}: {local_file}")
                    
                    self.transfer_file(local_file)
                    
                    # Salva progresso ogni 10 file (non in dry-run)
                    if i % 10 == 0 and not self.dry_run:
                        self.logger.info(f"Progresso salvato: {i}/{len(local_files)} file processati")
                        
            except KeyboardInterrupt:
                if self.dry_run:
                    self.logger.warning("[DRY-RUN] Simulazione interrotta dall'utente")
                else:
                    self.logger.warning("Sincronizzazione interrotta dall'utente")
                    self.db.update_sync_report(self.sync_id, self.report, 
                                             (datetime.now() - start_time).total_seconds(), 
                                             'INTERRUPTED')
                    print(f"\nSincronizzazione interrotta. Progresso salvato nel database (ID: {self.sync_id})")
                    print("Riavvia lo script per continuare da dove si era fermato.")
                return False
            
            # Comandi post-sincronizzazione
            if self.report.files_transferred > 0 or self.report.duplicates_renamed > 0 or self.dry_run:
                self.execute_post_sync_commands()
            
        except Exception as e:
            self.logger.error(f"Errore generale durante sincronizzazione: {e}")
            self.report.add_error(f"Errore generale: {e}")
            if not self.dry_run:
                self.db.log_error(self.sync_id, f"Errore generale: {e}")
            
        finally:
            if hasattr(self, 'ssh_client'):
                self.ssh_client.close()
        
        # Aggiorna report nel database
        end_time = datetime.now()
        duration = end_time - start_time
        duration_seconds = duration.total_seconds()
        
        status = 'DRY_RUN_COMPLETED' if self.dry_run else ('COMPLETED' if len(self.report.errors) == 0 else 'COMPLETED_WITH_ERRORS')
        self.db.update_sync_report(self.sync_id, self.report, duration_seconds, status)
        
        self.print_report(duration)
        return len(self.report.errors) == 0f"File da processare: {len(local_files)}")
            if resumed:
                estimated_remaining = len(local_files) - len(self.processed_files)
                self.logger.info(f"Stima file rimanenti: {estimated_remaining}")
            
            # Trasferisce ogni file
            try:
                for i, local_file in enumerate(local_files, 1):
                    self.logger.info(f"Processando file {i}/{len(local_files)}: {local_file}")
                    self.transfer_file(local_file)
                    
                    # Salva progresso ogni 10 file
                    if i % 10 == 0:
                        self.logger.info(f"Progresso salvato: {i}/{len(local_files)} file processati")
                        
            except KeyboardInterrupt:
                self.logger.warning("Sincronizzazione interrotta dall'utente")
                self.db.update_sync_report(self.sync_id, self.report, 
                                         (datetime.now() - start_time).total_seconds(), 
                                         'INTERRUPTED')
                print(f"\nSincronizzazione interrotta. Progresso salvato nel database (ID: {self.sync_id})")
                print("Riavvia lo script per continuare da dove si era fermato.")
                return False
            
            # Comandi post-sincronizzazione
            if self.report.files_transferred > 0 or self.report.duplicates_renamed > 0:
                self.execute_post_sync_commands()
            
        except Exception as e:
            self.logger.error(f"Errore generale durante sincronizzazione: {e}")
            self.report.add_error(f"Errore generale: {e}")
            self.db.log_error(self.sync_id, f"Errore generale: {e}")
            
        finally:
            if hasattr(self, 'ssh_client'):
                self.ssh_client.close()
        
        # Aggiorna report nel database
        end_time = datetime.now()
        duration = end_time - start_time
        duration_seconds = duration.total_seconds()
        
        status = 'COMPLETED' if len(self.report.errors) == 0 else 'COMPLETED_WITH_ERRORS'
        self.db.update_sync_report(self.sync_id, self.report, duration_seconds, status)
        
        self.print_report(duration)
        return len(self.report.errors) == 0 self.nextcloud_dest_path)
        
        try:
            # Connessione SSH
            if not self.connect_ssh():
                self.db.update_sync_report(self.sync_id, self.report, 0, 'FAILED')
                return False
            
            # Scansiona file esistenti sul server
            self.scan_remote_files()
            
            # Ottiene lista file locali
            local_files = self.get_local_files()
            if not local_files:
                self.logger.warning("Nessun file multimediale trovato localmente")
                self.db.update_sync_report(self.sync_id, self.report, 0, 'NO_FILES')
                return True
            
            # Trasferisce ogni file
            for i, local_file in enumerate(local_files, 1):
                self.logger.info(f"Processando file {i}/{len(local_files)}: {local_file}")
                self.transfer_file(local_file)
            
            # Comandi post-sincronizzazione
            if self.report.files_transferred > 0 or self.report.duplicates_renamed > 0:
                self.execute_post_sync_commands()
            
        except Exception as e:
            self.logger.error(f"Errore generale durante sincronizzazione: {e}")
            self.report.add_error(f"Errore generale: {e}")
            self.db.log_error(self.sync_id, f"Errore generale: {e}")
            
        finally:
            if hasattr(self, 'ssh_client'):
                self.ssh_client.close()
        
        # Aggiorna report nel database
        end_time = datetime.now()
        duration = end_time - start_time
        duration_seconds = duration.total_seconds()
        
        status = 'COMPLETED' if len(self.report.errors) == 0 else 'COMPLETED_WITH_ERRORS'
        self.db.update_sync_report(self.sync_id, self.report, duration_seconds, status)
        
        self.print_report(duration)
        return len(self.report.errors) == 0
    
    def print_report(self, duration):
        """Stampa il report finale"""
        print("\n" + "="*60)
        if self.dry_run:
            print("REPORT DRY-RUN COMPLETATO")
        else:
            print("REPORT SINCRONIZZAZIONE COMPLETATA")
        print("="*60)
        print(f"Durata: {duration}")
        
        if self.dry_run:
            print(f"File che sarebbero trasferiti: {self.report.files_transferred}")
            print(f"Duplicati che sarebbero trovati: {self.report.duplicates_found}")
            print(f"Duplicati che sarebbero rinominati: {self.report.duplicates_renamed}")
            print(f"File già elaborati (che sarebbero skippati): {self.report.already_processed}")
            print(f"Dimensione totale che sarebbe trasferita: {self.format_size(self.report.total_size_transferred)}")
        else:
            print(f"File trasferiti: {self.report.files_transferred}")
            print(f"Duplicati trovati: {self.report.duplicates_found}")
            print(f"Duplicati rinominati: {self.report.duplicates_renamed}")
            print(f"File già elaborati (skippati): {self.report.already_processed}")
            print(f"File saltati (errori): {self.report.skipped_files}")
            print(f"Dimensione totale trasferita: {self.format_size(self.report.total_size_transferred)}")
        
        print(f"Database sync ID: {self.sync_id}")
        if self.resumed_from_id:
            print(f"Ripresa da sync ID: {self.resumed_from_id}")
        
        if self.report.errors:
            print(f"\nErrori ({len(self.report.errors)}):")
            for error in self.report.errors[-5:]:  # Mostra ultimi 5 errori
                print(f"  - {error}")
            if len(self.report.errors) > 5:
                print(f"  ... e altri {len(self.report.errors) - 5} errori (vedi database)")
        
        if self.dry_run:
            print("\n🔍 MODALITÀ DRY-RUN: Nessun file è stato trasferito realmente.")
            print("   Esegui senza --dry-run per effettuare il trasferimento.")
        
        print("="*60)
    
    def format_size(self, size_bytes):
        """Formatta la dimensione in modo leggibile"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

def show_recent_reports(db_path="nextcloud_sync.db"):
    """Mostra i report recenti dal database"""
    db = DatabaseManager(db_path)
    reports = db.get_recent_reports()
    
    if not reports:
        print("Nessun report trovato nel database")
        return
    
    print("\n" + "="*80)
    print("REPORT SINCRONIZZAZIONI RECENTI")
    print("="*80)
    
    for report in reports:
        sync_id, sync_date, files_transferred, duplicates_found, duplicates_renamed, \
        errors_count, skipped_files, already_processed, total_size_bytes, duration_seconds, \
        source_path, dest_path, status, resumed_from_id = report
        
        print(f"\nID: {sync_id} | Data: {sync_date} | Status: {status}")
        if resumed_from_id:
            print(f"Ripresa da ID: {resumed_from_id}")
        print(f"Percorso: {source_path} -> {dest_path}")
        print(f"File trasferiti: {files_transferred} | Duplicati: {duplicates_found} ({duplicates_renamed} rinominati)")
        print(f"File già processati: {already_processed} | Errori: {errors_count} | Saltati: {skipped_files}")
        
        if total_size_bytes:
            size_str = f"{total_size_bytes/1024/1024:.2f} MB"
            print(f"Dimensione: {size_str} | Durata: {duration_seconds:.1f}s")
    
    print("="*80)

def main():
    parser = argparse.ArgumentParser(description='Sincronizzazione file multimediali da Raspberry Pi a Nextcloud')
    parser.add_argument('--nextcloud-host', required=True, help='IP/hostname server Nextcloud')
    parser.add_argument('--nextcloud-user', default='root', help='Username SSH Nextcloud (default: root)')
    parser.add_argument('--nextcloud-dest', required=True, help='Percorso destinazione su Nextcloud')
    parser.add_argument('--local-source', required=True, help='Percorso sorgente locale sul Raspberry Pi')
    parser.add_argument('--ssh-key', help='Percorso chiave SSH privata')
    parser.add_argument('--extensions', nargs='*', help='Estensioni da sincronizzare (es: .jpg .mp4)')
    parser.add_argument('--db-path', default='nextcloud_sync.db', help='Percorso database SQLite')
    parser.add_argument('--show-reports', action='store_true', help='Mostra report recenti e esci')
    parser.add_argument('--force-new', action='store_true', help='Forza nuova sincronizzazione ignorando quelle incomplete')
    parser.add_argument('--resume', type=int, metavar='SYNC_ID', help='Riprendi sincronizzazione specifica dal database')
    parser.add_argument('--dry-run', action='store_true', help='Modalità dry-run: simula operazioni senza trasferire file')
    
    args = parser.parse_args()
    
    if args.show_reports:
        show_recent_reports(args.db_path)
        return
    
    # Crea il sincronizzatore
    syncer = NextcloudMediaSync(
        nextcloud_host=args.nextcloud_host,
        nextcloud_user=args.nextcloud_user,
        nextcloud_dest_path=args.nextcloud_dest,
        local_source_path=args.local_source,
        ssh_key_path=args.ssh_key,
        extensions=args.extensions,
        db_path=args.db_path,
        dry_run=args.dry_run
    )
    
    if args.dry_run:
        print("🔍 MODALITÀ DRY-RUN ATTIVATA")
        print("   Tutte le operazioni saranno simulate senza trasferimenti reali")
        print("   Verrà testata la connettività e mostrato cosa accadrebbe\n")
    
    # Gestione opzioni di ripresa
    if args.resume:
        syncer.resumed_from_id = args.resume
        syncer.processed_files = syncer.db.get_processed_files([args.resume])
        print(f"Ripresa forzata dalla sincronizzazione ID {args.resume}")
    elif args.force_new:
        print("Nuova sincronizzazione forzata (ignorando quelle incomplete)")
        # Marca eventuali sync incomplete come interrotte
        incomplete_id = syncer.db.find_incomplete_sync(syncer.local_source_path, syncer.nextcloud_dest_path)
        if incomplete_id:
            syncer.db.mark_sync_interrupted(incomplete_id)
            print(f"Sincronizzazione {incomplete_id} marcata come interrotta")
    
    # Avvia sincronizzazione
    success = syncer.sync_files()
    
    if args.dry_run:
        print("\n🔍 DRY-RUN COMPLETATO!")
        print("   Nessun file è stato trasferito. Esegui senza --dry-run per la sincronizzazione reale.")
        exit(0)
    elif success:
        print("\nSincronizzazione completata con successo!")
        exit(0)
    else:
        print("\nSincronizzazione terminata con errori!")
        exit(1)

if __name__ == "__main__":
    main()