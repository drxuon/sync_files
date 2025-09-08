#!/usr/bin/env python3
"""
SSH Manager per la sincronizzazione Nextcloud
Gestisce le connessioni SSH e i comandi remoti
"""

import logging
import getpass
import paramiko
from scp import SCPClient

class SSHManager:
    def __init__(self, host, user, ssh_key_path=None):
        self.host = host
        self.user = user
        self.ssh_key_path = ssh_key_path
        self.ssh_client = None
    
    def connect(self):
        """Stabilisce connessione SSH al server"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            if self.ssh_key_path:
                self.ssh_client.connect(
                    self.host, 
                    username=self.user, 
                    key_filename=self.ssh_key_path
                )
            else:
                password = getpass.getpass(f"Password per {self.user}@{self.host}: ")
                self.ssh_client.connect(
                    self.host, 
                    username=self.user, 
                    password=password
                )
                
            logging.info(f"Connessione SSH stabilita con {self.host}")
            return True
            
        except Exception as e:
            logging.error(f"Errore connessione SSH: {e}")
            return False
    
    def disconnect(self):
        """Chiude la connessione SSH"""
        if self.ssh_client:
            self.ssh_client.close()
            self.ssh_client = None
            logging.info("Connessione SSH chiusa")
    
    def execute_command(self, command, timeout=300):
        """Esegue un comando SSH e ritorna il risultato"""
        if not self.ssh_client:
            raise Exception("Connessione SSH non attiva")
        
        try:
            stdin, stdout, stderr = self.ssh_client.exec_command(command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            return {
                'exit_status': exit_status,
                'output': output.strip(),
                'error': error.strip()
            }
            
        except Exception as e:
            logging.error(f"Errore esecuzione comando '{command}': {e}")
            raise
    
    def transfer_file(self, local_path, remote_path):
        """Trasferisce un file via SCP"""
        if not self.ssh_client:
            raise Exception("Connessione SSH non attiva")
        
        try:
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(str(local_path), str(remote_path))
            return True
            
        except Exception as e:
            logging.error(f"Errore trasferimento file {local_path} -> {remote_path}: {e}")
            raise
    
    def file_exists(self, remote_path):
        """Verifica se un file esiste sul server remoto"""
        try:
            result = self.execute_command(f"test -f '{remote_path}' && echo 'exists' || echo 'not_exists'")
            return result['output'] == 'exists'
        except Exception:
            return False
    
    def execute_as_www_data(self, command, timeout=300):
        """Esegue un comando come utente www-data usando su via root"""
        if not self.ssh_client:
            raise Exception("Connessione SSH non attiva")
        
        # Se siamo già root, usiamo direttamente su
        if self.user == 'root':
            su_command = f"su -c '{command}' www-data"
        else:
            # Se non siamo root, dobbiamo prima diventare root, poi www-data
            # Prova prima con sudo
            su_command = f"sudo su -c '{command}' www-data"
        
        try:
            _, stdout, stderr = self.ssh_client.exec_command(su_command, timeout=timeout)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode()
            error = stderr.read().decode()
            
            # Se sudo fallisce e non siamo root, proviamo con su root
            if exit_status != 0 and self.user != 'root' and 'sudo' in error:
                logging.debug("Sudo fallito, tentativo con su root...")
                # Questo richiederà la password root interattivamente
                su_command = f"su -c 'su -c \"{command}\" www-data' root"
                _, stdout, stderr = self.ssh_client.exec_command(su_command, timeout=timeout)
                exit_status = stdout.channel.recv_exit_status()
                output = stdout.read().decode()
                error = stderr.read().decode()
            
            return {
                'exit_status': exit_status,
                'output': output.strip(),
                'error': error.strip()
            }
            
        except Exception as e:
            logging.error(f"Errore esecuzione comando come www-data '{command}': {e}")
            raise

    def transfer_file_as_www_data(self, local_path, remote_path):
        """Trasferisce un file e gestisce proprietario www-data"""
        if not self.ssh_client:
            raise Exception("Connessione SSH non attiva")
        
        try:
            # Prima crea la directory di destinazione normalmente
            remote_dir = str(remote_path).rsplit('/', 1)[0]
            mkdir_result = self.execute_command(f"mkdir -p '{remote_dir}'")
            if mkdir_result['exit_status'] != 0:
                logging.warning(f"Impossibile creare directory {remote_dir}: {mkdir_result['error']}")
            
            # Trasferisce il file normalmente con l'utente connesso
            with SCPClient(self.ssh_client.get_transport()) as scp:
                scp.put(str(local_path), str(remote_path))
            
            # Cambia proprietario a www-data usando sudo/su root
            chown_result = self.execute_as_www_data(f"chown www-data:www-data '{remote_path}'")
            if chown_result['exit_status'] != 0:
                logging.warning(f"Attenzione: impossibile cambiare proprietario per {remote_path}")
                logging.warning(f"Errore: {chown_result['error']}")
                logging.info("Il file è stato trasferito ma potrebbe avere proprietario sbagliato")
                # Non fallire per questo, il file è comunque trasferito
            else:
                logging.debug(f"File trasferito e proprietario impostato a www-data: {remote_path}")
            
            return True
            
        except Exception as e:
            logging.error(f"Errore trasferimento file {local_path} -> {remote_path}: {e}")
            return False

    def check_www_data_access(self, remote_path):
        """Verifica se www-data può accedere al percorso remoto"""
        try:
            result = self.execute_as_www_data(f"test -w '{remote_path}' && echo 'writable' || echo 'not_writable'")
            return result['exit_status'] == 0 and result['output'] == 'writable'
        except Exception:
            return False

    def get_client(self):
        """Ritorna il client SSH per operazioni avanzate"""
        return self.ssh_client

class NextcloudCommands:
    """Classe per gestire i comandi specifici di Nextcloud"""
    
    def __init__(self, ssh_manager, nextcloud_path="/var/www/nextcloud"):
        self.ssh_manager = ssh_manager
        self.nextcloud_path = nextcloud_path
    
    def check_and_fix_cache(self, dry_run=False):
        """Controlla e corregge problemi di cache di Nextcloud"""
        if dry_run:
            logging.info("[DRY-RUN] Controllo e correzione cache Nextcloud simulati")
            return True
        
        logging.info("Controllo configurazione cache Nextcloud...")
        
        try:
            # Verifica se APCu è installato
            result = self.ssh_manager.execute_command("php -m | grep -i apcu")
            
            if result['exit_status'] != 0:
                logging.warning("APCu non trovato, tentativo installazione...")
                
                # Comandi per installare APCu
                install_commands = [
                    "apt update",
                    "apt install -y php-apcu",
                    "systemctl restart apache2 nginx php*-fpm || true"
                ]
                
                for cmd in install_commands:
                    logging.info(f"Eseguendo: {cmd}")
                    result = self.ssh_manager.execute_command(cmd, timeout=600)
                    if result['exit_status'] != 0:
                        logging.warning(f"Comando fallito: {cmd} - {result['error']}")
            
            # Configura Nextcloud per usare ArrayCache come fallback
            config_cmd = f"cd {self.nextcloud_path} && sudo -u www-data php occ config:system:set memcache.local --value='\\OC\\Memcache\\ArrayCache' --type=string"
            logging.info("Configurando cache di fallback...")
            result = self.ssh_manager.execute_command(config_cmd)
            
            if result['exit_status'] == 0:
                logging.info("Cache configurata correttamente")
            else:
                logging.warning(f"Errore configurazione cache: {result['error']}")
            
            return True
                
        except Exception as e:
            logging.error(f"Errore controllo cache: {e}")
            return False
    
    def set_file_permissions(self, target_path, dry_run=False):
        """Imposta i permessi corretti sui file"""
        if dry_run:
            logging.info(f"[DRY-RUN] Impostazione permessi file per {target_path}")
            return True
        
        try:
            # Permessi file
            logging.info("Impostando permessi file (644)...")
            result = self.ssh_manager.execute_command(
                f"find '{target_path}' -type f -exec chmod 644 {{}} +",
                timeout=600
            )
            
            if result['exit_status'] != 0:
                logging.error(f"Errore impostazione permessi file: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Errore impostazione permessi file: {e}")
            return False
    
    def set_directory_permissions(self, target_path, dry_run=False):
        """Imposta i permessi corretti sulle directory"""
        if dry_run:
            logging.info(f"[DRY-RUN] Impostazione permessi directory per {target_path}")
            return True
        
        try:
            # Permessi directory
            logging.info("Impostando permessi directory (755)...")
            result = self.ssh_manager.execute_command(
                f"find '{target_path}' -type d -exec chmod 755 {{}} +",
                timeout=600
            )
            
            if result['exit_status'] != 0:
                logging.error(f"Errore impostazione permessi directory: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Errore impostazione permessi directory: {e}")
            return False
    
    def set_ownership(self, target_path, owner="www-data", group="www-data", dry_run=False):
        """Imposta la proprietà corretta sui file"""
        if dry_run:
            logging.info(f"[DRY-RUN] Impostazione proprietà {owner}:{group} per {target_path}")
            return True
        
        try:
            logging.info(f"Impostando proprietà {owner}:{group}...")
            result = self.ssh_manager.execute_command(
                f"chown -R {owner}:{group} '{target_path}'",
                timeout=600
            )
            
            if result['exit_status'] != 0:
                logging.error(f"Errore impostazione proprietà: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Errore impostazione proprietà: {e}")
            return False
    
    def scan_files(self, dry_run=False):
        """Esegue la scansione dei file di Nextcloud"""
        if dry_run:
            logging.info("[DRY-RUN] Scansione file Nextcloud simulata")
            return True
        
        try:
            logging.info("Eseguendo scansione file Nextcloud...")
            result = self.ssh_manager.execute_command(
                f'su -c "php {self.nextcloud_path}/occ files:scan --all" www-data -s /bin/bash',
                timeout=1800  # 30 minuti per la scansione
            )
            
            if result['exit_status'] == 0:
                logging.info("Scansione file completata con successo")
                if result['output']:
                    logging.info(f"Output scansione: {result['output']}")
            else:
                logging.error(f"Errore durante scansione file: {result['error']}")
                return False
            
            return True
            
        except Exception as e:
            logging.error(f"Errore scansione file: {e}")
            return False
    
    def execute_post_sync_commands(self, target_path, dry_run=False):
        """Esegue tutti i comandi post-sincronizzazione"""
        if dry_run:
            logging.info("[DRY-RUN] COMANDI POST-SINCRONIZZAZIONE SIMULATI:")
            logging.info(f"[DRY-RUN] find '{target_path}' -type f -exec chmod 644 {{}} +")
            logging.info(f"[DRY-RUN] find '{target_path}' -type d -exec chmod 755 {{}} +")
            logging.info(f"[DRY-RUN] chown -R www-data:www-data '{target_path}'")
            logging.info("[DRY-RUN] su -c \"php /var/www/nextcloud/occ files:scan --all\" www-data -s /bin/bash")
            logging.info("[DRY-RUN] Configurazione cache Nextcloud")
            return True
        
        logging.info("Esecuzione comandi post-sincronizzazione...")
        
        # Lista dei passaggi da eseguire
        steps = [
            ("Correzione cache", lambda: self.check_and_fix_cache(dry_run)),
            ("Permessi file", lambda: self.set_file_permissions(target_path, dry_run)),
            ("Permessi directory", lambda: self.set_directory_permissions(target_path, dry_run)),
            ("Proprietà file", lambda: self.set_ownership(target_path, dry_run=dry_run)),
            ("Scansione Nextcloud", lambda: self.scan_files(dry_run))
        ]
        
        success_count = 0
        for step_name, step_func in steps:
            try:
                logging.info(f"Eseguendo: {step_name}...")
                if step_func():
                    success_count += 1
                    logging.info(f"{step_name} completato con successo")
                else:
                    logging.error(f"{step_name} fallito")
            except Exception as e:
                logging.error(f"Errore durante {step_name}: {e}")
        
        logging.info(f"Comandi post-sincronizzazione completati: {success_count}/{len(steps)} riusciti")
        return success_count == len(steps)