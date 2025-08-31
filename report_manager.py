#!/usr/bin/env python3
"""
Report Manager per la sincronizzazione Nextcloud
Gestisce i report e le statistiche della sincronizzazione
"""

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
        """Aggiunge un file trasferito alle statistiche"""
        self.files_transferred += 1
        self.total_size_transferred += file_size
        
    def add_duplicate(self):
        """Aggiunge un duplicato alle statistiche"""
        self.duplicates_found += 1
        
    def add_renamed_duplicate(self):
        """Aggiunge un duplicato rinominato alle statistiche"""
        self.duplicates_renamed += 1
        
    def add_error(self, error_msg):
        """Aggiunge un errore al report"""
        self.errors.append(error_msg)
        
    def add_skipped(self):
        """Aggiunge un file saltato alle statistiche"""
        self.skipped_files += 1
    
    def add_already_processed(self):
        """Aggiunge un file già processato alle statistiche"""
        self.already_processed += 1

class ReportFormatter:
    @staticmethod
    def format_size(size_bytes):
        """Formatta la dimensione in modo leggibile"""
        if size_bytes == 0:
            return "0 B"
        
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"
    
    @staticmethod
    def format_duration(seconds):
        """Formatta la durata in modo leggibile"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    @staticmethod
    def print_sync_report(report, duration, sync_id=None, resumed_from_id=None, dry_run=False):
        """Stampa il report finale della sincronizzazione"""
        print("\n" + "="*60)
        if dry_run:
            print("REPORT DRY-RUN COMPLETATO")
        else:
            print("REPORT SINCRONIZZAZIONE COMPLETATA")
        print("="*60)
        
        print(f"Durata: {ReportFormatter.format_duration(duration.total_seconds())}")
        
        if dry_run:
            print(f"File che sarebbero trasferiti: {report.files_transferred}")
            print(f"Duplicati che sarebbero trovati: {report.duplicates_found}")
            print(f"Duplicati che sarebbero rinominati: {report.duplicates_renamed}")
            print(f"File già elaborati (che sarebbero skippati): {report.already_processed}")
            print(f"Dimensione totale che sarebbe trasferita: {ReportFormatter.format_size(report.total_size_transferred)}")
        else:
            print(f"File trasferiti: {report.files_transferred}")
            print(f"Duplicati trovati: {report.duplicates_found}")
            print(f"Duplicati rinominati: {report.duplicates_renamed}")
            print(f"File già elaborati (skippati): {report.already_processed}")
            print(f"File saltati (errori): {report.skipped_files}")
            print(f"Dimensione totale trasferita: {ReportFormatter.format_size(report.total_size_transferred)}")
        
        if sync_id:
            print(f"Database sync ID: {sync_id}")
        if resumed_from_id:
            print(f"Ripresa da sync ID: {resumed_from_id}")
        
        if report.errors:
            print(f"\nErrori ({len(report.errors)}):")
            for error in report.errors[-5:]:  # Mostra ultimi 5 errori
                print(f"  - {error}")
            if len(report.errors) > 5:
                print(f"  ... e altri {len(report.errors) - 5} errori (vedi database)")
        
        if dry_run:
            print("\n🔍 MODALITÀ DRY-RUN: Nessun file è stato trasferito realmente.")
            print("   Esegui senza --dry-run per effettuare il trasferimento.")
        
        print("="*60)
    
    @staticmethod
    def show_recent_reports(db_manager, limit=10):
        """Mostra i report recenti dal database"""
        reports = db_manager.get_recent_reports(limit)
        
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
                size_str = ReportFormatter.format_size(total_size_bytes)
                duration_str = ReportFormatter.format_duration(duration_seconds) if duration_seconds else "N/A"
                print(f"Dimensione: {size_str} | Durata: {duration_str}")
        
        print("="*80)
    
    @staticmethod
    def show_detailed_report(db_manager, sync_id):
        """Mostra un report dettagliato per una specifica sincronizzazione"""
        stats = db_manager.get_sync_statistics(sync_id)
        
        if not stats['report']:
            print(f"Sincronizzazione con ID {sync_id} non trovata")
            return
        
        report = stats['report']
        print(f"\n" + "="*60)
        print(f"REPORT DETTAGLIATO - SYNC ID: {sync_id}")
        print("="*60)
        
        print(f"Data: {report[1]}")
        print(f"Status: {report[12]}")
        print(f"Percorso sorgente: {report[10]}")
        print(f"Percorso destinazione: {report[11]}")
        
        if report[13]:  # resumed_from_id
            print(f"Ripresa da sync ID: {report[13]}")
        
        print(f"\nStatistiche:")
        print(f"  File trasferiti: {report[2]}")
        print(f"  Duplicati trovati: {report[3]}")
        print(f"  Duplicati rinominati: {report[4]}")
        print(f"  File già processati: {report[7]}")
        print(f"  File saltati: {report[6]}")
        print(f"  Errori: {report[5]}")
        
        if report[8]:  # total_size_bytes
            print(f"  Dimensione totale: {ReportFormatter.format_size(report[8])}")
        
        if report[9]:  # duration_seconds
            print(f"  Durata: {ReportFormatter.format_duration(report[9])}")
        
        if stats['errors']:
            print(f"\nErrori ({len(stats['errors'])}):")
            for error in stats['errors']:
                error_id, sync_id, error_msg, file_path, error_date = error
                print(f"  [{error_date}] {error_msg}")
                if file_path:
                    print(f"    File: {file_path}")
        
        print("="*60)