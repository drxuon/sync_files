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
                    files_transferred INTEGER,
                    duplicates_found INTEGER,
                    duplicates_renamed INTEGER,
                    errors_count INTEGER,
                    skipped_files INTEGER,
                    total_size_bytes INTEGER,
                    duration_seconds REAL,
                    source_path TEXT,
                    dest_path TEXT,
                    status TEXT
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
    
    def start_sync_session(self, source_path, dest_path):
        """Inizia una nuova sessione di sincronizzazione"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sync_reports (source_path, dest_path, status)
                VALUES (?, ?, 'RUNNING')
            ''', (str(source_path), str(dest_path)))
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
                report.total_size_transferred,
                duration_seconds,
                status,
                sync_id
            ))
    
    def log_transferred_file(self, sync_id, source_file, dest_file, file_hash, file_size, is_duplicate=False):
        """Registra un file trasferito"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transferred_files 
                (sync_id, source_file, dest_file, file_hash, file_size, is_duplicate)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (sync_id, str(source_file), str(dest_file), file_hash, file_size, is_duplicate))
    
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

class MediaSyncReport:
    def __init__(self):
        self.files_transferred = 0
        self.duplicates_found = 0
        self.duplicates_renamed = 0
        self.errors = []
        self.skipped_files = 0
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

class NextcloudMediaSync:
    def __init__(self, nextcloud_host, nextcloud_user, nextcloud_dest_path, 
                 local_source_path, ssh_key_path=None, extensions=None, db_path=None):
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
        """
        self.nextcloud_host = nextcloud_host
        self.nextcloud_user = nextcloud_user
        self.nextcloud_dest_path = Path(nextcloud_dest_path)
        self.local_source_path = Path(local_source_path)
        self.ssh_key_path = ssh_key_path
        
        # Estensioni multimediali supportate
        self.extensions = extensions or [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Immagini
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',    # Video
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'            # Audio
        ]
        
        self.report = MediaSyncReport()
        self.remote_file_hashes = {}  # Cache degli hash dei file remoti
        
        # Database manager
        self.db = DatabaseManager(db_path or "nextcloud_sync.db")
        self.sync_id = None
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('nextcloud_sync.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
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
            # Calcola il percorso di destinazione mantenendo la struttura
            try:
                relative_path = local_file_path.relative_to(self.local_source_path)
            except ValueError:
                relative_path = local_file_path.name
            
            remote_dest_path = self.nextcloud_dest_path / relative_path
            
            # Crea directory remote se necessario
            remote_parent = remote_dest_path.parent
            mkdir_cmd = f"mkdir -p '{remote_parent}'"
            self.ssh_client.exec_command(mkdir_cmd)
            
            # Calcola hash del file locale
            file_hash = self.calculate_file_hash(local_file_path)
            if not file_hash:
                self.report.add_error(f"Impossibile calcolare hash per {local_file_path}")
                if self.sync_id:
                    self.db.log_error(self.sync_id, f"Calcolo hash fallito", local_file_path)
                return False
            
            # Controlla se è un duplicato
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
            file_size = local_file_path.stat().st_size
            if not is_duplicate:
                self.report.add_transferred(file_size)
            
            # Log nel database
            if self.sync_id:
                self.db.log_transferred_file(
                    self.sync_id, local_file_path, final_remote_path, 
                    file_hash, file_size, is_duplicate
                )
            
            self.logger.info(f"Trasferito: {local_file_path} -> {final_remote_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore trasferimento {local_file_path}: {e}")
            self.report.add_error(f"Trasferimento fallito {local_file_path}: {e}")
            self.report.add_skipped()
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Trasferimento: {e}", local_file_path)
            return False
    
    def execute_post_sync_commands(self):
        """Esegue i comandi post-sincronizzazione sul server Nextcloud"""
        self.logger.info("Esecuzione comandi post-sincronizzazione...")
        
        commands = [
            # Permessi file
            f"find '{self.nextcloud_dest_path}' -type f -exec chmod 644 {{}} +",
            # Permessi directory  
            f"find '{self.nextcloud_dest_path}' -type d -exec chmod 755 {{}} +",
            # Cambio proprietà a www-data
            f"chown -R www-data:www-data '{self.nextcloud_dest_path}'",
            # Scan Nextcloud
            'su -c "php /var/www/nextcloud/occ files:scan --all" www-data -s /bin/bash'
        ]
        
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
        self.logger.info("Inizio sincronizzazione file multimediali")
        
        # Inizia sessione nel database
        self.sync_id = self.db.start_sync_session(self.local_source_path, self.nextcloud_dest_path)
        
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
        print("REPORT SINCRONIZZAZIONE COMPLETATA")
        print("="*60)
        print(f"Durata: {duration}")
        print(f"File trasferiti: {self.report.files_transferred}")
        print(f"Duplicati trovati: {self.report.duplicates_found}")
        print(f"Duplicati rinominati: {self.report.duplicates_renamed}")
        print(f"File saltati (errori): {self.report.skipped_files}")
        print(f"Dimensione totale trasferita: {self.format_size(self.report.total_size_transferred)}")
        print(f"Database sync ID: {self.sync_id}")
        
        if self.report.errors:
            print(f"\nErrori ({len(self.report.errors)}):")
            for error in self.report.errors[-5:]:  # Mostra ultimi 5 errori
                print(f"  - {error}")
            if len(self.report.errors) > 5:
                print(f"  ... e altri {len(self.report.errors) - 5} errori (vedi database)")
        
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
        errors_count, skipped_files, total_size_bytes, duration_seconds, source_path, \
        dest_path, status = report
        
        print(f"\nID: {sync_id} | Data: {sync_date} | Status: {status}")
        print(f"Percorso: {source_path} -> {dest_path}")
        print(f"File trasferiti: {files_transferred} | Duplicati: {duplicates_found} ({duplicates_renamed} rinominati)")
        print(f"Errori: {errors_count} | Saltati: {skipped_files}")
        
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
        db_path=args.db_path
    )
    
    # Avvia sincronizzazione
    success = syncer.sync_files()
    
    if success:
        print("\nSincronizzazione completata con successo!")
        exit(0)
    else:
        print("\nSincronizzazione terminata con errori!")
        exit(1)

if __name__ == "__main__":
    main()