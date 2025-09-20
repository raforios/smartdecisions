#!/bin/bash

# Nombre del contenedor y la imagen de Docker para DynamoDB Local
CONTAINER_NAME="dynamodb-local-container"
IMAGE_NAME="amazon/dynamodb-local"
PORT_MAPPING="3100:8000"
ENDPOINT_URL="http://localhost:3100"
REGION="us-east-1"

# Definición de las tablas a crear. Cada elemento es un objeto JSON.
TABLES=(
    '{ "name": "audit_records", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
    '{ "name": "usage_logs", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
)

echo "==================================================="
echo "  Gestión de DynamoDB Local con Docker y AWS CLI"
echo "==================================================="
echo ""

# --- Paso 1: Gestión del Contenedor Docker ---

echo "Verificando el estado del contenedor Docker '${CONTAINER_NAME}'..."

# 1.1. Verificar si el contenedor ya existe y está corriendo
if docker ps --filter "name=${CONTAINER_NAME}" --filter "status=running" --quiet | grep -q .; then
    echo "El contenedor '${CONTAINER_NAME}' ya está corriendo. No se requiere ninguna acción de Docker."
elif docker ps -a --filter "name=${CONTAINER_NAME}" --quiet | grep -q .; then
    # 1.2. Verificar si el contenedor existe pero no está corriendo (detenido/exited)
    echo "El contenedor '${CONTAINER_NAME}' existe pero no está corriendo. Iniciándolo..."
    docker start "${CONTAINER_NAME}"
    if [ $? -eq 0 ]; then
        echo "Contenedor '${CONTAINER_NAME}' iniciado correctamente."
    else
        echo "ERROR al iniciar el contenedor '${CONTAINER_NAME}'. Por favor, verifica los logs de Docker."
        exit 1
    fi
else
    # 1.3. Si el contenedor no existe, crear y ejecutar
    echo "El contenedor '${CONTAINER_NAME}' no existe. Verificando la imagen '${IMAGE_NAME}'..."
    if docker images --quiet "${IMAGE_NAME}" | grep -q .; then
        echo "La imagen '${IMAGE_NAME}' está presente. Creando y ejecutando el contenedor..."
    else
        echo "La imagen '${IMAGE_NAME}' no está presente. Descargando la imagen y creando el contenedor..."
    fi

    echo "Ejecutando: docker run -d --name ${CONTAINER_NAME} -p ${PORT_MAPPING} ${IMAGE_NAME}"
    docker run -d --name "${CONTAINER_NAME}" -p "${PORT_MAPPING}" "${IMAGE_NAME}"

    if [ $? -eq 0 ]; then
        echo "Contenedor '${CONTAINER_NAME}' creado y ejecutado correctamente en el puerto ${PORT_MAPPING//:/\/}."
    else
        echo "ERROR al crear y ejecutar el contenedor '${CONTAINER_NAME}'. Por favor, verifica los logs de Docker."
        exit 1
    fi
fi

echo ""

# --- Paso 2: Esperar a que DynamoDB Local esté listo ---

check_dynamodb_ready() {
    echo "Esperando a que DynamoDB Local esté listo en ${ENDPOINT_URL}..."
    local retries=15
    local count=0
    local sleep_time=2

    while ! aws dynamodb list-tables --endpoint-url "${ENDPOINT_URL}" --region "${REGION}" &>/dev/null; do
        if [ $count -ge $retries ]; then
            echo "ERROR: DynamoDB Local no respondió después de $retries intentos. Abortando."
            return 1
        fi
        echo "  DynamoDB Local aún no está listo. Reintentando en ${sleep_time} segundos... (Intento $((count + 1))/${retries})"
        sleep "${sleep_time}"
        count=$((count + 1))
    done
    echo "DynamoDB Local está listo y respondiendo."
    return 0
}

check_dynamodb_ready
if [ $? -ne 0 ]; then
    echo "No se pudo conectar con DynamoDB Local. Terminando el script."
    exit 1
fi

echo ""

# --- Paso 3: Gestión de la Tabla DynamoDB (Modular) ---

# Función para crear una tabla DynamoDB y configurar TTL
create_or_update_table() {
    local table_name="$1"
    local attribute_defs="$2"
    local key_schema="$3"

    echo "Verificando si la tabla '${table_name}' existe..."
    if aws dynamodb list-tables --endpoint-url "${ENDPOINT_URL}" --region "${REGION}" | grep -q "\"${table_name}\""; then
        echo "La tabla '${table_name}' ya existe. Saltando la creación."
    else
        echo "La tabla '${table_name}' no existe. Creándola..."
        aws dynamodb create-table \
            --table-name "${table_name}" \
            --attribute-definitions "${attribute_defs}" \
            --key-schema "${key_schema}" \
            --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
            --region "${REGION}" \
            --endpoint-url "${ENDPOINT_URL}"

        if [ $? -ne 0 ]; then
            echo "ERROR al crear la tabla '${table_name}'. Abortando."
            exit 1
        fi
        echo "Tabla '${table_name}' creada exitosamente. Esperando a que esté activa..."
        aws dynamodb wait table-exists --table-name "${table_name}" --endpoint-url "${ENDPOINT_URL}" --region "${REGION}"
        if [ $? -ne 0 ]; then
            echo "ERROR: La tabla '${table_name}' no se activó."
            exit 1
        fi
        echo "La tabla '${table_name}' está activa."
    fi

    # Configurar Time-to-Live (TTL)
    echo "Configurando TTL para la tabla '${table_name}'..."
    aws dynamodb update-time-to-live \
        --table-name "${table_name}" \
        --time-to-live-specification "Enabled=true,AttributeName=ttl" \
        --region "${REGION}" \
        --endpoint-url "${ENDPOINT_URL}"
    if [ $? -ne 0 ]; then
        echo "ERROR al configurar TTL para la tabla '${table_name}'. Abortando."
        exit 1
    fi
    echo "TTL configurado exitosamente para la tabla '${table_name}'."
    echo ""
}

# --- Paso 4: Iterar y Gestionar Todas las Tablas ---

for table_json in "${TABLES[@]}"; do
    table_name=$(echo "${table_json}" | jq -r '.name')
    attribute_defs=$(echo "${table_json}" | jq -r '.attributes')
    key_schema=$(echo "${table_json}" | jq -r '.keys')
    create_or_update_table "${table_name}" "${attribute_defs}" "${key_schema}"
done

echo "==================================================="
echo "  Proceso completado exitosamente."
echo "==================================================="
