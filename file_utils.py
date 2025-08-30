#!/usr/bin/env python3
"""
File Utilities per la sincronizzazione Nextcloud
Gestisce operazioni sui file, calcolo hash e controlli
"""

import hashlib
import logging
from pathlib import Path

class FileUtils:
    
    # Estensioni multimediali supportate
    MEDIA_EXTENSIONS = [
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp',  # Immagini
        '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm',    # Video
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'            # Audio
    ]
    
    @staticmethod
    def calculate_file_hash(file_path, chunk_size=8192):
        """Calcola l'hash MD5 di un file locale"""
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            logging.error(f"Errore nel calcolo hash per {file_path}: {e}")
            return None
    
    @staticmethod
    def calculate_remote_file_hash(ssh_client, remote_path):
        """Calcola l'hash MD5 di un file remoto via SSH"""
        try:
            cmd = f"md5sum '{remote_path}' | cut -d' ' -f1"
            stdin, stdout, stderr = ssh_client.exec_command(cmd)
            hash_result = stdout.read().decode().strip()
            error = stderr.read().decode().strip()
            
            if error:
                logging.warning(f"Warning calcolo hash remoto {remote_path}: {error}")
                return None
                
            return hash_result if hash_result else None
            
        except Exception as e:
            logging.error(f"Errore calcolo hash remoto {remote_path}: {e}")
            return None
    
    @staticmethod
    def is_media_file(file_path, extensions=None):
        """Verifica se il file è multimediale"""
        if extensions is None:
            extensions = FileUtils.MEDIA_EXTENSIONS
        return any(str(file_path).lower().endswith(ext) for ext in extensions)
    
    @staticmethod
    def generate_duplicate_name(ssh_client, remote_path, dry_run=False):
        """Genera un nome per file duplicato aggiungendo _DUP prima dell'estensione"""
        path_obj = Path(remote_path)
        stem = path_obj.stem
        suffix = path_obj.suffix
        parent = path_obj.parent
        
        counter = 1
        while True:
            new_name = f"{stem}_DUP{counter if counter > 1 else ''}{suffix}"
            new_path = parent / new_name
            
            if dry_run:
                # In dry-run, simula che il file non esiste
                return new_path
            
            # Verifica se esiste sul server remoto
            check_cmd = f"test -f '{new_path}' && echo 'exists' || echo 'not_exists'"
            stdin, stdout, stderr = ssh_client.exec_command(check_cmd)
            result = stdout.read().decode().strip()
            
            if result == 'not_exists':
                return new_path
            counter += 1
    
    @staticmethod
    def get_local_media_files(source_path, extensions=None):
        """Ottiene la lista di tutti i file multimediali locali"""
        if extensions is None:
            extensions = FileUtils.MEDIA_EXTENSIONS
            
        try:
            source_path = Path(source_path)
            local_files = []
            
            for file_path in source_path.rglob('*'):
                if file_path.is_file() and FileUtils.is_media_file(file_path, extensions):
                    local_files.append(file_path)
            
            logging.info(f"Trovati {len(local_files)} file multimediali locali")
            return local_files
            
        except Exception as e:
            logging.error(f"Errore nel recupero file locali: {e}")
            return []
    
    @staticmethod
    def get_relative_path(file_path, base_path):
        """Ottiene il percorso relativo di un file rispetto a un percorso base"""
        try:
            return Path(file_path).relative_to(Path(base_path))
        except ValueError:
            # Se il file non è sotto base_path, usa solo il nome del file
            return Path(file_path).name
    
    @staticmethod
    def ensure_remote_directory(ssh_client, remote_path, dry_run=False):
        """Assicura che una directory remota esista"""
        if dry_run:
            logging.info(f"[DRY-RUN] Creazione directory: {remote_path}")
            return True
        
        try:
            mkdir_cmd = f"mkdir -p '{remote_path}'"
            stdin, stdout, stderr = ssh_client.exec_command(mkdir_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status != 0:
                error = stderr.read().decode().strip()
                logging.error(f"Errore creazione directory {remote_path}: {error}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Errore creazione directory {remote_path}: {e}")
            return False

class DuplicateChecker:
    """Classe per gestire il controllo dei duplicati"""
    
    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.processed_files = set()
        self.remote_file_hashes = {}
    
    def load_processed_files(self, source_path, dest_path, exclude_sync_id=None):
        """Carica i file già elaborati dalle sincronizzazioni precedenti"""
        processed_with_hash = self.db_manager.get_all_previous_processed_files(
            source_path, dest_path, exclude_sync_id
        )
        
        # Estrae solo i percorsi
        self.processed_files = set(processed_with_hash.keys())
        
        logging.info(f"Caricati {len(self.processed_files)} file già elaborati")
        return processed_with_hash
    
    def load_interrupted_files(self, sync_ids):
        """Carica i file da sincronizzazioni interrotte"""
        interrupted_files = self.db_manager.get_processed_files(sync_ids)
        self.processed_files.update(interrupted_files)
        
        logging.info(f"Caricati {len(interrupted_files)} file da sync interrotte")
    
    def is_file_already_processed(self, file_path, file_hash=None):
        """Verifica se un file è già stato elaborato in precedenza"""
        file_path_str = str(file_path)
        
        # Controllo veloce per percorso
        if file_path_str in self.processed_files:
            return True
        
        # Se abbiamo l'hash, controlliamo anche quello
        if file_hash:
            for processed_hash in self.remote_file_hashes.values():
                if processed_hash == file_hash:
                    return True
        
        return False
    
    def is_duplicate_in_remote(self, file_hash):
        """Verifica se un file è un duplicato sui file remoti attuali"""
        return file_hash in self.remote_file_hashes
    
    def add_remote_file_hash(self, file_hash, file_path):
        """Aggiunge un hash di file remoto alla cache"""
        self.remote_file_hashes[file_hash] = file_path
    
    def get_existing_duplicate_path(self, file_hash):
        """Ottiene il percorso del file duplicato esistente"""
        return self.remote_file_hashes.get(file_hash)

class FileScanner:
    """Classe per scansionare file remoti"""
    
    @staticmethod
    def scan_remote_files(ssh_client, remote_path, extensions, duplicate_checker, dry_run=False):
        """Scansiona i file esistenti sul server remoto e calcola i loro hash"""
        logging.info("Scansione file esistenti sul server remoto...")
        
        if dry_run:
            logging.info("[DRY-RUN] Simulando scansione file remoti...")
            return
        
        try:
            # Crea la directory di destinazione se non esiste
            FileUtils.ensure_remote_directory(ssh_client, remote_path)
            
            # Trova tutti i file multimediali esistenti
            extensions_pattern = " -o ".join([f"-name '*.{ext[1:]}'" for ext in extensions])
            find_cmd = f"find '{remote_path}' -type f \\( {extensions_pattern} \\)"
            
            stdin, stdout, stderr = ssh_client.exec_command(find_cmd)
            existing_files = stdout.read().decode().strip().split('\n')
            existing_files = [f for f in existing_files if f.strip()]
            
            logging.info(f"Trovati {len(existing_files)} file esistenti sul server")
            
            # Calcola hash per ogni file esistente
            for i, file_path in enumerate(existing_files, 1):
                if i % 50 == 0:  # Log progresso ogni 50 file
                    logging.info(f"Calcolando hash: {i}/{len(existing_files)}")
                    
                file_hash = FileUtils.calculate_remote_file_hash(ssh_client, file_path)
                if file_hash:
                    duplicate_checker.add_remote_file_hash(file_hash, file_path)
                    
        except Exception as e:
            logging.error(f"Errore scansione file remoti: {e}")
            raise