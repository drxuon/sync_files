#!/usr/bin/env python3
"""
Database Manager per la sincronizzazione Nextcloud
Gestisce tutte le operazioni sul database SQLite locale
"""

import sqlite3
from pathlib import Path

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
    
    def get_sync_statistics(self, sync_id):
        """Ottiene statistiche dettagliate per una sincronizzazione"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Statistiche generali
            cursor.execute('SELECT * FROM sync_reports WHERE id = ?', (sync_id,))
            report = cursor.fetchone()
            
            # File trasferiti
            cursor.execute('''
                SELECT COUNT(*), SUM(file_size) FROM transferred_files 
                WHERE sync_id = ? AND processing_status = 'COMPLETED'
            ''', (sync_id,))
            files_stats = cursor.fetchone()
            
            # Errori
            cursor.execute('SELECT * FROM sync_errors WHERE sync_id = ?', (sync_id,))
            errors = cursor.fetchall()
            
            return {
                'report': report,
                'files_count': files_stats[0] or 0,
                'total_size': files_stats[1] or 0,
                'errors': errors
            }