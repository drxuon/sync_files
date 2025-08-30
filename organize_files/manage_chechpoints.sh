#!/bin/bash

# Script per gestire i checkpoint di organize_files.sh
# Uso: ./manage_checkpoints.sh [list|clean|info]

CHECKPOINT_DIR="/tmp"
CHECKPOINT_PATTERN="organize_files_checkpoint_*"
PROCESSED_PATTERN="organize_files_processed_*"

case "$1" in
    "list"|"l")
        echo "CHECKPOINT ATTIVI:"
        echo "=================="
        found=false
        
        for checkpoint in $CHECKPOINT_DIR/$CHECKPOINT_PATTERN; do
            if [ -f "$checkpoint" ]; then
                found=true
                pid=$(basename "$checkpoint" | sed 's/organize_files_checkpoint_//')
                echo "📁 Checkpoint PID: $pid"
                echo "   File: $checkpoint"
                
                if [ -f "${CHECKPOINT_DIR}/organize_files_processed_${pid}" ]; then
                    processed_count=$(wc -l < "${CHECKPOINT_DIR}/organize_files_processed_${pid}")
                    echo "   File processati: $processed_count"
                fi
                
                if [ -r "$checkpoint" ]; then
                    source "$checkpoint" 2>/dev/null
                    echo "   Statistiche: $MOVED spostati, $DUPLICATES_FOUND duplicati, $ERRORS errori"
                fi
                echo ""
            fi
        done
        
        if [ "$found" = false ]; then
            echo "Nessun checkpoint trovato"
        fi
        ;;
        
    "clean"|"c")
        echo "PULIZIA CHECKPOINT..."
        echo "===================="
        removed=0
        
        for checkpoint in $CHECKPOINT_DIR/$CHECKPOINT_PATTERN; do
            if [ -f "$checkpoint" ]; then
                echo "Rimozione: $checkpoint"
                rm -f "$checkpoint"
                ((removed++))
            fi
        done
        
        for processed in $CHECKPOINT_DIR/$PROCESSED_PATTERN; do
            if [ -f "$processed" ]; then
                echo "Rimozione: $processed"
                rm -f "$processed"
            fi
        done
        
        echo "Rimossi $removed checkpoint"
        echo "✅ Pulizia completata"
        ;;
        
    "info"|"i")
        if [ $# -eq 2 ]; then
            checkpoint_file="$CHECKPOINT_DIR/organize_files_checkpoint_$2"
            processed_file="$CHECKPOINT_DIR/organize_files_processed_$2"
            
            if [ -f "$checkpoint_file" ]; then
                echo "DETTAGLI CHECKPOINT PID: $2"
                echo "========================="
                echo "File checkpoint: $checkpoint_file"
                echo "File processati: $processed_file"
                echo ""
                
                if [ -r "$checkpoint_file" ]; then
                    echo "STATISTICHE:"
                    source "$checkpoint_file"
                    echo "- File spostati: $MOVED"
                    echo "- File saltati: $SKIPPED"
                    echo "- Duplicati: $DUPLICATES_FOUND" 
                    echo "- Errori: $ERRORS"
                    
                    if [ ${#DUPLICATE_FILES[@]} -gt 0 ]; then
                        echo ""
                        echo "FILE DUPLICATI:"
                        for dup_file in "${DUPLICATE_FILES[@]}"; do
                            echo "  • $dup_file"
                        done
                    fi
                fi
                
                if [ -f "$processed_file" ]; then
                    echo ""
                    echo "FILE PROCESSATI: $(wc -l < "$processed_file")"
                    echo "Ultimi 10 file processati:"
                    tail -10 "$processed_file" | while read file; do
                        echo "  • $(basename "$file")"
                    done
                fi
            else
                echo "❌ Checkpoint PID $2 non trovato"
            fi
        else
            echo "Uso: $0 info <PID>"
            echo "Per ottenere il PID, usa: $0 list"
        fi
        ;;
        
    "help"|"h"|*)
        echo "GESTORE CHECKPOINT ORGANIZE_FILES"
        echo "================================="
        echo ""
        echo "Uso: $0 <comando> [opzioni]"
        echo ""
        echo "Comandi disponibili:"
        echo "  list, l           Elenca tutti i checkpoint attivi"
        echo "  clean, c          Rimuove tutti i checkpoint (ricomincia da capo)"
        echo "  info, i <PID>     Mostra dettagli di un checkpoint specifico"
        echo "  help, h           Mostra questo messaggio"
        echo ""
        echo "Esempi:"
        echo "  $0 list                    # Elenca checkpoint"
        echo "  $0 clean                   # Pulisce tutto"
        echo "  $0 info 12345              # Dettagli checkpoint PID 12345"
        echo ""
        echo "NOTA: I checkpoint permettono di riprendere organize_files.sh"
        echo "      dal punto di interruzione senza riprocessare i file già gestiti."
        ;;
esac