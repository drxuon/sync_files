#!/usr/bin/env python3
"""
Script principale per la sincronizzazione file multimediali da Raspberry Pi a Nextcloud
con gestione duplicati, database SQLite locale, ripresa automatica e dry-run
"""

import argparse
import sys
import logging
import os
from pathlib import Path

# Import dei moduli personalizzati
try:
    from database_manager import DatabaseManager
    from report_manager import ReportFormatter
    from sync_manager import NextcloudMediaSync
except ImportError as e:
    print(f"❌ Errore importazione moduli: {e}")
    print("   Assicurati che tutti i file .py siano nella stessa directory")
    sys.exit(1)

def setup_logging(verbose=False):
    """Configura il sistema di logging"""
    log_level = logging.DEBUG if verbose else logging.INFO
    
    # Configura il logging base
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('nextcloud_sync.log'),
            logging.StreamHandler()
        ]
    )

def validate_paths(args):
    """Valida i percorsi forniti"""
    errors = []
    
    # Controlla percorso sorgente locale
    if args.local_source:
        source_path = Path(args.local_source)
        if not source_path.exists():
            errors.append(f"Percorso sorgente non trovato: {args.local_source}")
        elif not source_path.is_dir():
            errors.append(f"Percorso sorgente non è una directory: {args.local_source}")
    
    # Controlla chiave SSH se specificata
    if args.ssh_key:
        ssh_key_path = Path(args.ssh_key)
        if not ssh_key_path.exists():
            errors.append(f"Chiave SSH non trovata: {args.ssh_key}")
        elif not ssh_key_path.is_file():
            errors.append(f"Chiave SSH non è un file: {args.ssh_key}")
    
    # Controlla directory database
    if args.db_path:
        db_dir = Path(args.db_path).parent
        if not db_dir.exists():
            try:
                db_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                errors.append(f"Impossibile creare directory database: {e}")
    
    return errors

def print_banner():
    """Stampa il banner di avvio"""
    print("="*60)
    print("🔄 NEXTCLOUD MEDIA SYNC")
    print("   Sincronizzazione intelligente file multimediali")
    print("="*60)

def print_config_summary(args):
    """Stampa un riassunto della configurazione"""
    print("\n📋 CONFIGURAZIONE:")
    print(f"   🖥️  Server Nextcloud: {args.nextcloud_user}@{args.nextcloud_host}")
    print(f"   📂 Sorgente locale: {args.local_source}")
    print(f"   📁 Destinazione: {args.nextcloud_dest}")
    
    if args.ssh_key:
        print(f"   🔑 Chiave SSH: {args.ssh_key}")
    else:
        print("   🔑 Autenticazione: Password (verrà richiesta)")
    
    if args.extensions:
        print(f"   📄 Estensioni: {', '.join(args.extensions)}")
    else:
        print("   📄 Estensioni: Tutte le estensioni multimediali")
    
    print(f"   🗃️  Database: {args.db_path}")
    
    if args.dry_run:
        print("   🔍 Modalità: DRY-RUN (simulazione)")
    else:
        print("   ⚡ Modalità: SINCRONIZZAZIONE REALE")

def handle_sync_setup(syncer, args, db):
    """Gestisce le opzioni di setup della sincronizzazione"""
    if args.resume:
        syncer.force_resume_from_sync(args.resume)
        print(f"\n🔄 RIPRESA FORZATA:")
        print(f"   📋 Ripresa dalla sincronizzazione ID: {args.resume}")
        
    elif args.force_new:
        print(f"\n🆕 NUOVA SINCRONIZZAZIONE FORZATA:")
        print(f"   ⚠️  Ignorando sincronizzazioni incomplete esistenti")
        
        # Marca eventuali sync incomplete come interrotte
        incomplete_id = db.find_incomplete_sync(syncer.local_source_path, syncer.nextcloud_dest_path)
        if incomplete_id:
            db.mark_sync_interrupted(incomplete_id)
            print(f"   📝 Sincronizzazione {incomplete_id} marcata come interrotta")
        else:
            print(f"   ✅ Nessuna sincronizzazione incompleta trovata")

def main():
    parser = argparse.ArgumentParser(
        description='Sincronizzazione file multimediali da Raspberry Pi a Nextcloud',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
ESEMPI DI UTILIZZO:

  🔍 Test iniziale (DRY-RUN):
    python main.py --dry-run \\
                   --nextcloud-host 192.168.1.200 \\
                   --local-source /home/pi/photos \\
                   --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos

  ⚡ Sincronizzazione completa:
    python main.py --nextcloud-host 192.168.1.200 --nextcloud-user root \\
                   --nextcloud-dest /var/www/nextcloud/data/admin/files/Photos \\
                   --local-source /home/pi/photos --ssh-key ~/.ssh/id_rsa

  🔄 Gestione interruzioni:
    python main.py --resume 15 --nextcloud-host server --local-source /photos --nextcloud-dest /dest
    python main.py --force-new --nextcloud-host server --local-source /photos --nextcloud-dest /dest

  📊 Report e monitoraggio:
    python main.py --show-reports
    python main.py --show-detail 15

  🎯 Estensioni specifiche:
    python main.py --extensions .jpg .png --nextcloud-host server --local-source /photos --nextcloud-dest /dest
        """
    )
    
    # Gruppi di argomenti per migliore organizzazione
    connection_group = parser.add_argument_group('🔗 CONNESSIONE NEXTCLOUD')
    connection_group.add_argument('--nextcloud-host', required=False, 
                                help='IP/hostname del server Nextcloud')
    connection_group.add_argument('--nextcloud-user', required=False,
                                help='Username SSH per Nextcloud (es: davide)')
    connection_group.add_argument('--ssh-key', 
                                help='Percorso chiave SSH privata')
    
    paths_group = parser.add_argument_group('📁 PERCORSI')
    paths_group.add_argument('--local-source', required=False,
                           help='Percorso sorgente locale sul Raspberry Pi')
    paths_group.add_argument('--nextcloud-dest', required=False,
                           help='Percorso destinazione su Nextcloud')
    
    options_group = parser.add_argument_group('⚙️ OPZIONI SINCRONIZZAZIONE')
    options_group.add_argument('--extensions', nargs='*',
                             help='Estensioni da sincronizzare (es: .jpg .mp4)')
    options_group.add_argument('--db-path', default='nextcloud_sync.db',
                             help='Percorso database SQLite (default: nextcloud_sync.db)')
    options_group.add_argument('--dry-run', action='store_true',
                             help='Simula operazioni senza trasferire file')
    
    control_group = parser.add_argument_group('🎛️ CONTROLLO ESECUZIONE')
    control_group.add_argument('--force-new', action='store_true',
                             help='Forza nuova sincronizzazione ignorando quelle incomplete')
    control_group.add_argument('--resume', type=int, metavar='SYNC_ID',
                             help='Riprendi sincronizzazione specifica dal database')
    
    report_group = parser.add_argument_group('📊 REPORT E MONITORAGGIO')
    report_group.add_argument('--show-reports', action='store_true',
                            help='Mostra report delle sincronizzazioni recenti')
    report_group.add_argument('--show-detail', type=int, metavar='SYNC_ID',
                            help='Mostra dettagli di una sincronizzazione specifica')
    
    debug_group = parser.add_argument_group('🐛 DEBUG')
    debug_group.add_argument('--verbose', '-v', action='store_true',
                           help='Output di debug più dettagliato')
    debug_group.add_argument('--version', action='version', version='Nextcloud Media Sync 1.0.0')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Banner di avvio
    print_banner()
    
    try:
        # Inizializza database
        db = DatabaseManager(args.db_path)
        
        # Gestione comandi di sola lettura (non richiedono connessione)
        if args.show_reports:
            print("\n📊 REPORT SINCRONIZZAZIONI RECENTI:")
            ReportFormatter.show_recent_reports(db)
            return 0
        
        if args.show_detail:
            print(f"\n🔍 DETTAGLI SINCRONIZZAZIONE ID {args.show_detail}:")
            ReportFormatter.show_detailed_report(db, args.show_detail)
            return 0
        
        # Validazione argomenti obbligatori per sincronizzazione
        missing_args = []
        if not args.nextcloud_host:
            missing_args.append('--nextcloud-host')
        if not args.nextcloud_user:
            missing_args.append('--nextcloud-user')
        if not args.nextcloud_dest:
            missing_args.append('--nextcloud-dest')
        if not args.local_source:
            missing_args.append('--local-source')
        
        if missing_args:
            print(f"\n❌ ERRORE: Argomenti obbligatori mancanti: {', '.join(missing_args)}")
            print("\n💡 SUGGERIMENTO:")
            print("   Per vedere solo i report: python main.py --show-reports")
            print("   Per sincronizzazione: specifica tutti i percorsi richiesti")
            print("\n📖 Usa 'python main.py --help' per la guida completa")
            return 1
        
        # Validazione percorsi
        path_errors = validate_paths(args)
        if path_errors:
            print("\n❌ ERRORI DI VALIDAZIONE:")
            for error in path_errors:
                print(f"   • {error}")
            return 1
        
        # Mostra configurazione
        print_config_summary(args)
        
        # Crea il sincronizzatore
        print("\n🔧 INIZIALIZZAZIONE SINCRONIZZATORE...")
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
        
        # Gestione opzioni di controllo
        handle_sync_setup(syncer, args, db)
        
        # Conferma prima dell'avvio (solo se non dry-run)
        if not args.dry_run and not args.resume and not args.force_new:
            print(f"\n⚠️  CONFERMA RICHIESTA:")
            print(f"   Stai per avviare una sincronizzazione REALE")
            print(f"   I file verranno trasferiti su {args.nextcloud_host}")
            
            response = input("\n❓ Procedere? [y/N]: ").strip().lower()
            if response not in ['y', 'yes', 's', 'si']:
                print("   🛑 Sincronizzazione annullata dall'utente")
                print("   💡 Usa --dry-run per testare senza trasferire file")
                return 0
        
        # Avvio sincronizzazione
        print(f"\n🚀 AVVIO SINCRONIZZAZIONE:")
        print(f"   🔗 Connessione a: {args.nextcloud_user}@{args.nextcloud_host}")
        print(f"   📤 Trasferimento: {args.local_source} -> {args.nextcloud_dest}")
        
        if args.dry_run:
            print(f"   🔍 MODALITÀ DRY-RUN: Solo simulazione, nessun trasferimento reale")
        
        print()  # Riga vuota prima dei log di sincronizzazione
        
        # Esegue la sincronizzazione
        success = syncer.sync_files()
        
        # Gestione risultati finali
        if args.dry_run:
            print("\n" + "="*60)
            print("🔍 DRY-RUN COMPLETATO!")
            print("="*60)
            print("✨ La simulazione è completata con successo")
            print("💡 Nessun file è stato trasferito realmente")
            print("🚀 Esegui senza --dry-run per la sincronizzazione reale")
            print("📊 Controlla i dettagli nel report sopra")
            return 0
            
        elif success:
            print("\n" + "="*60)
            print("✅ SINCRONIZZAZIONE COMPLETATA CON SUCCESSO!")
            print("="*60)
            print("🎉 Tutti i file sono stati sincronizzati correttamente")
            print("🔍 Controlla Nextcloud per verificare i file trasferiti")
            print(f"📝 Log completo disponibile in: nextcloud_sync.log")
            print(f"🗃️  Database aggiornato: {args.db_path}")
            return 0
            
        else:
            print("\n" + "="*60)
            print("❌ SINCRONIZZAZIONE COMPLETATA CON ERRORI")
            print("="*60)
            print("⚠️  Alcuni file potrebbero non essere stati trasferiti")
            print("🔍 Controlla il report sopra per i dettagli degli errori")
            print(f"📝 Log completo: nextcloud_sync.log")
            print("🔄 Riavvia lo script per riprovare con i file falliti")
            return 1
    
    except KeyboardInterrupt:
        print("\n" + "="*60)
        print("🛑 INTERRUZIONE MANUALE")
        print("="*60)
        print("⚠️  Sincronizzazione interrotta dall'utente (Ctrl+C)")
        
        if not args.dry_run:
            print(f"💾 Il progresso è stato salvato nel database: {args.db_path}")
            print("🔄 Riavvia lo script per continuare da dove si era fermato")
            print("   Lo script rileverà automaticamente la sincronizzazione incompleta")
        
        return 130  # Exit code standard per SIGINT
    
    except Exception as e:
        print("\n" + "="*60)
        print("💥 ERRORE CRITICO")
        print("="*60)
        print(f"❌ Errore imprevisto: {e}")
        print(f"📝 Dettagli completi salvati in: nextcloud_sync.log")
        print("🐛 Se il problema persiste, controlla:")
        print("   • Connessione di rete")
        print("   • Permessi sui file")
        print("   • Spazio disco disponibile")
        print("   • Configurazione SSH")
        
        if args.verbose:
            import traceback
            print("\n🔍 STACK TRACE (modalità verbose):")
            traceback.print_exc()
        
        logging.exception("Errore critico durante l'esecuzione")
        return 1

if __name__ == "__main__":
    # Gestisce l'esecuzione come script principale
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n💥 Errore fatale: {e}")
        sys.exit(1)