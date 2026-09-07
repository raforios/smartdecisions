#!/bin/bash

# Crea las tablas de DynamoDB que usan los microservicios.
# Es idempotente: puedes ejecutarlo múltiples veces sin errores.

# Detiene la ejecución si algún comando falla
set -e

# --- Configuración de las Tablas ---
# Sintaxis: "tabla:pk:tipo_pk"              -> clave simple
#           "tabla:pk:tipo_pk:sk:tipo_sk"   -> clave compuesta (partición + orden)
# Tipos: S (String), N (Number), B (Binary)
#
# Los nombres de clave son los que las tablas tienen realmente en AWS y los que
# el código consulta. Si cambias uno aquí, cámbialo también en el deploy.config
# del servicio: son dos declaraciones de la misma tabla y ya divergieron una vez.
#
# Todas se crean bajo demanda (PAY_PER_REQUEST). La capacidad provisionada de 5
# RCU con la que nacieron algunas tablas provocaba throttling en cuanto varias
# consultas coincidían, que fue el cuello de botella de usage_logs.

TABLES=(
    # --- Base: auditoría y logs de uso (EVENTS) ---
    "audit_records:id:S"
    "usage_logs:id:S"

    # --- SmartDecisions ---
    "ingest_datasets:id:S"
    "analytics_runs:id:S"
    # Clave compuesta: cada ítem es un punto de una ruta de un día concreto.
    "optimization_routes:route_day_key:S:client_id:N"
    # Clave compuesta: toda lectura es "esta moneda entre estas dos fechas".
    "exchange_rates:currency:S:date:S"
    # MINING_ANALYSIS sobre DynamoDB. El catálogo se lee por mineral; las
    # cotizaciones siempre se leen como "este mineral entre estas dos fechas",
    # que es exactamente para lo que sirve la clave de ordenamiento.
    "minerals:mineral_id:S"
    "mining_prices:mineral_id:S:date:S"
    # Capa de IA. Los roles se versionan, así que la clave de ordenamiento es la
    # versión; el caché es una sola clave porque solo se busca por ella exacta.
    "ai_prompts:view:S:version:N"
    "ai_explanations:cache_key:S"

    # --- Cumbre Minera (temporal) ---
    "mining_summit_participants:ci:S"
    "mining_summit_registration:ci:S"
    "mining_summit_attendances:id:S"
    "mining_summit_institutions:id:S"
    "mining_summit_aulas:code:S"
    "mining_summit_load_batches:batch_id:S"
)

REGION="us-east-1"
PROFILE="deploy_ml"

echo "Iniciando la gestión de tablas de DynamoDB..."

for table_config in "${TABLES[@]}"; do
    IFS=':' read -r TABLE_NAME PK_NAME PK_TYPE SK_NAME SK_TYPE <<< "$table_config"

    echo "Verificando tabla: '$TABLE_NAME'..."

    if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" --profile "$PROFILE" &>/dev/null; then
        echo "Tabla '$TABLE_NAME' ya existe. Saltando la creación."
        continue
    fi

    echo "Tabla '$TABLE_NAME' no encontrada. Creándola..."

    ATTRIBUTES="AttributeName=$PK_NAME,AttributeType=$PK_TYPE"
    KEY_SCHEMA="AttributeName=$PK_NAME,KeyType=HASH"

    # La clave de orden es opcional: sin ella la tabla guarda un ítem por clave;
    # con ella, una partición agrupa ítems que se leen por rango.
    if [ -n "$SK_NAME" ]; then
        ATTRIBUTES="$ATTRIBUTES AttributeName=$SK_NAME,AttributeType=$SK_TYPE"
        KEY_SCHEMA="$KEY_SCHEMA AttributeName=$SK_NAME,KeyType=RANGE"
        echo "  Clave compuesta: $PK_NAME (HASH) + $SK_NAME (RANGE)"
    fi

    aws dynamodb create-table \
        --table-name "$TABLE_NAME" \
        --attribute-definitions $ATTRIBUTES \
        --key-schema $KEY_SCHEMA \
        --billing-mode PAY_PER_REQUEST \
        --region "$REGION" \
        --profile "$PROFILE"

    echo "Esperando a que la tabla '$TABLE_NAME' esté activa..."
    aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION" --profile "$PROFILE"
    echo "Tabla '$TABLE_NAME' creada y activa."
done

echo "Proceso de creación de tablas finalizado con éxito. ✅"
