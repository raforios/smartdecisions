#!/bin/bash

# Script de emergencia para actualizar variables de entorno de Lambda
# Corregido para máxima compatibilidad de shell (eliminando 'declare -A').

set -e
set -o pipefail

# --- 1. CONFIGURACIÓN DE TU ENTORNO ---
REGION="us-east-1"  # Ajusta a tu región
AWS_PROFILE="deploy_binaria" # Ajusta a tu perfil
CUSTOM_DOMAIN_BASE="https://api.binaria.app"
# --- 2. FUNCIONES DE CONSULTA DE DATOS (Reemplazo de Arrays Asociativos) ---

# Función para obtener la URL de un microservicio
get_api_url() {
    case "$1" in
        "binaria-file-handler-service") echo "${CUSTOM_DOMAIN_BASE}/files" ;;
        "binaria-events-handler-service") echo "${CUSTOM_DOMAIN_BASE}/events" ;;
        "binaria-forms-handler-service") echo "${CUSTOM_DOMAIN_BASE}/forms" ;;
        "binaria-localization-handler-service") echo "${CUSTOM_DOMAIN_BASE}/localization" ;;
        "binaria-planning-handler-service") echo "${CUSTOM_DOMAIN_BASE}/planning" ;;
        *) echo "" ;; # URL no encontrada
    esac
}

# Función para obtener la cadena de dependencias de un microservicio
get_dependencies_string() {
    case "$1" in
        "binaria-localization-handler-service") echo "FILES_SERVICE_URL:binaria-file-handler-service,EVENTS_SERVICE_URL:binaria-events-handler-service" ;;
        "binaria-forms-handler-service") echo "FILES_SERVICE_URL:binaria-file-handler-service,EVENTS_SERVICE_URL:binaria-events-handler-service,PLANNING_SERVICE_URL:binaria-planning-handler-service,LOCALIZATION_SERVICE_URL:binaria-localization-handler-service" ;;
        "binaria-planning-handler-service") echo "FILES_SERVICE_URL:binaria-file-handler-service,EVENTS_SERVICE_URL:binaria-events-handler-service" ;;
        *) echo "" ;; # Sin dependencias
    esac
}

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
}

# Función para actualizar las variables de entorno de una sola Lambda
update_lambda_env() {
    local LAMBDA_NAME=$1
    local DEPENDENCIES_STRING=$2
    local ORIGINAL_ENV_VARS=""
    local NEW_ENV_VARS=""
    local FINAL_ENV_JSON=""
    
    log_section "ACTUALIZANDO ENV PARA: $LAMBDA_NAME"

    # 1. Obtener variables de entorno originales (JSON del objeto de variables K:V)
    ORIGINAL_ENV_VARS=$(aws lambda get-function-configuration \
        --function-name "$LAMBDA_NAME" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" \
        --query 'Environment.Variables' \
        --output json)

    # 2. Inicializar el JSON de actualización con las variables originales
    NEW_ENV_VARS=$(echo "$ORIGINAL_ENV_VARS" | jq '.')

    IFS=',' read -r -a DEPS <<< "$DEPENDENCIES_STRING"
    
    for DEP in "${DEPS[@]}"; do
        IFS=':' read -r ENV_VAR_NAME TARGET_SERVICE <<< "$DEP"
        
        TARGET_URL=$(get_api_url "$TARGET_SERVICE")

        if [ -z "$TARGET_URL" ]; then
            echo "⛔️ Error: URL para $TARGET_SERVICE no encontrada. Saltando."
            continue
        fi

        echo "   -> Estableciendo $ENV_VAR_NAME como $TARGET_URL"
        
        # Agrega la nueva variable al JSON
        NEW_ENV_VARS=$(echo "$NEW_ENV_VARS" | jq --arg key "$ENV_VAR_NAME" --arg val "$TARGET_URL" '. + {($key): $val}')
    done

    # 3. Aplicar las variables de entorno
    # 💥 LA CORRECCIÓN: Creamos la estructura JSON COMPLETA y COMPACTA que el CLI espera: 
    # '{"Variables": { "DB_DIALECT": "...", "FILES_SERVICE_URL": "...", ... }}'
    FINAL_ENV_JSON=$(echo "$NEW_ENV_VARS" | jq -c '{"Variables": .}')

    # 4. Aplicar la configuración: Usamos el JSON completo como argumento
    aws lambda update-function-configuration \
        --function-name "$LAMBDA_NAME" \
        --environment "$FINAL_ENV_JSON" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" > /dev/null
        
    echo "   -> Variables de entorno actualizadas exitosamente. $LAMBDA_NAME está listo."
}


# --- LÓGICA PRINCIPAL ---

# Lista de servicios a actualizar (los que tienen dependencias)
SERVICE_LIST_TO_UPDATE="binaria-localization-handler-service binaria-forms-handler-service binaria-planning-handler-service"

log_section "INICIANDO PROCESO DE ACTUALIZACIÓN DE URLS"

for SERVICE_NAME in $SERVICE_LIST_TO_UPDATE; do
    DEPENDENCIES_STRING=$(get_dependencies_string "$SERVICE_NAME")
    if [ -n "$DEPENDENCIES_STRING" ]; then
        update_lambda_env "$SERVICE_NAME" "$DEPENDENCIES_STRING"
    fi
done

log_section "PROCESO DE ACTUALIZACIÓN DE URLS COMPLETADO"
echo "Las Lambdas dependientes ahora tienen las nuevas URLs de sus compañeros."
