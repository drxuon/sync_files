#!/usr/bin/env python3
"""
Script per sincronizzazione file multimediali da Raspberry Pi a Nextcloud
con gestione duplicati e report dettagliato
"""

import os
import hashlib
import shutil
import logging
from pathlib import Path
from collections import defaultdict
import argparse
from datetime import datetime
import paramiko
from scp import SCPClient
import mimetypes

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
    def __init__(self, source_host, source_user, source_path, 
                 dest_path, ssh_key_path=None, extensions=None):
        """
        Inizializza il sincronizzatore
        
        Args:
            source_host: IP/hostname del Raspberry Pi
            source_user: username SSH per il Raspberry Pi
            source_path: percorso base dei file sul Raspberry Pi
            dest_path: percorso di destinazione su Nextcloud
            ssh_key_path: percorso della chiave SSH (opzionale)
            extensions: lista delle estensioni da sincronizzare
        """
        self.source_host = source_host
        self.source_user = source_user
        self.source_path = Path(source_path)
        self.dest_path = Path(dest_path)
        self.ssh_key_path = ssh_key_path
        
        # Estensioni multimediali supportate
        self.extensions = extensions or [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Immagini
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',    # Video
            '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'            # Audio
        ]
        
        self.report = MediaSyncReport()
        self.file_hashes = {}  # Cache degli hash per rilevare duplicati
        
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
        """Calcola l'hash MD5 di un file"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"Errore nel calcolo hash per {file_path}: {e}")
            return None
    
    def is_media_file(self, file_path):
        """Verifica se il file è multimediale"""
        return any(str(file_path).lower().endswith(ext) for ext in self.extensions)
    
    def generate_duplicate_name(self, file_path):
        """Genera un nome per file duplicato aggiungendo _DUP prima dell'estensione"""
        path_obj = Path(file_path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_DUP{counter if counter > 1 else ''}{suffix}"
            new_path = parent / new_name
            if not new_path.exists():
                return new_path
            counter += 1
    
    def scan_existing_files(self):
        """Scansiona i file esistenti nella destinazione e calcola i loro hash"""
        self.logger.info("Scansione file esistenti nella destinazione...")
        
        if not self.dest_path.exists():
            self.dest_path.mkdir(parents=True, exist_ok=True)
            return
            
        for file_path in self.dest_path.rglob('*'):
            if file_path.is_file() and self.is_media_file(file_path):
                file_hash = self.calculate_file_hash(file_path)
                if file_hash:
                    self.file_hashes[file_hash] = file_path
                    
        self.logger.info(f"Trovati {len(self.file_hashes)} file esistenti")
    
    def connect_ssh(self):
        """Stabilisce connessione SSH al Raspberry Pi"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.ssh_key_path:
                self.ssh_client.connect(
                    self.source_host, 
                    username=self.source_user, 
                    key_filename=self.ssh_key_path
                )
            else:
                # Richiede password se non specificata chiave SSH
                password = input(f"Password per {self.source_user}@{self.source_host}: ")
                self.ssh_client.connect(
                    self.source_host, 
                    username=self.source_user, 
                    password=password
                )
                
            self.logger.info(f"Connessione SSH stabilita con {self.source_host}")
            return True
            
        except Exception as e:
            self.logger.error(f"Errore connessione SSH: {e}")
            self.report.add_error(f"Connessione SSH fallita: {e}")
            return False
    
    def get_remote_files(self):
        """Ottiene la lista dei file multimediali dal Raspberry Pi"""
        try:
            # Comando per trovare tutti i file multimediali organizzati per anno/mese
            extensions_pattern = " -o ".join([f"-name '*.{ext[1:]}'" for ext in self.extensions])
            find_cmd = f"find {self.source_path} -type f \\( {extensions_pattern} \\)"
            
            stdin, stdout, stderr = self.ssh_client.exec_command(find_cmd)
            file_list = stdout.read().decode().strip().split('\n')
            
            if stderr.read():
                self.logger.warning(f"Warning durante la ricerca: {stderr.read().decode()}")
            
            # Filtra file vuoti dalla lista
            remote_files = [f for f in file_list if f.strip()]
            self.logger.info(f"Trovati {len(remote_files)} file multimediali sul Raspberry Pi")
            
            return remote_files
            
        except Exception as e:
            self.logger.error(f"Errore nel recupero file remoti: {e}")
            self.report.add_error(f"Recupero file remoti fallito: {e}")
            return []
    
    def transfer_file(self, remote_file_path):
        """Trasferisce un singolo file dal Raspberry Pi"""
        try:
            remote_path = Path(remote_file_path)
            
            # Mantiene la struttura delle directory (anno/mese)
            # Estrae la parte relativa del percorso rispetto al source_path
            try:
                relative_path = remote_path.relative_to(self.source_path)
            except ValueError:
                # Se il file non è sotto source_path, usa solo il nome del file
                relative_path = remote_path.name
            
            local_dest_path = self.dest_path / relative_path
            local_dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Trasferimento temporaneo
            temp_file = local_dest_path.with_suffix(local_dest_path.suffix + '.tmp')
            
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.get(str(remote_file_path), str(temp_file))
            
            # Calcola hash del file trasferito
            file_hash = self.calculate_file_hash(temp_file)
            if not file_hash:
                temp_file.unlink()
                self.report.add_error(f"Impossibile calcolare hash per {remote_file_path}")
                return False
            
            # Controlla se è un duplicato
            if file_hash in self.file_hashes:
                self.report.add_duplicate()
                existing_file = self.file_hashes[file_hash]
                self.logger.info(f"Duplicato trovato: {remote_file_path} -> {existing_file}")
                
                # Rinomina come duplicato
                duplicate_path = self.generate_duplicate_name(local_dest_path)
                temp_file.rename(duplicate_path)
                self.report.add_renamed_duplicate()
                self.logger.info(f"File rinominato come duplicato: {duplicate_path}")
                
            else:
                # File unico, sposta dalla posizione temporanea
                temp_file.rename(local_dest_path)
                self.file_hashes[file_hash] = local_dest_path
                file_size = local_dest_path.stat().st_size
                self.report.add_transferred(file_size)
                self.logger.info(f"Trasferito: {remote_file_path} -> {local_dest_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Errore trasferimento {remote_file_path}: {e}")
            self.report.add_error(f"Trasferimento fallito {remote_file_path}: {e}")
            if 'temp_file' in locals() and temp_file.exists():
                temp_file.unlink()
            return False
    
    def sync_files(self):
        """Esegue la sincronizzazione completa"""
        start_time = datetime.now()
        self.logger.info("Inizio sincronizzazione file multimediali")
        
        # Scansiona file esistenti
        self.scan_existing_files()
        
        # Connessione SSH
        if not self.connect_ssh():
            return False
        
        try:
            # Ottiene lista file remoti
            remote_files = self.get_remote_files()
            if not remote_files:
                self.logger.warning("Nessun file multimediale trovato sul Raspberry Pi")
                return True
            
            # Trasferisce ogni file
            for i, remote_file in enumerate(remote_files, 1):
                self.logger.info(f"Processando file {i}/{len(remote_files)}: {remote_file}")
                
                if not self.transfer_file(remote_file):
                    self.report.add_skipped()
                    
        finally:
            self.ssh_client.close()
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        self.print_report(duration)
        return True
    
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
        
        if self.report.errors:
            print(f"\nErrori ({len(self.report.errors)}):")
            for error in self.report.errors[-10:]:  # Mostra ultimi 10 errori
                print(f"  - {error}")
            if len(self.report.errors) > 10:
                print(f"  ... e altri {len(self.report.errors) - 10} errori")
        
        print("="*60)
    
    def format_size(self, size_bytes):
        """Formatta la dimensione in modo leggibile"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


def main():
    parser = argparse.ArgumentParser(description='Sincronizzazione file multimediali Nextcloud')
    parser.add_argument('--source-host', required=True, help='IP/hostname Raspberry Pi')
    parser.add_argument('--source-user', required=True, help='Username SSH Raspberry Pi')
    parser.add_argument('--source-path', required=True, help='Percorso base file sul Raspberry Pi')
    parser.add_argument('--dest-path', required=True, help='Percorso destinazione Nextcloud')
    parser.add_argument('--ssh-key', help='Percorso chiave SSH privata')
    parser.add_argument('--extensions', nargs='*', help='Estensioni da sincronizzare (es: .jpg .mp4)')
    
    args = parser.parse_args()
    
    # Crea il sincronizzatore
    syncer = NextcloudMediaSync(
        source_host=args.source_host,
        source_user=args.source_user,
        source_path=args.source_path,
        dest_path=args.dest_path,
        ssh_key_path=args.ssh_key,
        extensions=args.extensions
    )
    
    # Avvia sincronizzazione
    success = syncer.sync_files()
    
    if success:
        print("Sincronizzazione completata con successo!")
        exit(0)
    else:
        print("Sincronizzazione terminata con errori!")
        exit(1)


if __name__ == "__main__":
    main()