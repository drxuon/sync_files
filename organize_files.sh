#!/bin/bash

# Script per organizzare file multimediali in struttura anno/mese
# Uso: ./organize_files.sh /path/to/source /path/to/destination

SOURCE_DIR="$1"
DEST_DIR="$2"

# Controlla che siano stati forniti i parametri
if [ $# -ne 2 ]; then
    echo "Uso: $0 <directory_sorgente> <directory_destinazione>"
    exit 1
fi

# Controlla che le directory esistano
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Errore: Directory sorgente non trovata: $SOURCE_DIR"
    exit 1
fi

# Crea la directory destinazione se non esiste
mkdir -p "$DEST_DIR"

# Contatori per statistiche
MOVED=0
SKIPPED=0
ERRORS=0

echo "Inizio organizzazione file da $SOURCE_DIR a $DEST_DIR"
echo "----------------------------------------"

# Trova tutti i file multimediali
find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) | while read -r file; do
    
    filename=$(basename "$file")
    echo "Processando: $filename"
    
    # Estrai data dal nome file - diversi formati possibili
    year=""
    month=""
    
    # Formato: YYYY-MM-DD o YYYY_MM_DD o YYYYMMDD
    if [[ $filename =~ ([0-9]{4})[-_]?([0-9]{2})[-_]?([0-9]{2}) ]]; then
        year="${BASH_REMATCH[1]}"
        month="${BASH_REMATCH[2]}"
    # Formato: DD-MM-YYYY o DD_MM_YYYY o DD/MM/YYYY
    elif [[ $filename =~ ([0-9]{2})[-_/]([0-9]{2})[-_/]([0-9]{4}) ]]; then
        year="${BASH_REMATCH[3]}"
        month="${BASH_REMATCH[2]}"
    # Formato: IMG_YYYYMMDD o VID_YYYYMMDD
    elif [[ $filename =~ (IMG|VID|DSC)_([0-9]{4})([0-9]{2})([0-9]{2}) ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
    # Formato: Screenshot_YYYY-MM-DD
    elif [[ $filename =~ Screenshot_([0-9]{4})-([0-9]{2})-([0-9]{2}) ]]; then
        year="${BASH_REMATCH[1]}"
        month="${BASH_REMATCH[2]}"
    fi
    
    # Se non riesci a estrarre la data, prova con i metadati del file
    if [ -z "$year" ] || [ -z "$month" ]; then
        # Usa exiftool se disponibile
        if command -v exiftool >/dev/null 2>&1; then
            date_taken=$(exiftool -DateTimeOriginal -d "%Y-%m" -T "$file" 2>/dev/null)
            if [ -n "$date_taken" ] && [ "$date_taken" != "-" ]; then
                year=$(echo "$date_taken" | cut -d'-' -f1)
                month=$(echo "$date_taken" | cut -d'-' -f2)
            fi
        fi
        
        # Se ancora non hai la data, usa la data di modifica del file
        if [ -z "$year" ] || [ -z "$month" ]; then
            file_date=$(stat -c %Y "$file")
            year=$(date -d "@$file_date" +%Y)
            month=$(date -d "@$file_date" +%m)
            echo "  Usando data di modifica: $year-$month"
        fi
    fi
    
    # Valida anno e mese
    if [ "$year" -ge 1990 ] && [ "$year" -le $(date +%Y) ] && [ "$month" -ge 1 ] && [ "$month" -le 12 ]; then
        # Crea directory destinazione
        dest_dir="$DEST_DIR/$year/$(printf "%02d" $month)"
        mkdir -p "$dest_dir"
        
        dest_file="$dest_dir/$filename"
        
        # Controlla se il file esiste già
        if [ -f "$dest_file" ]; then
            # Se i file sono identici, salta
            if cmp -s "$file" "$dest_file"; then
                echo "  File identico già esistente, saltato"
                ((SKIPPED++))
                continue
            else
                # Rinomina con suffisso numerico
                counter=1
                base_name="${filename%.*}"
                extension="${filename##*.}"
                while [ -f "$dest_dir/${base_name}_$counter.$extension" ]; do
                    ((counter++))
                done
                dest_file="$dest_dir/${base_name}_$counter.$extension"
                echo "  Rinominato in: ${base_name}_$counter.$extension"
            fi
        fi
        
        # Sposta il file
        if mv "$file" "$dest_file"; then
            echo "  Spostato in: $dest_dir/"
            ((MOVED++))
        else
            echo "  ERRORE nello spostamento"
            ((ERRORS++))
        fi
    else
        echo "  Data non valida estratta: $year-$month, saltato"
        ((SKIPPED++))
    fi
    
    echo ""
done

echo "----------------------------------------"
echo "Organizzazione completata!"
echo "File spostati: $MOVED"
echo "File saltati: $SKIPPED" 
echo "Errori: $ERRORS"