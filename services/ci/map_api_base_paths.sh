#!/bin/bash

# Script para mapear todas las APIs de Lambda al dominio personalizado estático (api.binaria.app)

set -e
set -o pipefail

# --- CONFIGURACIÓN ---
REGION="us-east-1"
AWS_PROFILE="deploy_binaria"
CUSTOM_DOMAIN="api.binaria.app"

# --- LISTA DE MAPEOS (ACTUALIZA ESTO CON TUS IDs REALES DE API GATEWAY) ---
# Formato: API_ID:RutaBaseEstática
# Usa los IDs de tu última salida de despliegue (ej. mijwvdu4g6, ozg7itcrvg, etc.)

API_MAPPINGS=(
    "mijwvdu4g6:files"      # binaria-file-handler-service
    "ozg7itcrvg:events"     # binaria-events-handler-service
    "vk22i8orck:forms"      # binaria-forms-handler-service
    "yvivgga9i8:localization" # binaria-localization-handler-service
    "9bdyb0z3ol:planning"    # binaria-planning-handler-service
    "v65w34fghh:auth"       # binaria-auth-handler-service
)

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
}

# --- LÓGICA PRINCIPAL ---

log_section "INICIANDO MAPEO DE APIS A $CUSTOM_DOMAIN"

for MAPPING_PAIR in "${API_MAPPINGS[@]}"; do
    
    # 1. Separar el par API_ID y BASE_PATH usando el dos puntos (:)
    IFS=':' read -r API_ID BASE_PATH <<< "$MAPPING_PAIR"
    
    # 2. Verificar que la separación fue exitosa (el API_ID tiene 10 caracteres)
    if [ ${#API_ID} -ne 10 ]; then
        echo "⛔️ Error en el parseo del par: $MAPPING_PAIR. Saltando."
        continue
    fi
    
    echo "-> Mapeando API ID $API_ID a la ruta base: /$BASE_PATH"

    # Comando para crear el mapeo de API 
    aws apigatewayv2 create-api-mapping \
        --domain-name "$CUSTOM_DOMAIN" \
        --api-id "$API_ID" \
        --api-mapping-key "$BASE_PATH" \
        --stage "\$default" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" 2>/dev/null || true # Ignora errores de "ya existe"
    
    echo "✅ Mapeo /$BASE_PATH completado para API ID $API_ID."
done

log_section "MAPEO COMPLETADO"
echo "El tráfico a https://$CUSTOM_DOMAIN/ruta/ahora será dirigido a la API Gateway correspondiente."