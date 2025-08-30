#!/bin/bash

# Script per testare il riconoscimento delle date nei nomi file
# Uso: ./test_patterns.sh /path/to/directory

SOURCE_DIR="$1"

if [ $# -ne 1 ]; then
    echo "Uso: $0 <directory_da_testare>"
    exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Errore: Directory non trovata: $SOURCE_DIR"
    exit 1
fi

echo "Test riconoscimento date per i file in: $SOURCE_DIR"
echo "========================================================"

# Funzione per estrarre data dal nome file
extract_date() {
    local filename="$1"
    local year=""
    local month=""
    
    echo "Testando: $filename"
    
    # Formato: [prefisso_]YYYY-MM-DD[_suffisso] o [prefisso_]YYYY_MM_DD[_suffisso] o [prefisso_]YYYYMMDD[_suffisso]
    if [[ $filename =~ ([^0-9]*)([0-9]{4})[-_]?([0-9]{2})[-_]?([0-9]{2})(.*)$ ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        echo "  ✓ Pattern YYYY-MM-DD trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[4]}')"
    # Formato: [prefisso_]DD-MM-YYYY[_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{1,2})[-_/]([0-9]{1,2})[-_/]([0-9]{4})(.*)$ ]]; then
        potential_year="${BASH_REMATCH[4]}"
        potential_month="${BASH_REMATCH[3]}"
        if [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            echo "  ✓ Pattern DD-MM-YYYY trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
        else
            # Prova formato americano MM-DD-YYYY
            potential_month="${BASH_REMATCH[2]}"
            if [ "$potential_month" -le 12 ]; then
                year="$potential_year"
                month=$(printf "%02d" $potential_month)
                echo "  ✓ Pattern MM-DD-YYYY trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
            fi
        fi
    # Formato con timestamp: [prefisso_]YYYY[MM[DD[_HHMMSS]]][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})([0-9]{2})([0-9]{2})[^0-9]*(.*) ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        echo "  ✓ Pattern YYYYMMDD trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
    # Formato ISO con prefisso/suffisso: [prefisso_]YYYY[MM][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})[^0-9]*([0-9]{2})[^0-9]*(.*) ]]; then
        potential_year="${BASH_REMATCH[2]}"
        potential_month="${BASH_REMATCH[3]}"
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            echo "  ✓ Pattern YYYY-MM trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[4]}')"
        fi
    fi
    
    # Validazione finale
    if [ -n "$year" ] && [ -n "$month" ] && [ "$year" -ge 1990 ] && [ "$year" -le $(date +%Y) ] && [ "$month" -ge 1 ] && [ "$month" -le 12 ]; then
        echo "  → Destinazione: $year/$(printf "%02d" $month)/"
        return 0
    else
        echo "  ✗ Nessun pattern di data valido trovato"
        return 1
    fi
}

# Contatori
total_files=0
recognized_files=0
unrecognized_files=0

# Test su tutti i file multimediali
find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) | while read -r file; do
    filename=$(basename "$file")
    ((total_files++))
    
    if extract_date "$filename"; then
        ((recognized_files++))
    else
        ((unrecognized_files++))
    fi
    
    echo ""
done

echo "========================================================"
echo "RIEPILOGO:"
echo "File totali testati: $total_files"
echo "File con data riconosciuta: $recognized_files"
echo "File senza data riconosciuta: $unrecognized_files"

# Esempi di pattern supportati
echo ""
echo "ESEMPI DI PATTERN SUPPORTATI:"
echo "• vacanza_2024-03-15_tramonto.jpg"
echo "• IMG_20240315_120000.jpg"
echo "• photo_15-03-2024_sera.png"
echo "• backup_03-15-2024.zip (formato USA)"
echo "• screenshot_2024_03_15_importante.png"
echo "• DSC_202403151200_finale.tiff"
echo "• video_2024-03_compleanno.mp4"