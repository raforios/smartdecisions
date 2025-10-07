#!/bin/bash

# setup_api_gateway.sh: Crea un API Gateway HTTP (V2) dedicado para CADA microservicio.
# Utiliza la opción --target para obtener la URL más limpia y sin Stage,
# replicando la funcionalidad de build_and_deploy_v1.sh.

set -e
set -o pipefail

# --- 1. CONFIGURACIÓN Y UTILIDADES ---

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
}

# Función para obtener el ARN de la Lambda
get_lambda_arn() {
    aws lambda get-function --function-name "$1" --query 'Configuration.FunctionArn' --output text --region "$REGION" --profile "$AWS_PROFILE" 2>/dev/null
}

# Función PRINCIPAL para crear y configurar UN SOLO API Gateway HTTP (V2)
setup_single_http_api() {
    local FUNCTION_NAME=$1
    # Usaremos el nombre de la función como nombre de la API
    local API_NAME="${PROJECT_TAG}-API-HTTP-${FUNCTION_NAME}" 
    local API_ENDPOINT_URL=""
    local API_ID=""
    
    log_section "CONFIGURANDO API GATEWAY HTTP (V2) PARA: $FUNCTION_NAME"

    # 1. Obtener IDs
    ACCOUNT_ID=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --query 'Account' --output text --region "$REGION")
    LAMBDA_ARN=$(get_lambda_arn "$FUNCTION_NAME")

    if [ -z "$LAMBDA_ARN" ]; then
        echo "⛔️ Error: Lambda '$FUNCTION_NAME' no encontrada. Omitiendo la configuración de la API."
        return 1
    fi
    
    LAMBDA_ARN_TARGET="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"

    # 2. VERIFICAR/DESTRUIR API existente (Para idempotencia y limpieza)
    API_ID=$(aws apigatewayv2 get-apis --region "$REGION" --profile "$AWS_PROFILE" \
        --query "Items[?Name=='$API_NAME'].ApiId" --output text 2>/dev/null || true)

    if [ -n "$API_ID" ]; then
        echo "   -> API Gateway HTTP existente (ID: $API_ID). Eliminando para recrear con la configuración correcta..."
        aws apigatewayv2 delete-api --api-id "$API_ID" --region "$REGION" --profile "$AWS_PROFILE" || true
        # Esperar un momento para la eliminación
        sleep 5
        API_ID=""
    fi

    # 3. CREAR NUEVA API GATEWAY HTTP CON TARGET DIRECTO (MÉTODO LIMPIO)
    echo "   -> Creando nueva API Gateway HTTP con target directo a Lambda..."
    API_ID=$(aws apigatewayv2 create-api \
        --name "$API_NAME" \
        --protocol-type HTTP \
        --target "$LAMBDA_ARN_TARGET" \
        --cors-configuration "AllowOrigins=[\"*\"],AllowMethods=[\"GET\",\"POST\",\"OPTIONS\",\"PUT\",\"DELETE\"],AllowHeaders=[\"*\"],MaxAge=86400" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" \
        --query 'ApiId' --output text) || { echo "Error: Falló la creación de la API Gateway HTTP."; exit 1; }
    
    echo "   -> API Gateway HTTP creada con ID: $API_ID."

    # 4. CONFIGURAR PERMISO DE INVOCACIÓN DE LAMBDA
    # El permiso es el mismo que en tu script build_and_deploy_v1.sh
    STATEMENT_ID="apigateway-v2-invoke-$FUNCTION_NAME"
    SOURCE_ARN="arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*"

    # Eliminar permiso anterior para idempotencia
    aws lambda remove-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "$STATEMENT_ID" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" 2>/dev/null || true 

    # Añadir permiso
    aws lambda add-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "$STATEMENT_ID" \
        --action "lambda:InvokeFunction" \
        --principal "apigateway.amazonaws.com" \
        --source-arn "$SOURCE_ARN" \
        --profile "$AWS_PROFILE" \
        --region "$REGION" || { echo "Error: Falló al añadir el permiso de invocación a Lambda."; exit 1; }

    echo "   -> Permiso de invocación configurado con éxito."

    # 5. IMPRIMIR URL FINAL (LIMPIA)
    # AWS HTTP API con --target usa el stage por defecto ($default) que no aparece en la URL.
    API_ENDPOINT_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/"
    
    echo "=========================================================================================================="
    echo "✅ API GATEWAY HTTP (V2) CONFIGURADA EXITOSAMENTE."
    echo "URL de la API para $FUNCTION_NAME:"
    echo "$API_ENDPOINT_URL"
    echo "Ejemplo de uso de Swagger:"
    echo "-> ${API_ENDPOINT_URL}docs"
    echo "=========================================================================================================="
    
    return 0
}

# --- LÓGICA PRINCIPAL ---
log_section "INICIANDO CONFIGURACIÓN DE API GATEWAYS HTTP (V2) INDIVIDUALES"

# Dividir la lista de microservicios (ignorando el path de routing)
IFS=',' read -r -a SERVICES_ARRAY <<< "$MICROSERVICES_LIST"

for SERVICE_PAIR in "${SERVICES_ARRAY[@]}"; do
    # Extraer solo el nombre de la función (ignorar el path y el prefijo de la ruta)
    FUNCTION_NAME=$(echo "$SERVICE_PAIR" | cut -d':' -f1 | xargs)
    
    # Llamar a la función de despliegue para el servicio individual
    setup_single_http_api "$FUNCTION_NAME"
done

log_section "CONFIGURACIÓN DE TODOS LOS API GATEWAYS INDIVIDUALES COMPLETADA"
