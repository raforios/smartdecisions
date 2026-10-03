#!/bin/bash

# Publica todos los microservicios bajo un solo dominio: api.bearsoft.com.bo.
#
#   https://api.bearsoft.com.bo/v1/ingest/...      -> API de INGEST
#   https://api.bearsoft.com.bo/v1/analytics/...   -> API de ANALYTICS
#   ...
#
# Sin ALB ni EC2 (eso era de BINARIA): un dominio personalizado REGIONAL de API
# Gateway, un certificado de ACM y un mapeo por prefijo. Ninguna de las tres
# piezas tiene costo; se sigue pagando sólo por llamada, igual que hoy.
#
# El mapeo de varios niveles ("v1/ingest") exige dominio REGIONAL con TLS 1.2.
# El prefijo mapeado coincide con el de las rutas de cada servicio, así que la
# URL no repite nada y el código de los servicios no cambia.
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

# Prefijo de ruta -> nombre del API (el API_NAME de su deploy.config).
# Los prefijos son los de las rutas de cada servicio; si un servicio agrega un
# prefijo nuevo, se agrega acá.
MAPPINGS=(
    # --- Base: los usa todo producto ---
    "v1/auth:auth-handler-service"
    "v1/users:auth-handler-service"
    "v1/events:events-handler-service"
    "v1/s3:file-handler-service"
    "v1/classification:ml-functions-handler-service"
    "v1/common:ml-functions-handler-service"
    "v1/prediction:ml-functions-handler-service"
    # --- SmartDecisions ---
    "v1/ingest:ingest-service"
    "v1/analytics:analytics-service"
    "v1/optimization:optimization-service"
    "v1/quotes:quotes-service"
    "v1/ai:ai-service"
    "v1/mining-analysis:mining-handler-service"
    # --- SmartBilling ---
    "v1/billing:billing-handler-service"
)

aws_cli() {
    aws "$@" --region "$REGION" --profile "$PROFILE"
}

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

echo "=== 3. Mapeos por prefijo ==="
EXISTING=$(aws_cli apigatewayv2 get-api-mappings --domain-name "$DOMAIN" \
    --query "Items[].[ApiMappingKey,ApiId,ApiMappingId]" --output text)
for MAPPING in "${MAPPINGS[@]}"; do
    KEY="${MAPPING%%:*}"
    API_NAME="${MAPPING##*:}"
    API_ID=$(aws_cli apigatewayv2 get-apis --query "Items[?Name=='$API_NAME'].ApiId | [0]" --output text)
    if [ "$API_ID" == "None" ] || [ -z "$API_ID" ]; then
        echo "  $KEY: el API '$API_NAME' no existe todavía; se mapea cuando se despliegue."
        continue
    fi
    CURRENT=$(echo "$EXISTING" | awk -v key="$KEY" '$1 == key {print $2" "$3}')
    if [ -z "$CURRENT" ]; then
        aws_cli apigatewayv2 create-api-mapping --domain-name "$DOMAIN" \
            --api-mapping-key "$KEY" --api-id "$API_ID" --stage '$default' > /dev/null
        echo "  $KEY -> $API_NAME ($API_ID): creado."
    elif [ "${CURRENT%% *}" != "$API_ID" ]; then
        # El API se recreó y cambió de ID: el mapeo se corrige, la URL no cambia.
        aws_cli apigatewayv2 update-api-mapping --domain-name "$DOMAIN" \
            --api-mapping-id "${CURRENT##* }" --api-id "$API_ID" --stage '$default' > /dev/null
        echo "  $KEY -> $API_NAME ($API_ID): actualizado."
    else
        echo "  $KEY -> $API_NAME ($API_ID): ya estaba."
    fi
done

echo "=== 4. Prueba de humo ==="
# Sin token, un servicio alcanzado por la ruta correcta responde 401 (lo
# rechaza FastAPI); un 404 o un 403 significa que el mapeo no llegó al servicio
# o que la ruta no coincide. El DNS de Cloudflare puede tardar en propagar.
FAILED=0
for PROBE in "v1/ingest/datasets" "v1/analytics/runs" "v1/optimization/routes/planned"; do
    CODE=$(curl -s -o /dev/null -m 20 -w "%{http_code}" "https://$DOMAIN/$PROBE") || CODE="000"
    echo "  /$PROBE -> HTTP $CODE $([ "$CODE" == "401" ] && echo "(OK)" || echo "(revisar)")"
    [ "$CODE" == "401" ] || FAILED=1
done
if [ "$FAILED" == "1" ]; then
    echo "La prueba de humo no pasó: no cambies las URLs todavía (DNS sin propagar o mapeo mal)."
    exit 4
fi

echo "Listo. Base para el portal y los .env: https://$DOMAIN"
