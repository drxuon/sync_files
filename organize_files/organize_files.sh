#!/bin/bash

# Script per organizzare file multimediali in struttura anno/mese
# Uso: ./organize_files.sh /path/to/source /path/to/destination [--dry-run]

SOURCE_DIR=""
DEST_DIR=""
DRY_RUN=false

# Analizza i parametri
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            if [ -z "$SOURCE_DIR" ]; then
                SOURCE_DIR="$1"
            elif [ -z "$DEST_DIR" ]; then
                DEST_DIR="$1"
            else
                echo "Errore: Troppi parametri"
                echo "Uso: $0 <directory_sorgente> <directory_destinazione> [--dry-run]"
                exit 1
            fi
            shift
            ;;
    esac
done

# Controlla che siano stati forniti i parametri obbligatori
if [ -z "$SOURCE_DIR" ] || [ -z "$DEST_DIR" ]; then
    echo "Uso: $0 <directory_sorgente> <directory_destinazione> [--dry-run]"
    echo ""
    echo "Opzioni:"
    echo "  --dry-run    Simula l'esecuzione senza effettuare modifiche reali"
    exit 1
fi

# Controlla che le directory esistano
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Errore: Directory sorgente non trovata: $SOURCE_DIR"
    exit 1
fi

# Crea la directory destinazione se non esiste
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$DEST_DIR"
fi

# Contatori per statistiche
MOVED=0
SKIPPED=0
ERRORS=0
DUPLICATES_FOUND=0

# Array per tenere traccia dei duplicati
declare -a DUPLICATE_FILES

# File di checkpoint per restart intelligente
CHECKPOINT_FILE="/tmp/organize_files_checkpoint_$$"
PROCESSED_FILES_LOG="/tmp/organize_files_processed_$$"

# Funzione per caricare checkpoint esistente
load_checkpoint() {
    if [ -f "$CHECKPOINT_FILE" ] && [ "$DRY_RUN" = false ]; then
        echo "=========================================="
        echo "CHECKPOINT TROVATO - CARICAMENTO DATI"
        echo "=========================================="
        source "$CHECKPOINT_FILE"
        echo "Caricati dati sessione precedente:"
        echo "- File già spostati: $MOVED"
        echo "- File già saltati: $SKIPPED"  
        echo "- Duplicati già trovati: $DUPLICATES_FOUND"
        echo "- Errori precedenti: $ERRORS"
        echo ""
        
        if [ -f "$PROCESSED_FILES_LOG" ]; then
            processed_count=$(wc -l < "$PROCESSED_FILES_LOG")
            echo "- File già processati: $processed_count"
            echo ""
            echo "Riprendendo l'elaborazione..."
        fi
        echo "----------------------------------------"
    elif [ -f "$CHECKPOINT_FILE" ] && [ "$DRY_RUN" = true ]; then
        echo "ℹ️  Checkpoint esistente ignorato in modalità dry-run"
    fi
}

# Funzione per salvare checkpoint
save_checkpoint() {
    if [ "$DRY_RUN" = false ]; then
        cat > "$CHECKPOINT_FILE" << EOF
MOVED=$MOVED
SKIPPED=$SKIPPED
ERRORS=$ERRORS
DUPLICATES_FOUND=$DUPLICATES_FOUND
declare -a DUPLICATE_FILES=($(printf "'%s' " "${DUPLICATE_FILES[@]}"))
EOF
    fi
}

# Funzione per verificare se un file è già stato processato
is_file_processed() {
    local file_path="$1"
    if [ -f "$PROCESSED_FILES_LOG" ] && [ "$DRY_RUN" = false ]; then
        grep -Fxq "$file_path" "$PROCESSED_FILES_LOG" 2>/dev/null
    else
        return 1  # File non processato
    fi
}

# Funzione per marcare un file come processato
mark_file_processed() {
    local file_path="$1"
    if [ "$DRY_RUN" = false ]; then
        echo "$file_path" >> "$PROCESSED_FILES_LOG"
    fi
}

# Gestione interruzioni (Ctrl+C)
cleanup() {
    echo ""
    echo "=========================================="
    echo "INTERRUZIONE RILEVATA - SALVATAGGIO STATO"
    echo "=========================================="
    
    # Salva checkpoint finale
    save_checkpoint
    
    echo "Operazione interrotta dall'utente"
    echo ""
    echo "STATISTICHE PARZIALI:"
    echo "- File processati prima dell'interruzione: $((MOVED + SKIPPED + ERRORS + DUPLICATES_FOUND))"
    echo "- File spostati con successo: $MOVED"
    echo "- File saltati (data non valida): $SKIPPED"
    echo "- File duplicati trovati e rinominati: $DUPLICATES_FOUND"
    echo "- Errori: $ERRORS"
    
    if [ ${#DUPLICATE_FILES[@]} -gt 0 ]; then
        echo ""
        echo "FILE DUPLICATI TROVATI E RINOMINATI:"
        for dup_file in "${DUPLICATE_FILES[@]}"; do
            echo "  • $dup_file"
        done
    fi
    
    echo ""
    echo "📁 Checkpoint salvato in: $CHECKPOINT_FILE"
    echo "📝 Log file processati: $PROCESSED_FILES_LOG"
    echo ""
    echo "Per riprendere dal punto di interruzione, rilancia:"
    echo "$0 \"$SOURCE_DIR\" \"$DEST_DIR\""
    echo ""
    echo "Per ricominciare da capo, cancella prima i file di checkpoint:"
    echo "rm -f \"$CHECKPOINT_FILE\" \"$PROCESSED_FILES_LOG\""
    
    exit 1
}

# Cattura segnali di interruzione
trap cleanup INT TERM

# Modalità dry-run
if [ "$DRY_RUN" = true ]; then
    echo "=== MODALITÀ DRY-RUN ATTIVA ==="
    echo "Nessuna modifica verrà effettuata realmente"
    echo ""
fi

echo "Inizio organizzazione file da $SOURCE_DIR a $DEST_DIR"
echo "Scansione ricorsiva di tutte le sottodirectory..."
echo "Esclusione file con pattern *_DUP.*"
echo "----------------------------------------"

# Carica checkpoint se esistente
load_checkpoint

# Conta i file da processare (solo se non in dry-run per non rallentare)
if [ "$DRY_RUN" = false ]; then
    echo "Conteggio file da processare..."
    total_files_to_process=$(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) ! -name "*_DUP.*" | wc -l)
    
    excluded_files=$(find "$SOURCE_DIR" -type f -name "*_DUP.*" | wc -l)
    
    echo "File multimediali trovati: $total_files_to_process"
    if [ "$excluded_files" -gt 0 ]; then
        echo "File _DUP.* esclusi: $excluded_files"
    fi
    echo "----------------------------------------"
fi

# Crea file temporanei per i contatori in dry-run
if [ "$DRY_RUN" = true ]; then
    TEMP_COUNTERS="/tmp/organize_counters_$"
    echo "MOVED=0" > "$TEMP_COUNTERS"
    echo "SKIPPED=0" >> "$TEMP_COUNTERS"
    echo "ERRORS=0" >> "$TEMP_COUNTERS"
    echo "DUPLICATES_FOUND=0" >> "$TEMP_COUNTERS"
    echo "DUPLICATE_FILES=()" >> "$TEMP_COUNTERS"
fi

# Trova tutti i file multimediali ricorsivamente, escludendo i file _DUP
while IFS= read -r -d '' file; do
    
    # Controlla se il file è già stato processato
    if is_file_processed "$file"; then
        if [ "$DRY_RUN" = false ]; then
            # In modalità normale, salta i file già processati silenziosamente
            continue
        fi
    fi
    
    filename=$(basename "$file")
    relative_path="${file#$SOURCE_DIR/}"
    echo "Processando: $relative_path"
    
    # Estrai data dal nome file - diversi formati possibili con prefissi/suffissi
    year=""
    month=""
    
    # Formato: [prefisso_]YYYY-MM-DD[_suffisso] o [prefisso_]YYYY_MM_DD[_suffisso] o [prefisso_]YYYYMMDD[_suffisso]
    if [[ $filename =~ ([^0-9]*)([0-9]{4})[-_]?([0-9]{2})[-_]?([0-9]{2})(.*)$ ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        echo "  Data trovata (YYYY-MM-DD): $year-$month"
    # Formato: [prefisso_]DD-MM-YYYY[_suffisso] o [prefisso_]DD_MM_YYYY[_suffisso] o [prefisso_]DD/MM/YYYY[_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{1,2})[-_/]([0-9]{1,2})[-_/]([0-9]{4})(.*)$ ]]; then
        potential_year="${BASH_REMATCH[4]}"
        potential_month="${BASH_REMATCH[3]}"
        # Rimuovi zeri iniziali e assicurati che il mese sia valido (01-12)
        potential_month=$((10#$potential_month))
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            echo "  Data trovata (DD-MM-YYYY): $year-$month"
        else
            year=""
            month=""
        fi
    # Formato: [prefisso_]MM-DD-YYYY[_suffisso] (formato americano)
    elif [[ $filename =~ ([^0-9]*)([0-9]{1,2})[-_/]([0-9]{1,2})[-_/]([0-9]{4})(.*)$ ]]; then
        potential_year="${BASH_REMATCH[4]}"
        potential_month="${BASH_REMATCH[2]}"
        # Rimuovi zeri iniziali e assicurati che il mese sia valido (01-12)
        potential_month=$((10#$potential_month))
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            echo "  Data trovata (MM-DD-YYYY): $year-$month"
        else
            year=""
            month=""
        fi
    # Formato con timestamp: [prefisso_]YYYY[MM[DD[_HHMMSS]]][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})([0-9]{2})([0-9]{2})[^0-9]*(.*) ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        echo "  Data trovata (YYYYMMDD): $year-$month"
    # Formato ISO con prefisso/suffisso: [prefisso_]YYYY[MM][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})[^0-9]*([0-9]{2})[^0-9]*(.*) ]]; then
        potential_year="${BASH_REMATCH[2]}"
        potential_month="${BASH_REMATCH[3]}"
        # Rimuovi zeri iniziali e valida il mese
        potential_month=$((10#$potential_month))
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            echo "  Data trovata (YYYY-MM): $year-$month"
        fi
    fi
    
    # Se non riesci a estrarre la data, prova con i metadati del file
    if [ -z "$year" ] || [ -z "$month" ]; then
        # Usa exiftool se disponibile (solo se non in dry-run o per test)
        if command -v exiftool >/dev/null 2>&1 && [ "$DRY_RUN" = false ]; then
            date_taken=$(exiftool -DateTimeOriginal -d "%Y-%m" -T "$file" 2>/dev/null)
            if [ -n "$date_taken" ] && [ "$date_taken" != "-" ]; then
                year=$(echo "$date_taken" | cut -d'-' -f1)
                month=$(echo "$date_taken" | cut -d'-' -f2)
                echo "  Data da metadati EXIF: $year-$month"
            fi
        elif [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] Proverei a estrarre data da metadati EXIF"
        fi
        
        # Se ancora non hai la data, usa la data di modifica del file
        if [ -z "$year" ] || [ -z "$month" ]; then
            if [ "$DRY_RUN" = false ]; then
                file_date=$(stat -c %Y "$file")
                year=$(date -d "@$file_date" +%Y)
                month=$(date -d "@$file_date" +%m)
            else
                # In dry-run, simula una data di modifica
                year=$(date +%Y)
                month=$(date +%m)
            fi
            echo "  Usando data di modifica: $year-$month"
        fi
    fi
    
    # Valida anno e mese
    if [ -n "$year" ] && [ -n "$month" ] && [ "$year" -ge 1990 ] && [ "$year" -le $(date +%Y) ]; then
        # Rimuovi zeri iniziali dal mese per evitare problemi con printf octal
        month_num=$((10#$month))
        if [ "$month_num" -ge 1 ] && [ "$month_num" -le 12 ]; then
            # Crea directory destinazione
            month_formatted=$(printf "%02d" $month_num)
            dest_dir="$DEST_DIR/$year/$month_formatted"
            
            if [ "$DRY_RUN" = false ]; then
                mkdir -p "$dest_dir"
            else
                echo "  [DRY-RUN] Creerei directory: $dest_dir"
            fi
            
            dest_file="$dest_dir/$filename"
            
            # CONTROLLO CRITICO: Verifica se il file è già nella posizione corretta
            if [ "$DRY_RUN" = false ]; then
                source_real=$(realpath "$file" 2>/dev/null)
                dest_real=$(realpath "$dest_file" 2>/dev/null)
                
                # Se i percorsi reali sono identici, il file è già al posto giusto
                if [ -n "$source_real" ] && [ -n "$dest_real" ] && [ "$source_real" = "$dest_real" ]; then
                    echo "  File già nella posizione corretta, saltato"
                    ((SKIPPED++))
                    mark_file_processed "$file"
                    save_checkpoint
                    continue
                fi
            fi
            
            # Controlla se il file esiste già nella destinazione
            if [ -f "$dest_file" ] || ( [ "$DRY_RUN" = true ] && [ -f "$dest_file" ] ); then
                # Simula controllo file esistente anche in dry-run
                file_exists=false
                files_identical=false
                
                if [ -f "$dest_file" ]; then
                    file_exists=true
                    if cmp -s "$file" "$dest_file" 2>/dev/null; then
                        files_identical=true
                    fi
                elif [ "$DRY_RUN" = true ]; then
                    # In dry-run, simula casualmente esistenza e identità file per demo
                    if (( RANDOM % 4 == 0 )); then  # 25% probabilità file esistente
                        file_exists=true
                        if (( RANDOM % 2 == 0 )); then  # 50% probabilità file identico
                            files_identical=true
                        fi
                    fi
                fi
                
                if [ "$file_exists" = true ] && [ "$files_identical" = true ]; then
                    echo "  File identico trovato nella destinazione, rinomino sorgente con _DUP"
                    base_name="${filename%.*}"
                    extension="${filename##*.}"
                    
                    # Trova un nome libero per il duplicato nella directory sorgente
                    dup_counter=1
                    dup_name="${base_name}_DUP"
                    if [ -n "$extension" ]; then
                        dup_filename="${dup_name}.$extension"
                    else
                        dup_filename="$dup_name"
                    fi
                    
                    dup_path="$(dirname "$file")/$dup_filename"
                    
                    if [ "$DRY_RUN" = false ]; then
                        while [ -f "$dup_path" ]; do
                            dup_name="${base_name}_DUP$dup_counter"
                            if [ -n "$extension" ]; then
                                dup_filename="${dup_name}.$extension"
                            else
                                dup_filename="$dup_name"
                            fi
                            dup_path="$(dirname "$file")/$dup_filename"
                            ((dup_counter++))
                        done
                        
                        # Rinomina il file nella directory sorgente
                        if mv "$file" "$dup_path"; then
                            echo "  File rinominato come duplicato: $dup_filename"
                            DUPLICATE_FILES+=("$dup_filename")
                            ((DUPLICATES_FOUND++))
                            mark_file_processed "$file"
                            save_checkpoint
                        else
                            echo "  ERRORE nel rinominare il duplicato"
                            ((ERRORS++))
                            mark_file_processed "$file"
                            save_checkpoint
                        fi
                    else
                        echo "  [DRY-RUN] Rinominerei file come duplicato: $dup_filename"
                        DUPLICATE_FILES+=("$dup_filename")
                        ((DUPLICATES_FOUND++))
                    fi
                    continue
                    
                elif [ "$file_exists" = true ]; then
                    # File diverso con stesso nome - crea versione numerata nella destinazione
                    counter=1
                    base_name="${filename%.*}"
                    extension="${filename##*.}"
                    
                    if [ "$DRY_RUN" = false ]; then
                        while [ -f "$dest_dir/${base_name}_$counter.$extension" ]; do
                            ((counter++))
                        done
                    fi
                    
                    dest_file="$dest_dir/${base_name}_$counter.$extension"
                    echo "  File diverso con stesso nome, rinominato in: ${base_name}_$counter.$extension"
                    if [ "$DRY_RUN" = true ]; then
                        echo "  [DRY-RUN] Creerei file con nome modificato"
                    fi
                fi
            fi
            
            # Sposta il file
            if [ "$DRY_RUN" = false ]; then
                if mv "$file" "$dest_file"; then
                    echo "  Spostato in: $dest_dir/"
                    ((MOVED++))
                    mark_file_processed "$file"
                    save_checkpoint
                else
                    echo "  ERRORE nello spostamento"
                    ((ERRORS++))
                    mark_file_processed "$file"
                    save_checkpoint
                fi
            else
                echo "  [DRY-RUN] Sposterei in: $dest_dir/"
                ((MOVED++))
            fi
        else
            echo "  Data non valida estratta: $year-$month_formatted, saltato"
            if [ "$DRY_RUN" = true ]; then
                echo "  [DRY-RUN] File non verrebbe spostato"
                source "$TEMP_COUNTERS"
                ((SKIPPED++))
                echo "MOVED=$MOVED" > "$TEMP_COUNTERS"
                echo "SKIPPED=$SKIPPED" >> "$TEMP_COUNTERS"
                echo "ERRORS=$ERRORS" >> "$TEMP_COUNTERS"
                echo "DUPLICATES_FOUND=$DUPLICATES_FOUND" >> "$TEMP_COUNTERS"
                printf "DUPLICATE_FILES=(" >> "$TEMP_COUNTERS"
                printf "'%s' " "${DUPLICATE_FILES[@]}" >> "$TEMP_COUNTERS"
                printf ")\n" >> "$TEMP_COUNTERS"
            else
                ((SKIPPED++))
                mark_file_processed "$file"
                save_checkpoint
            fi
        fi
    else
        echo "  Data non valida estratta: $year-$month, saltato"
        if [ "$DRY_RUN" = true ]; then
            echo "  [DRY-RUN] File non verrebbe spostato"
            source "$TEMP_COUNTERS"
            ((SKIPPED++))
            echo "MOVED=$MOVED" > "$TEMP_COUNTERS"
            echo "SKIPPED=$SKIPPED" >> "$TEMP_COUNTERS"
            echo "ERRORS=$ERRORS" >> "$TEMP_COUNTERS"
            echo "DUPLICATES_FOUND=$DUPLICATES_FOUND" >> "$TEMP_COUNTERS"
            printf "DUPLICATE_FILES=(" >> "$TEMP_COUNTERS"
            printf "'%s' " "${DUPLICATE_FILES[@]}" >> "$TEMP_COUNTERS"
            printf ")\n" >> "$TEMP_COUNTERS"
        else
            ((SKIPPED++))
            mark_file_processed "$file"
            save_checkpoint
        fi
    fi
    
    echo ""
    
    # Mostra progresso ogni 50 file processati (solo in modalità normale)
    if [ "$DRY_RUN" = false ]; then
        total_processed=$((MOVED + SKIPPED + ERRORS + DUPLICATES_FOUND))
        if (( total_processed % 50 == 0 )) && (( total_processed > 0 )); then
            echo "--- PROGRESSO: $total_processed file processati ---"
            echo "    (Spostati: $MOVED | Saltati: $SKIPPED | Duplicati: $DUPLICATES_FOUND | Errori: $ERRORS)"
        fi
    fi
done < <(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) ! -name "*_DUP.*" -print0)

# Carica i contatori finali in modalità dry-run
if [ "$DRY_RUN" = true ] && [ -f "$TEMP_COUNTERS" ]; then
    source "$TEMP_COUNTERS"
fi

echo "----------------------------------------"

# Report finale
if [ "$DRY_RUN" = true ]; then
    echo "=== REPORT DRY-RUN COMPLETATO ==="
    echo ""
    echo "RIEPILOGO SIMULAZIONE:"
    echo "- File che verrebbero spostati: $MOVED"
    echo "- File che verrebbero saltati: $SKIPPED"
    echo "- File duplicati che verrebbero rinominati: $DUPLICATES_FOUND"
    echo "- Errori che si verificherebbero: $ERRORS"
    echo "- Totale file che verrebbero processati: $((MOVED + SKIPPED + DUPLICATES_FOUND + ERRORS))"
    
    if [ ${#DUPLICATE_FILES[@]} -gt 0 ]; then
        echo ""
        echo "FILE DUPLICATI CHE VERREBBERO RINOMINATI:"
        for dup_file in "${DUPLICATE_FILES[@]}"; do
            echo "  • $dup_file"
        done
    fi
    
    echo ""
    echo "STRUTTURA DIRECTORY CHE VERREBBE CREATA:"
    
    # Simula la struttura delle directory che verrebbero create
    temp_structure="/tmp/dry_run_structure_$"
    find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) ! -name "*_DUP.*" | while read -r file; do
        filename=$(basename "$file")
        
        # Ripeti la logica di estrazione data (versione semplificata)
        year=""
        month=""
        
        if [[ $filename =~ ([^0-9]*)([0-9]{4})[-_]?([0-9]{2})[-_]?([0-9]{2})(.*)$ ]]; then
            year="${BASH_REMATCH[2]}"
            month="${BASH_REMATCH[3]}"
        elif [[ $filename =~ ([^0-9]*)([0-9]{1,2})[-_/]([0-9]{1,2})[-_/]([0-9]{4})(.*)$ ]]; then
            potential_year="${BASH_REMATCH[4]}"
            potential_month="${BASH_REMATCH[3]}"
            potential_month=$((10#$potential_month))
            if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
                year="$potential_year"
                month=$(printf "%02d" $potential_month)
            else
                potential_month="${BASH_REMATCH[2]}"
                potential_month=$((10#$potential_month))
                if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
                    year="$potential_year"
                    month=$(printf "%02d" $potential_month)
                fi
            fi
        elif [[ $filename =~ ([^0-9]*)([0-9]{4})([0-9]{2})([0-9]{2})[^0-9]*(.*) ]]; then
            year="${BASH_REMATCH[2]}"
            month="${BASH_REMATCH[3]}"
        elif [[ $filename =~ ([^0-9]*)([0-9]{4})[^0-9]*([0-9]{2})[^0-9]*(.*) ]]; then
            potential_year="${BASH_REMATCH[2]}"
            potential_month="${BASH_REMATCH[3]}"
            potential_month=$((10#$potential_month))
            if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
                year="$potential_year"
                month=$(printf "%02d" $potential_month)
            fi
        fi
        
        if [ -n "$year" ] && [ -n "$month" ] && [ "$year" -ge 1990 ] && [ "$year" -le $(date +%Y) ]; then
            month_num=$((10#$month))
            if [ "$month_num" -ge 1 ] && [ "$month_num" -le 12 ]; then
                month_formatted=$(printf "%02d" $month_num)
                echo "$year/$month_formatted" >> "$temp_structure"
            fi
        fi
    done
    
    if [ -f "$temp_structure" ]; then
        sort "$temp_structure" | uniq | while read -r dir_path; do
            echo "$DEST_DIR/$dir_path/"
        done
        rm -f "$temp_structure"
    fi
    
    echo ""
    echo "Per eseguire realmente le modifiche, rilancia senza --dry-run:"
    echo "$0 \"$SOURCE_DIR\" \"$DEST_DIR\""
    
else
    echo "=========================================="
    echo "ORGANIZZAZIONE COMPLETATA CON SUCCESSO!"
    echo "=========================================="
    echo ""
    echo "STATISTICHE FINALI:"
    echo "- File spostati con successo: $MOVED"
    echo "- File saltati (data non valida o già posizionati): $SKIPPED" 
    echo "- File duplicati trovati e rinominati: $DUPLICATES_FOUND"
    echo "- Errori verificatisi: $ERRORS"
    echo "- Totale file processati: $((MOVED + SKIPPED + ERRORS + DUPLICATES_FOUND))"
    
    # Calcola percentuali se ci sono file processati
    total_files=$((MOVED + SKIPPED + ERRORS + DUPLICATES_FOUND))
    if [ "$total_files" -gt 0 ]; then
        moved_percent=$(( MOVED * 100 / total_files ))
        duplicates_percent=$(( DUPLICATES_FOUND * 100 / total_files ))
        echo ""
        echo "PERCENTUALI:"
        echo "- File spostati correttamente: ${moved_percent}%"
        if [ "$DUPLICATES_FOUND" -gt 0 ]; then
            echo "- File duplicati trovati: ${duplicates_percent}%"
        fi
    fi
    
    if [ ${#DUPLICATE_FILES[@]} -gt 0 ]; then
        echo ""
        echo "📋 DETTAGLIO FILE DUPLICATI RINOMINATI ($DUPLICATES_FOUND totali):"
        for dup_file in "${DUPLICATE_FILES[@]}"; do
            echo "  • $dup_file"
        done
        echo ""
        echo "NOTA: I file duplicati sono rimasti nella directory sorgente"
        echo "      con il suffisso _DUP per evitare perdite di dati"
    fi
    
    if [ "$ERRORS" -gt 0 ]; then
        echo ""
        echo "⚠️  ATTENZIONE: Si sono verificati $ERRORS errori durante l'operazione"
        echo "   Controlla i messaggi sopra per i dettagli"
    fi
    
    if [ "$MOVED" -eq 0 ] && [ "$DUPLICATES_FOUND" -eq 0 ]; then
        echo ""
        echo "ℹ️  Nessun file è stato spostato. Possibili cause:"
        echo "   • Tutti i file hanno date non riconoscibili"
        echo "   • Tutti i file sono già nella destinazione corretta"
        echo "   • La directory sorgente non contiene file multimediali"
        echo "   • Tutti i file multimediali sono già stati rinominati con _DUP"
    fi
    
    # Mostra riepilogo sottodirectory processate
    if [ "$MOVED" -gt 0 ] || [ "$DUPLICATES_FOUND" -gt 0 ]; then
        echo ""
        echo "📁 RIEPILOGO DIRECTORY PROCESSATE:"
        find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) ! -name "*_DUP.*" -printf '%h\n' | sort | uniq -c | sort -nr | head -10 | while read count dir; do
            relative_dir="${dir#$SOURCE_DIR}"
            [ -z "$relative_dir" ] && relative_dir="/"
            echo "  $count file da: $relative_dir"
        done
    fi
    
    # Pulizia file di checkpoint al completamento
    if [ -f "$CHECKPOINT_FILE" ]; then
        rm -f "$CHECKPOINT_FILE"
    fi
    if [ -f "$PROCESSED_FILES_LOG" ]; then
        rm -f "$PROCESSED_FILES_LOG"
    fi
    echo ""
    echo "🎉 File di checkpoint puliti - operazione completata!"
fi

# Pulizia file temporanei
if [ "$DRY_RUN" = true ] && [ -f "$TEMP_COUNTERS" ]; then
    rm -f "$TEMP_COUNTERS"
fi

# Rimuovi il trap alla fine
trap - INT TERM