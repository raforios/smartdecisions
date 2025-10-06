#!/bin/bash

# 'setup_api_gateway.sh': Crea un único API Gateway REST y configura
# recursos e integraciones para todos los microservicios Lambda.
# 'Toda la configuración es cargada desde las variables de entorno.'

set -e
set -o pipefail

# --- Verificación de Variables (Cargadas por manage_infrastructure.sh) ---
: ${REGION:?"Error: REGION no está configurada."}
: ${API_NAME:?"Error: API_NAME no está configurada."}
: ${API_STAGE_NAME:?"Error: API_STAGE_NAME no está configurada."}
: ${MICROSERVICES_LIST:?"Error: MICROSERVICES_LIST no está configurada."}

# --- Configuración Derivada ---
API_SERVICE_ROLE_NAME="ApiGatewayLambdaInvocationRole" # Nombre fijo del rol de servicio
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text --region "$REGION")

# --- Mapeo Dinámico de Microservicios ---
IFS=',' read -r -a MS_ARRAY <<< "$MICROSERVICES_LIST"


# --- Funciones de Utilidad ---

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

get_lambda_arn() {
    local function_name="$1"
    # Usa la variable de entorno $REGION
    aws lambda get-function \
        --function-name "$function_name" \
        --query 'Configuration.FunctionArn' \
        --output text \
        --region "$REGION" 2>/dev/null
}

# --- Rol de IAM para Integración ---

manage_api_service_role() {
    log_section "ROL DE SERVICIO IAM PARA API GATEWAY"
    
    # 1. 'Verificar' si el rol existe
    API_SERVICE_ROLE_ARN=$(aws iam get-role --role-name "$API_SERVICE_ROLE_NAME" --query 'Role.Arn' --output text --region "$REGION" 2>/dev/null || true)
    
    if [ -z "$API_SERVICE_ROLE_ARN" ]; then
        echo "Creando 'Rol de Servicio API Gateway': $API_SERVICE_ROLE_NAME..."
        
        # 2. 'Crear' el trust policy JSON
        TRUST_POLICY_JSON=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "apigateway.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
)
        # 3. 'Crear' el rol
        API_SERVICE_ROLE_ARN=$(aws iam create-role \
            --role-name "$API_SERVICE_ROLE_NAME" \
            --assume-role-policy-document "$TRUST_POLICY_JSON" \
            --query 'Role.Arn' \
            --output text \
            --region "$REGION")

        # 4. 'Crear' el policy document para invocación
        INVOCATION_POLICY_NAME="ApiGatewayInvokeLambdasPolicy"
        INVOCATION_POLICY_DOCUMENT=$(cat <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "lambda:InvokeFunction",
            "Resource": "arn:aws:lambda:$REGION:$ACCOUNT_ID:function:*",
            "Effect": "Allow"
        }
    ]
}
EOF
)
        # 5. 'Crear' y adjuntar la política
        POLICY_ARN=$(aws iam create-policy \
            --policy-name "$INVOCATION_POLICY_NAME" \
            --policy-document "$INVOCATION_POLICY_DOCUMENT" \
            --query 'Policy.Arn' \
            --output text \
            --region "$REGION")
            
        aws iam attach-role-policy \
            --role-name "$API_SERVICE_ROLE_NAME" \
            --policy-arn "$POLICY_ARN" \
            --region "$REGION"
            
        echo "Esperando 10 segundos para la propagación del rol IAM..."
        sleep 10
        echo "Configuración de Rol IAM completa."
    else
        echo "Rol de Servicio API Gateway '$API_SERVICE_ROLE_NAME' ya existe."
    fi
    
    export API_SERVICE_ROLE_ARN
}

# --- Gestión de API Gateway ---

manage_api_gateway() {
    log_section "CREACIÓN DE API GATEWAY REST"
    
    # Verificar si API Gateway existe usando la variable $API_NAME
    API_ID=$(aws apigateway get-rest-apis \
        --query "items[?name=='$API_NAME'].id" \
        --output text \
        --region "$REGION" || true)

    if [ -z "$API_ID" ]; then
        echo "API Gateway '$API_NAME' no encontrado. Creando..."
        API_ID=$(aws apigateway create-rest-api \
            --name "$API_NAME" \
            --description "Single API Gateway for all Microservices" \
            --endpoint-configuration types=REGIONAL \
            --query 'id' \
            --output text \
            --region "$REGION")
        echo "API Gateway '$API_ID' creado."
    else
        echo "API Gateway '$API_NAME' ya existe con ID: $API_ID."
    fi
    
    # Obtener el Root Resource ID
    ROOT_RESOURCE_ID=$(aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --query 'items[?path==`/`].id' \
        --output text \
        --region "$REGION")
        
    export API_ID
    export ROOT_RESOURCE_ID
}

configure_microservice() {
    local function_name="$1"
    local api_path="$2" # e.g., /auth
    local resource_name="${api_path#/}" # e.g., auth

    log_section "CONFIGURANDO MICROSERVICIO: $resource_name ($function_name)"
    
    # 1. 'Obtener' Lambda ARN (Usa $REGION)
    local LAMBDA_ARN=$(get_lambda_arn "$function_name")
    if [ -z "$LAMBDA_ARN" ]; then
        echo "Error: Función Lambda '$function_name' no encontrada. Saltando configuración." >&2
        return 1
    fi
    
    local INTEGRATION_URI="arn:aws:apigateway:$REGION:lambda:path/2015-03-31/functions/$LAMBDA_ARN/invocations"

    # 2. 'Crear' Recurso (e.g., /auth, /files)
    RESOURCE_ID=$(aws apigateway get-resources \
        --rest-api-id "$API_ID" \
        --query "items[?path=='$api_path'].id" \
        --output text \
        --region "$REGION" || true)

    if [ -z "$RESOURCE_ID" ]; then
        echo "Creando recurso '$api_path'..."
        RESOURCE_ID=$(aws apigateway create-resource \
            --rest-api-id "$API_ID" \
            --parent-id "$ROOT_RESOURCE_ID" \
            --path-part "$resource_name" \
            --query 'id' \
            --output text \
            --region "$REGION")
        echo "Recurso '$RESOURCE_ID' creado."
    else
        echo "Recurso '$api_path' ya existe con ID: $RESOURCE_ID."
    fi

    # 3. 'Crear' Método (ANY)
    if ! aws apigateway get-method --rest-api-id "$API_ID" --resource-id "$RESOURCE_ID" --http-method ANY --region "$REGION" 2>/dev/null; then
        echo "Creando método ANY para el recurso '$resource_name'..."
        aws apigateway put-method \
            --rest-api-id "$API_ID" \
            --resource-id "$RESOURCE_ID" \
            --http-method ANY \
            --authorization-type NONE \
            --region "$REGION"
    else
        echo "Método ANY ya existe para el recurso '$resource_name'."
    fi

    # 4. 'Crear' Integración (Lambda Proxy)
    if ! aws apigateway get-integration --rest-api-id "$API_ID" --resource-id "$RESOURCE_ID" --http-method ANY --region "$REGION" 2>/dev/null; then
        echo "Creando Integración Lambda para el recurso '$resource_name'..."
        aws apigateway put-integration \
            --rest-api-id "$API_ID" \
            --resource-id "$RESOURCE_ID" \
            --http-method ANY \
            --type AWS_PROXY \
            --integration-http-method POST \
            --uri "$INTEGRATION_URI" \
            --credentials "$API_SERVICE_ROLE_ARN" \
            --region "$REGION"
    else
        echo "La integración ya existe para el recurso '$resource_name'."
    fi
    
    # 5. 'Otorgar' Permiso de Invocación a Lambda
    local statement_id="ApigwInvoke$function_name"
    local source_arn="arn:aws:execute-api:$REGION:$ACCOUNT_ID:$API_ID/*/*$api_path" # Source ARN para la ruta del recurso

    # Verificar si el permiso ya existe antes de añadirlo
    if ! aws lambda get-policy --function-name "$function_name" --region "$REGION" | grep -q "$statement_id"; then
        echo "Añadiendo permiso Lambda para que API Gateway pueda invocar '$function_name'..."
        aws lambda add-permission \
            --function-name "$function_name" \
            --statement-id "$statement_id" \
            --action lambda:InvokeFunction \
            --principal apigateway.amazonaws.com \
            --source-arn "$source_arn" \
            --region "$REGION"
    else
        echo "El permiso Lambda para API Gateway ya existe para '$function_name'."
    fi
}

deploy_api_stage() {
    log_section "DESPLIEGUE DE API GATEWAY"
    local STAGE_NAME="$API_STAGE_NAME" # Usa la variable parametrizada
    
    # Realizar el despliegue
    aws apigateway create-deployment \
        --rest-api-id "$API_ID" \
        --stage-name "$STAGE_NAME" \
        --description "Despliegue inicial de todos los microservicios" \
        --region "$REGION" > /dev/null
    
    API_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/$STAGE_NAME"
    
    echo "Despliegue a la etapa '$STAGE_NAME' completado con éxito."
    echo "--------------------------------------------------------------------------------"
    echo " 'URL ÚNICA DE API PARA TODOS LOS MICROSERVICIOS:' "
    echo " '$API_URL' "
    echo "--------------------------------------------------------------------------------"
    echo "Endpoints de Microservicios:"
    
    # MODIFICADO: Ahora itera sobre el array simple MS_ARRAY y parsea los valores.
    for entry in "${MS_ARRAY[@]}"; do
        IFS=':' read -r FUNC_NAME API_PATH <<< "$entry"
        echo " - MS $FUNC_NAME: $API_URL$API_PATH"
    done
}

# --- Flujo de Ejecución Principal ---
echo "Iniciando 'Configuración de API Gateway Único' para Microservicios..."

# 1. 'Crear' o verificar el Rol IAM para que API Gateway invoque a Lambdas
manage_api_service_role

# 2. 'Crear' o verificar el API Gateway REST
manage_api_gateway

# 3. 'Configurar' cada microservicio (Recurso, Método, Integración, Permiso)
# Iteramos sobre el array simple MS_ARRAY y parseamos en el bucle.
for entry in "${MS_ARRAY[@]}"; do
    IFS=':' read -r FUNC_NAME API_PATH <<< "$entry"
    configure_microservice "$FUNC_NAME" "$API_PATH"
done

# 4. 'Desplegar' la API
deploy_api_stage

log_section "CONFIGURACIÓN DE API GATEWAY ÚNICO FINALIZADA"
