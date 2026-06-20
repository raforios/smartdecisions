#!/bin/bash

# Este script crea las tablas de DynamoDB necesarias para el microservicio de Events.
# Es idempotente, lo que significa que puedes ejecutarlo múltiples veces sin errores.

# Detiene la ejecución si algún comando falla
set -e

# --- Configuración de las Tablas ---
# Define un array de tablas con sus atributos de clave primaria y su tipo
# Sintaxis: "nombre_de_la_tabla:nombre_de_la_pk:tipo_de_pk"
# Tipos: S (String), N (Number), B (Binary)

TABLES=(
    "audit_records:id:S"
    "usage_logs:id:S"
    "mining_summit_participants:ci:N"
    "mining_summit_attendances:id:S"
    "ingest_datasets:id:S"
    "optimization_routes:id:S"
    "analytics_runs:id:S"
    "ingest_datasets:id:S"
)

REGION="us-east-1" # Asegúrate de que esta sea tu región de AWS
PROFILE="deploy_ml"
# --- Bucle para crear las tablas ---
echo "Iniciando la gestión de tablas de DynamoDB..."

for table_config in "${TABLES[@]}"; do
    # Lee la configuración de la tabla
    IFS=':' read -r TABLE_NAME PRIMARY_KEY_NAME PRIMARY_KEY_TYPE <<< "$table_config"

    echo "Verificando tabla: '$TABLE_NAME'..."

    # Verifica si la tabla ya existe
    if aws dynamodb describe-table --table-name "$TABLE_NAME" --region "$REGION" --profile "$PROFILE" &>/dev/null; then
        echo "Tabla '$TABLE_NAME' ya existe. Saltando la creación."
    else
        echo "Tabla '$TABLE_NAME' no encontrada. Creándola..."
        aws dynamodb create-table \
            --table-name "$TABLE_NAME" \
            --attribute-definitions AttributeName="$PRIMARY_KEY_NAME",AttributeType="$PRIMARY_KEY_TYPE" \
            --key-schema AttributeName="$PRIMARY_KEY_NAME",KeyType=HASH \
            --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
            --region "$REGION" \
            --profile "$PROFILE"
        
        echo "Esperando a que la tabla '$TABLE_NAME' esté activa..."
        aws dynamodb wait table-exists --table-name "$TABLE_NAME" --region "$REGION" --profile "$PROFILE"
        echo "Tabla '$TABLE_NAME' creada y activa."
    fi
done

echo "Proceso de creación de tablas finalizado con éxito. ✅"
