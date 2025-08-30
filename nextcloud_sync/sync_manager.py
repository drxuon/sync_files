#!/usr/bin/env python3
"""
Sync Manager - Gestore principale della sincronizzazione Nextcloud
Coordina tutte le operazioni di sincronizzazione
"""

import logging
from datetime import datetime
from pathlib import Path

from database_manager import DatabaseManager
from report_manager import MediaSyncReport, ReportFormatter
from file_utils import FileUtils, DuplicateChecker, FileScanner
from ssh_manager import SSHManager, NextcloudCommands

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
        self.extensions = extensions or FileUtils.MEDIA_EXTENSIONS
        
        # Componenti del sistema
        self.db = DatabaseManager(db_path or "nextcloud_sync.db")
        self.report = MediaSyncReport()
        self.duplicate_checker = DuplicateChecker(self.db)
        self.ssh_manager = SSHManager(nextcloud_host, nextcloud_user, ssh_key_path)
        self.nextcloud_commands = None  # Inizializzato dopo la connessione SSH
        
        # Stato della sincronizzazione
        self.sync_id = None
        self.resumed_from_id = None
        
        # Setup logging
        self._setup_logging()
        
        if self.dry_run:
            logging.info("MODALITÀ DRY-RUN ATTIVA - Nessun file sarà trasferito realmente")
    
    def _setup_logging(self):
        """Configura il sistema di logging"""
        log_level = logging.INFO
        log_format = '%(asctime)s - %(levelname)s - %(message)s'
        
        if self.dry_run:
            log_format = '%(asctime)s - [DRY-RUN] - %(levelname)s - %(message)s'
        
        logging.basicConfig(
            level=log_level,
            format=log_format,
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
                processed_with_hash = self.duplicate_checker.load_processed_files(
                    self.local_source_path, 
                    self.nextcloud_dest_path,
                    exclude_sync_id=incomplete_sync_id
                )
                
                # Includi anche i file della sessione interrotta se completati
                self.duplicate_checker.load_interrupted_files([incomplete_sync_id])
                
                logging.info(f"Ripresa sincronizzazione: {len(self.duplicate_checker.processed_files)} file già elaborati verranno skippati")
                return True
            else:
                # Marca come interrotta definitivamente
                self.db.mark_sync_interrupted(incomplete_sync_id)
                
        return False
    
    def force_resume_from_sync(self, sync_id):
        """Forza la ripresa da una sincronizzazione specifica"""
        self.resumed_from_id = sync_id
        self.duplicate_checker.load_interrupted_files([sync_id])
        logging.info(f"Ripresa forzata dalla sincronizzazione ID {sync_id}")
    
    def get_local_files(self):
        """Ottiene la lista dei file multimediali locali"""
        try:
            return FileUtils.get_local_media_files(self.local_source_path, self.extensions)
        except Exception as e:
            self.report.add_error(f"Recupero file locali fallito: {e}")
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Recupero file locali: {e}")
            return []
    
    def transfer_file(self, local_file_path):
        """Trasferisce un singolo file al server Nextcloud"""
        try:
            # Controllo se file già elaborato
            if self.duplicate_checker.is_file_already_processed(local_file_path):
                self.report.add_already_processed()
                logging.info(f"File già elaborato, skipping: {local_file_path}")
                return True
            
            # Calcola hash del file locale
            file_hash = FileUtils.calculate_file_hash(local_file_path)
            if not file_hash:
                self.report.add_error(f"Impossibile calcolare hash per {local_file_path}")
                if self.sync_id:
                    self.db.log_error(self.sync_id, f"Calcolo hash fallito", local_file_path)
                return False
            
            # Controllo più accurato con hash
            if self.duplicate_checker.is_file_already_processed(local_file_path, file_hash):
                self.report.add_already_processed()
                logging.info(f"File già elaborato (hash match), skipping: {local_file_path}")
                return True
            
            # Calcola percorso di destinazione
            relative_path = FileUtils.get_relative_path(local_file_path, self.local_source_path)
            remote_dest_path = self.nextcloud_dest_path / relative_path
            file_size = local_file_path.stat().st_size
            
            if self.dry_run:
                return self._simulate_transfer(local_file_path, remote_dest_path, file_hash, file_size)
            else:
                return self._execute_transfer(local_file_path, remote_dest_path, file_hash, file_size)
                
        except KeyboardInterrupt:
            logging.warning("Interruzione rilevata durante trasferimento")
            if self.sync_id:
                self.db.log_transferred_file(
                    self.sync_id, local_file_path, '', 
                    file_hash if 'file_hash' in locals() else '', 0, False, 'INTERRUPTED'
                )
            raise
            
        except Exception as e:
            logging.error(f"Errore trasferimento {local_file_path}: {e}")
            self.report.add_error(f"Trasferimento fallito {local_file_path}: {e}")
            self.report.add_skipped()
            if self.sync_id:
                self.db.log_error(self.sync_id, f"Trasferimento: {e}", local_file_path)
            return False
    
    def _simulate_transfer(self, local_file_path, remote_dest_path, file_hash, file_size):
        """Simula il trasferimento di un file (modalità dry-run)"""
        logging.info(f"[DRY-RUN] TRASFERIMENTO SIMULATO: {local_file_path}")
        logging.info(f"[DRY-RUN] Destinazione: {remote_dest_path}")
        logging.info(f"[DRY-RUN] Dimensione: {ReportFormatter.format_size(file_size)}")
        logging.info(f"[DRY-RUN] Hash MD5: {file_hash}")
        
        # Simula controllo duplicati
        is_duplicate = self.duplicate_checker.is_duplicate_in_remote(file_hash)
        if is_duplicate:
            existing_file = self.duplicate_checker.get_existing_duplicate_path(file_hash)
            logging.info(f"[DRY-RUN] DUPLICATO RILEVATO: esiste già come {existing_file}")
            final_remote_path = FileUtils.generate_duplicate_name(None, remote_dest_path, dry_run=True)
            logging.info(f"[DRY-RUN] Sarebbe rinominato come: {final_remote_path}")
            self.report.add_duplicate()
            self.report.add_renamed_duplicate()
        else:
            logging.info(f"[DRY-RUN] File unico, verrebbe trasferito normalmente")
            self.report.add_transferred(file_size)
        
        # Simula aggiornamento cache
        self.duplicate_checker.add_remote_file_hash(file_hash, str(remote_dest_path))
        
        # Log nel database in modalità dry-run
        if self.sync_id:
            self.db.log_transferred_file(
                self.sync_id, local_file_path, remote_dest_path, 
                file_hash, file_size, is_duplicate, 'DRY_RUN'
            )
        
        return True
    
    def _execute_transfer(self, local_file_path, remote_dest_path, file_hash, file_size):
        """Esegue il trasferimento reale di un file"""
        # Crea directory remota se necessario
        remote_parent = remote_dest_path.parent
        if not FileUtils.ensure_remote_directory(self.ssh_manager, remote_parent):
            self.report.add_error(f"Impossibile creare directory {remote_parent}")
            return False
        
        # Controlla se è un duplicato sui file remoti correnti
        is_duplicate = self.duplicate_checker.is_duplicate_in_remote(file_hash)
        final_remote_path = remote_dest_path
        
        if is_duplicate:
            self.report.add_duplicate()
            existing_file = self.duplicate_checker.get_existing_duplicate_path(file_hash)
            logging.info(f"Duplicato trovato: {local_file_path} -> {existing_file}")
            
            # Genera nome per duplicato
            final_remote_path = FileUtils.generate_duplicate_name(
                self.ssh_manager.get_client(), remote_dest_path
            )
            self.report.add_renamed_duplicate()
            logging.info(f"File sarà salvato come duplicato: {final_remote_path}")
        
        # Trasferimento via SCP
        if not self.ssh_manager.transfer_file(local_file_path, final_remote_path):
            self.report.add_error(f"Trasferimento SCP fallito per {local_file_path}")
            return False
        
        # Aggiorna cache hash
        self.duplicate_checker.add_remote_file_hash(file_hash, str(final_remote_path))
        
        # Statistiche
        if not is_duplicate:
            self.report.add_transferred(file_size)
        
        # Log nel database - file completato con successo
        if self.sync_id:
            self.db.log_transferred_file(
                self.sync_id, local_file_path, final_remote_path, 
                file_hash, file_size, is_duplicate, 'COMPLETED'
            )
        
        logging.info(f"Trasferito: {local_file_path} -> {final_remote_path}")
        return True
    
    def sync_files(self):
        """Esegue la sincronizzazione completa"""
        start_time = datetime.now()
        
        if self.dry_run:
            logging.info("=== INIZIO DRY-RUN: SIMULAZIONE SINCRONIZZAZIONE ===")
        else:
            logging.info("Inizio sincronizzazione file multimediali")
        
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
            logging.info(f"Ripresa della sincronizzazione - ID sessione: {self.sync_id}")
        
        try:
            # Connessione SSH (anche in dry-run per verificare connettività)
            if not self.ssh_manager.connect():
                self.db.update_sync_report(self.sync_id, self.report, 0, 'FAILED')
                return False
            
            # Inizializza i comandi Nextcloud
            self.nextcloud_commands = NextcloudCommands(self.ssh_manager)
            
            # Scansiona file esistenti sul server (saltata se resuming e non dry-run)
            if not resumed or self.dry_run:
                FileScanner.scan_remote_files(
                    self.ssh_manager.get_client(),
                    self.nextcloud_dest_path,
                    self.extensions,
                    self.duplicate_checker,
                    self.dry_run
                )
            else:
                logging.info("Ripresa: skipping scansione file remoti (usando cache precedente)")
            
            # Ottiene lista file locali
            local_files = self.get_local_files()
            if not local_files:
                logging.warning("Nessun file multimediale trovato localmente")
                self.db.update_sync_report(self.sync_id, self.report, 0, 'NO_FILES')
                return True
            
            logging.info(f"File da processare: {len(local_files)}")
            if resumed and not self.dry_run:
                estimated_remaining = len(local_files) - len(self.duplicate_checker.processed_files)
                logging.info(f"Stima file rimanenti: {estimated_remaining}")
            
            if self.dry_run:
                logging.info("=== INIZIO SIMULAZIONE TRASFERIMENTI ===")
            
            # Trasferisce ogni file
            try:
                for i, local_file in enumerate(local_files, 1):
                    if self.dry_run:
                        logging.info(f"[DRY-RUN] Processando file {i}/{len(local_files)}: {local_file}")
                    else:
                        logging.info(f"Processando file {i}/{len(local_files)}: {local_file}")
                    
                    self.transfer_file(local_file)
                    
                    # Salva progresso ogni 10 file (non in dry-run)
                    if i % 10 == 0 and not self.dry_run:
                        logging.info(f"Progresso salvato: {i}/{len(local_files)} file processati")
                        
            except KeyboardInterrupt:
                if self.dry_run:
                    logging.warning("[DRY-RUN] Simulazione interrotta dall'utente")
                else:
                    logging.warning("Sincronizzazione interrotta dall'utente")
                    self.db.update_sync_report(self.sync_id, self.report, 
                                             (datetime.now() - start_time).total_seconds(), 
                                             'INTERRUPTED')
                    print(f"\nSincronizzazione interrotta. Progresso salvato nel database (ID: {self.sync_id})")
                    print("Riavvia lo script per continuare da dove si era fermato.")
                return False
            
            # Comandi post-sincronizzazione
            if self.report.files_transferred > 0 or self.report.duplicates_renamed > 0 or self.dry_run:
                self.nextcloud_commands.execute_post_sync_commands(self.nextcloud_dest_path, self.dry_run)
            
        except Exception as e:
            logging.error(f"Errore generale durante sincronizzazione: {e}")
            self.report.add_error(f"Errore generale: {e}")
            if not self.dry_run:
                self.db.log_error(self.sync_id, f"Errore generale: {e}")
            
        finally:
            self.ssh_manager.disconnect()
        
        # Aggiorna report nel database
        end_time = datetime.now()
        duration = end_time - start_time
        duration_seconds = duration.total_seconds()
        
        status = 'DRY_RUN_COMPLETED' if self.dry_run else ('COMPLETED' if len(self.report.errors) == 0 else 'COMPLETED_WITH_ERRORS')
        self.db.update_sync_report(self.sync_id, self.report, duration_seconds, status)
        
        # Stampa report finale
        ReportFormatter.print_sync_report(
            self.report, 
            duration, 
            self.sync_id, 
            self.resumed_from_id, 
            self.dry_run
        )
        
        return len(self.report.errors) == 0