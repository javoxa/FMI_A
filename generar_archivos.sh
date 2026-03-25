 
#!/bin/bash
# Script para generar un archivo con la estructura y el contenido de todos los archivos de texto/código del proyecto.
# Uso: ./generar_contenido.sh

OUTPUT="proyecto_FMIA_completo.txt"

# Limpiar archivo de salida
> "$OUTPUT"

# ============================================
# 1. MOSTRAR ÁRBOL DEL PROYECTO (excluyendo pesos y caché)
# ============================================
printf "### ESTRUCTURA DEL PROYECTO: proyecto_FMIA\n\n" >> "$OUTPUT"
tree -a -N --charset=ASCII \
  -I 'models|models--*|__pycache__|blobs|snapshots|*.safetensors|*.lock|*.bin|*.pt|*.pth|*.onnx|cache|finetuning' \
  >> "$OUTPUT"

printf "\n\n### CONTENIDO DE ARCHIVOS DEL PROYECTO\n\n" >> "$OUTPUT"

# ============================================
# 2. RECORRER ARCHIVOS DE INTERÉS Y VOLCAR SU CONTENIDO
# ============================================
# Busca archivos con extensiones de texto/código, excluyendo carpetas de modelos y binarios.
# Puedes ajustar las extensiones y exclusiones según necesites.
find . -type f \( \
        -name "*.py" -o \
        -name "*.txt" -o \
        -name "*.sql" -o \
        -name "*.json" -o \
        -name "*.md" -o \
        -name "*.sh" -o \
        -name "Dockerfile" -o \
        -name "*.yml" -o \
        -name "*.yaml" -o \
        -name "*.conf" -o \
        -name "*.cfg" -o \
        -name "*.ini" -o \
        -name "*.toml" -o \
        -name "*.html" -o \
        -name "*.css" -o \
        -name "*.js" \
    \) \
    ! -path "*/cache/*" \
    ! -path "*/finetuning/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.git/*" \
    ! -path "*/blobs/*" \
    ! -path "*/snapshots/*" \
    ! -name "*.safetensors" \
    ! -name "*.lock" \
    ! -name "*.bin" \
    ! -name "*.pt" \
    ! -name "*.pth" \
    ! -name "*.onnx" \
    -print0 | sort -z | while IFS= read -r -d '' archivo; do

        # Separador por archivo
        printf "\n########################################\n" >> "$OUTPUT"
        printf "### %s\n" "$archivo" >> "$OUTPUT"
        printf "########################################\n\n" >> "$OUTPUT"

        # Volcar contenido
        cat "$archivo" >> "$OUTPUT"
done

echo "✅ Archivo '$OUTPUT' generado con éxito."
