#!/bin/bash

# Script per testare il riconoscimento delle date nei nomi file
# Uso: ./test_patterns.sh /path/to/directory [--dry-run]

SOURCE_DIR=""
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
            else
                echo "Errore: Troppi parametri"
                echo "Uso: $0 <directory_da_testare> [--dry-run]"
                exit 1
            fi
            shift
            ;;
    esac
done

if [ -z "$SOURCE_DIR" ]; then
    echo "Uso: $0 <directory_da_testare> [--dry-run]"
    echo ""
    echo "Opzioni:"
    echo "  --dry-run    Mostra solo statistiche senza elencare ogni file"
    exit 1
fi

if [ ! -d "$SOURCE_DIR" ]; then
    echo "Errore: Directory non trovata: $SOURCE_DIR"
    exit 1
fi

echo "Test riconoscimento date per i file in: $SOURCE_DIR"
echo "Scansione ricorsiva di tutte le sottodirectory..."
echo "Esclusione file con pattern *_DUP.*"
echo "========================================================"

# Funzione per estrarre data dal nome file (identica a organize_files.sh)
extract_date() {
    local filename="$1"
    local year=""
    local month=""
    
    if [ "$DRY_RUN" = false ]; then
        echo "Testando: $filename"
    fi
    
    # Formato: [prefisso_]YYYY-MM-DD[_suffisso] o [prefisso_]YYYY_MM_DD[_suffisso] o [prefisso_]YYYYMMDD[_suffisso]
    if [[ $filename =~ ([^0-9]*)([0-9]{4})[-_]?([0-9]{2})[-_]?([0-9]{2})(.*)$ ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        if [ "$DRY_RUN" = false ]; then
            echo "  ✓ Pattern YYYY-MM-DD trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[4]}')"
        fi
    # Formato: [prefisso_]DD-MM-YYYY[_suffisso] o [prefisso_]DD_MM_YYYY[_suffisso] o [prefisso_]DD/MM/YYYY[_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{1,2})[-_/]([0-9]{1,2})[-_/]([0-9]{4})(.*)$ ]]; then
        potential_year="${BASH_REMATCH[4]}"
        potential_month="${BASH_REMATCH[3]}"
        # Rimuovi zeri iniziali e assicurati che il mese sia valido (01-12)
        potential_month=$((10#$potential_month))
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            if [ "$DRY_RUN" = false ]; then
                echo "  ✓ Pattern DD-MM-YYYY trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
            fi
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
            if [ "$DRY_RUN" = false ]; then
                echo "  ✓ Pattern MM-DD-YYYY trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
            fi
        else
            year=""
            month=""
        fi
    # Formato con timestamp: [prefisso_]YYYY[MM[DD[_HHMMSS]]][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})([0-9]{2})([0-9]{2})[^0-9]*(.*) ]]; then
        year="${BASH_REMATCH[2]}"
        month="${BASH_REMATCH[3]}"
        if [ "$DRY_RUN" = false ]; then
            echo "  ✓ Pattern YYYYMMDD trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[5]}')"
        fi
    # Formato ISO con prefisso/suffisso: [prefisso_]YYYY[MM][_suffisso]
    elif [[ $filename =~ ([^0-9]*)([0-9]{4})[^0-9]*([0-9]{2})[^0-9]*(.*) ]]; then
        potential_year="${BASH_REMATCH[2]}"
        potential_month="${BASH_REMATCH[3]}"
        # Rimuovi zeri iniziali e valida il mese
        potential_month=$((10#$potential_month))
        if [ "$potential_month" -ge 1 ] && [ "$potential_month" -le 12 ]; then
            year="$potential_year"
            month=$(printf "%02d" $potential_month)
            if [ "$DRY_RUN" = false ]; then
                echo "  ✓ Pattern YYYY-MM trovato: $year-$month (prefisso:'${BASH_REMATCH[1]}', suffisso:'${BASH_REMATCH[4]}')"
            fi
        fi
    fi
    
    # Simulazione fallback per metadati (come in organize_files.sh)
    if [ -z "$year" ] || [ -z "$month" ]; then
        if [ "$DRY_RUN" = false ]; then
            echo "  Proverei a estrarre data da metadati EXIF o data modifica file"
        fi
        # In caso di fallback, usa data corrente per test
        if [ -z "$year" ] || [ -z "$month" ]; then
            year=$(date +%Y)
            month=$(date +%m)
            if [ "$DRY_RUN" = false ]; then
                echo "  Userei data di modifica: $year-$month"
            fi
        fi
    fi
    
    # Validazione finale (identica a organize_files.sh)
    if [ -n "$year" ] && [ -n "$month" ] && [ "$year" -ge 1990 ] && [ "$year" -le $(date +%Y) ]; then
        # Rimuovi zeri iniziali dal mese per evitare problemi con printf octal
        month_num=$((10#$month))
        if [ "$month_num" -ge 1 ] && [ "$month_num" -le 12 ]; then
            month_formatted=$(printf "%02d" $month_num)
            if [ "$DRY_RUN" = false ]; then
                echo "  → Destinazione: $year/$month_formatted/"
            fi
            return 0
        fi
    fi
    
    if [ "$DRY_RUN" = false ]; then
        echo "  ✗ Data non valida estratta: $year-$month"
    fi
    return 1
}

# Contatori
total_files=0
recognized_files=0
unrecognized_files=0

# Array per tenere traccia dei file non riconosciuti
declare -a unrecognized_list

# Test su tutti i file multimediali (stessi tipi di organize_files.sh)
while IFS= read -r -d '' file; do
    filename=$(basename "$file")
    ((total_files++))
    
    if [ "$DRY_RUN" = false ]; then
        if extract_date "$filename"; then
            ((recognized_files++))
        else
            ((unrecognized_files++))
            unrecognized_list+=("$filename")
        fi
        echo ""
    else
        # In modalità dry-run, solo conta senza output dettagliato
        if extract_date "$filename" >/dev/null 2>&1; then
            ((recognized_files++))
        else
            ((unrecognized_files++))
            unrecognized_list+=("$filename")
        fi
    fi
        done < <(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) ! -name "*_DUP.*" -print0)

echo "========================================================"
echo "RIEPILOGO:"
echo "File totali testati: $total_files"
echo "File con data riconosciuta: $recognized_files"
echo "File senza data riconosciuta: $unrecognized_files"

# Calcola percentuali
if [ "$total_files" -gt 0 ]; then
    recognized_percent=$((recognized_files * 100 / total_files))
    unrecognized_percent=$((unrecognized_files * 100 / total_files))
    echo "Percentuale riconoscimento: ${recognized_percent}%"
    echo "Percentuale non riconosciuti: ${unrecognized_percent}%"
fi

# Mostra file non riconosciuti
if [ "$unrecognized_files" -gt 0 ]; then
    echo ""
    echo "FILE NON RICONOSCIUTI:"
    echo "----------------------------------------"
    for unrecognized_file in "${unrecognized_list[@]}"; do
        echo "✗ $unrecognized_file"
    done
    echo ""
    echo "SUGGERIMENTI per migliorare il riconoscimento:"
    echo "• Verifica che le date siano in formato YYYY-MM-DD, DD-MM-YYYY, o YYYYMMDD"
    echo "• I file senza date nel nome useranno i metadati EXIF o la data di modifica"
    echo "• Considera di rinominare file con pattern irregolari"
    echo "• I file *_DUP.* vengono automaticamente esclusi dall'elaborazione"
fi

# Mostra preview struttura directory (solo in modalità normale)
if [ "$DRY_RUN" = false ] && [ "$recognized_files" -gt 0 ]; then
    echo ""
    echo "ANTEPRIMA STRUTTURA DIRECTORY:"
    echo "----------------------------------------"
    
    # Crea una lista temporanea delle directory che verrebbero create
    temp_dirs=$(mktemp)
    
    while IFS= read -r -d '' file; do
        filename=$(basename "$file")
        year=""
        month=""
        
        # Replica la logica di estrazione (versione semplificata)
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
                echo "$year/$month_formatted" >> "$temp_dirs"
            fi
        fi
    done < <(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" -o -iname "*.bmp" -o -iname "*.tiff" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" -o -iname "*.mkv" -o -iname "*.wmv" -o -iname "*.mp3" -o -iname "*.wav" -o -iname "*.flac" \) -print0)
    
    if [ -s "$temp_dirs" ]; then
        sort "$temp_dirs" | uniq -c | sort -nr | head -20 | while read count dir_path; do
            printf "%-20s (%d file%s)\n" "$dir_path/" "$count" "$([ $count -gt 1 ] && echo 's' || echo '')"
        done
        
        total_dirs=$(sort "$temp_dirs" | uniq | wc -l)
        if [ "$total_dirs" -gt 20 ]; then
            echo "... e altre $((total_dirs - 20)) directory"
        fi
    fi
    
    rm -f "$temp_dirs"
fi

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