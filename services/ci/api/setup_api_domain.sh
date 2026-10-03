#!/bin/bash

# Publica todos los microservicios bajo un solo dominio: api.bearsoft.com.bo.
#
#   https://api.bearsoft.com.bo/v1/ingest/...      -> Lambda de INGEST
#   https://api.bearsoft.com.bo/v1/analytics/...   -> Lambda de ANALYTICS
#   ...
#
# DISEÑO: una sola puerta de entrada (API HTTP "bearsoft-gateway") con una ruta
# por servicio —ANY /v1/ingest/{proxy+} -> Lambda de INGEST, etc.— y el dominio
# mapeado ENTERO a ese API. Es el patrón recomendado para varios microservicios
# detrás de un dominio:
#   - El Lambda recibe la ruta completa (/v1/ingest/datasets) en el formato de
#     evento 2.0, así que el código de los servicios no cambia.
#   - Un mapeo por prefijo hacia un API por servicio recorta el prefijo, y en
#     2.0 ese prefijo se pierde: el servicio recibía /datasets y respondía 404.
#   - El CORS vive en un solo lugar: el gateway.
#
# Los API de cada servicio (los que crea build_and_deploy.sh) siguen existiendo
# y respondiendo en su URL execute-api; el gateway no los usa, invoca los
# Lambdas directamente.
#
# Sin ALB ni EC2 (eso era de BINARIA). El certificado de ACM, el dominio de API
# Gateway, el API y sus rutas no tienen costo: se paga sólo por llamada, igual
# que hoy.
#
# Idempotente: crea sólo lo que falta. Se puede correr las veces que haga falta.
#
# Códigos de salida: 0 todo listo · 3 certificado pendiente de validar ·
# 4 la prueba de humo no dio 401 (no cambiar URLs todavía).
#
# Pasos manuales (una sola vez, en Cloudflare):
#   1. La primera corrida pide el certificado e imprime un CNAME de validación.
#      Se agrega en Cloudflare (sin proxy) y se vuelve a correr cuando ACM lo
#      emita (unos minutos).
#   2. Con el certificado emitido, el script crea el dominio e imprime el
#      destino: se agrega el CNAME "api" -> ese destino en Cloudflare, SIN proxy
#      (nube gris): el certificado es el de AWS, no el de Cloudflare.

set -e
set -o pipefail

REGION="us-east-1"
PROFILE="deploy_ml"
DOMAIN="api.bearsoft.com.bo"
GATEWAY_NAME="bearsoft-gateway"
CORS_CONFIGURATION='AllowOrigins=["*"],AllowMethods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"],AllowHeaders=["*"],MaxAge=86400'

# Prefijo de ruta -> Lambda (el FUNCTION_NAME de su deploy.config).
# Los prefijos son los de las rutas de cada servicio; si un servicio agrega un
# prefijo nuevo (un APIRouter(prefix = '/v1/algo')), se agrega acá.
ROUTES=(
    # --- Base: los usa todo producto ---
    "v1/auth:auth-handler-service"
    "v1/users:auth-handler-service"
    "v1/events:events-handler-service"
    "v1/s3:file-handler-service"
    "v1/classification:ml-functions-handler-service"
    "v1/common:ml-functions-handler-service"
    "v1/prediction:ml-functions-handler-service"
    # --- SmartDecisions ---
    "v1/ingest:ingest-handler-service"
    "v1/analytics:analytics-handler-service"
    "v1/optimization:optimization-handler-service"
    "v1/quotes:quotes-handler-service"
    "v1/ai:ai-handler-service"
    "v1/mining-analysis:mining-handler-service"
    # --- SmartBilling ---
    "v1/billing:billing-handler-service"
)

aws_cli() {
    aws "$@" --region "$REGION" --profile "$PROFILE"
}

ACCOUNT_ID=$(aws_cli sts get-caller-identity --query Account --output text)

echo "=== 1. Certificado de $DOMAIN ==="
CERT_ARN=$(aws_cli acm list-certificates \
    --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" --output text)
if [ "$CERT_ARN" == "None" ] || [ -z "$CERT_ARN" ]; then
    CERT_ARN=$(aws_cli acm request-certificate --domain-name "$DOMAIN" \
        --validation-method DNS --query CertificateArn --output text)
    echo "Certificado pedido: $CERT_ARN"
    sleep 10
fi
CERT_STATUS=$(aws_cli acm describe-certificate --certificate-arn "$CERT_ARN" \
    --query Certificate.Status --output text)
if [ "$CERT_STATUS" != "ISSUED" ]; then
    echo "El certificado está en estado $CERT_STATUS. Agrega este CNAME en Cloudflare (sin proxy):"
    aws_cli acm describe-certificate --certificate-arn "$CERT_ARN" \
        --query "Certificate.DomainValidationOptions[0].ResourceRecord.[Name,Value]" --output text
    echo "Cuando ACM lo emita, vuelve a ejecutar este script."
    exit 3
fi
echo "Certificado emitido."

echo "=== 2. Dominio personalizado ==="
TARGET=$(aws_cli apigatewayv2 get-domain-names \
    --query "Items[?DomainName=='$DOMAIN'].DomainNameConfigurations[0].ApiGatewayDomainName | [0]" \
    --output text)
if [ "$TARGET" == "None" ] || [ -z "$TARGET" ]; then
    TARGET=$(aws_cli apigatewayv2 create-domain-name --domain-name "$DOMAIN" \
        --domain-name-configurations \
        "CertificateArn=$CERT_ARN,EndpointType=REGIONAL,SecurityPolicy=TLS_1_2" \
        --query "DomainNameConfigurations[0].ApiGatewayDomainName" --output text)
    echo "Dominio creado."
fi
echo "Destino para el CNAME 'api' en Cloudflare (sin proxy): $TARGET"

echo "=== 3. API $GATEWAY_NAME ==="
GATEWAY_ID=$(aws_cli apigatewayv2 get-apis --query "Items[?Name=='$GATEWAY_NAME'].ApiId | [0]" --output text)
if [ "$GATEWAY_ID" == "None" ] || [ -z "$GATEWAY_ID" ]; then
    GATEWAY_ID=$(aws_cli apigatewayv2 create-api --name "$GATEWAY_NAME" --protocol-type HTTP \
        --cors-configuration "$CORS_CONFIGURATION" --query ApiId --output text)
    echo "API creado: $GATEWAY_ID"
else
    aws_cli apigatewayv2 update-api --api-id "$GATEWAY_ID" \
        --cors-configuration "$CORS_CONFIGURATION" > /dev/null
    echo "API existente: $GATEWAY_ID (CORS reafirmado)."
fi
STAGE=$(aws_cli apigatewayv2 get-stages --api-id "$GATEWAY_ID" \
    --query "Items[?StageName=='\$default'].StageName | [0]" --output text)
if [ "$STAGE" == "None" ] || [ -z "$STAGE" ]; then
    aws_cli apigatewayv2 create-stage --api-id "$GATEWAY_ID" --stage-name '$default' \
        --auto-deploy > /dev/null
    echo "Etapa \$default creada (se publica sola con cada cambio)."
fi

echo "=== 4. Rutas por servicio ==="
INTEGRATIONS=$(aws_cli apigatewayv2 get-integrations --api-id "$GATEWAY_ID" \
    --query "Items[].[IntegrationUri,IntegrationId]" --output text)
EXISTING_ROUTES=$(aws_cli apigatewayv2 get-routes --api-id "$GATEWAY_ID" \
    --query "Items[].RouteKey" --output text | tr '\t' '\n')

for ENTRY in "${ROUTES[@]}"; do
    PREFIX="${ENTRY%%:*}"
    FUNCTION_NAME="${ENTRY##*:}"
    FUNCTION_ARN="arn:aws:lambda:$REGION:$ACCOUNT_ID:function:$FUNCTION_NAME"

    if ! aws_cli lambda get-function --function-name "$FUNCTION_NAME" > /dev/null 2>&1; then
        echo "  /$PREFIX: el Lambda '$FUNCTION_NAME' no existe todavía; se enruta cuando se despliegue."
        continue
    fi

    # Una integración por Lambda, compartida por todos sus prefijos.
    INTEGRATION_ID=$(echo "$INTEGRATIONS" | awk -v uri="$FUNCTION_ARN" '$1 == uri {print $2; exit}')
    if [ -z "$INTEGRATION_ID" ]; then
        INTEGRATION_ID=$(aws_cli apigatewayv2 create-integration --api-id "$GATEWAY_ID" \
            --integration-type AWS_PROXY --integration-uri "$FUNCTION_ARN" \
            --payload-format-version 2.0 --query IntegrationId --output text)
        INTEGRATIONS="$INTEGRATIONS"$'\n'"$FUNCTION_ARN"$'\t'"$INTEGRATION_ID"
    fi

    # El gateway necesita permiso para invocar el Lambda. Un permiso que ya
    # existe responde ResourceConflictException: no es un error.
    aws_cli lambda add-permission --function-name "$FUNCTION_NAME" \
        --statement-id "$GATEWAY_NAME-invoke" --action lambda:InvokeFunction \
        --principal apigateway.amazonaws.com \
        --source-arn "arn:aws:execute-api:$REGION:$ACCOUNT_ID:$GATEWAY_ID/*/*" \
        > /dev/null 2>&1 || true

    # La ruta exacta del prefijo y todo lo que cuelga de él.
    for ROUTE_KEY in "ANY /$PREFIX" "ANY /$PREFIX/{proxy+}"; do
        if echo "$EXISTING_ROUTES" | grep -qxF "$ROUTE_KEY"; then
            continue
        fi
        aws_cli apigatewayv2 create-route --api-id "$GATEWAY_ID" --route-key "$ROUTE_KEY" \
            --target "integrations/$INTEGRATION_ID" > /dev/null
    done
    echo "  /$PREFIX -> $FUNCTION_NAME"
done

echo "=== 5. Dominio -> $GATEWAY_NAME ==="
# El dominio entero apunta al gateway (sin clave de mapeo): la ruta llega
# completa. Cualquier mapeo anterior por prefijo se quita.
for ROW in $(aws_cli apigatewayv2 get-api-mappings --domain-name "$DOMAIN" \
        --query "Items[].[ApiMappingId,ApiId,ApiMappingKey]" --output text | tr '\t' '|'); do
    MAPPING_ID="${ROW%%|*}"
    REST="${ROW#*|}"
    MAPPED_API="${REST%%|*}"
    MAPPING_KEY="${REST#*|}"
    if [ "$MAPPED_API" != "$GATEWAY_ID" ] || { [ -n "$MAPPING_KEY" ] && [ "$MAPPING_KEY" != "None" ]; }; then
        aws_cli apigatewayv2 delete-api-mapping --domain-name "$DOMAIN" \
            --api-mapping-id "$MAPPING_ID"
        echo "  Mapeo anterior '$MAPPING_KEY' quitado."
    fi
done
CURRENT_MAPPING=$(aws_cli apigatewayv2 get-api-mappings --domain-name "$DOMAIN" \
    --query "Items[?ApiId=='$GATEWAY_ID'].ApiMappingId | [0]" --output text)
if [ "$CURRENT_MAPPING" == "None" ] || [ -z "$CURRENT_MAPPING" ]; then
    aws_cli apigatewayv2 create-api-mapping --domain-name "$DOMAIN" \
        --api-id "$GATEWAY_ID" --stage '$default' > /dev/null
    echo "  $DOMAIN -> $GATEWAY_NAME."
else
    echo "  $DOMAIN ya apunta a $GATEWAY_NAME."
fi

echo "=== 6. Prueba de humo ==="
# Sin token, un servicio alcanzado por la ruta correcta responde 401 (lo
# rechaza FastAPI); un 404 o un 403 significa que la ruta no llegó al
# servicio. El DNS de Cloudflare puede tardar en propagar.
sleep 5
FAILED=0
for PROBE in "v1/ingest/datasets" "v1/analytics/runs" "v1/optimization/routes/planned"; do
    CODE=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "https://$DOMAIN/$PROBE") || CODE="000"
    echo "  /$PROBE -> HTTP $CODE $([ "$CODE" == "401" ] && echo "(OK)" || echo "(revisar)")"
    [ "$CODE" == "401" ] || FAILED=1
done
if [ "$FAILED" == "1" ]; then
    echo "La prueba de humo no pasó: no cambies las URLs todavía (DNS sin propagar o ruta mal)."
    exit 4
fi

echo "Listo. Base para el portal y los .env: https://$DOMAIN"
