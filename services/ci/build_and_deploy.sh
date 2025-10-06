#!/bin/bash

# Este script despliega una función Lambda y un API Gateway HTTP en AWS.
# Incluye gestión de IAM Role, construcción Docker y modo de destrucción.

set -e          # Terminar el script si algún comando falla
set -o pipefail # Terminar si algún comando en un pipeline falla
# set -x          # Descomenta para depuración detallada (muestra cada comando ejecutado)

# --- Configuración del Despliegue ---
HANDLER="main.handler"
RUNTIME="python3.13"
POLICIES=(
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 
    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
    "arn:aws:iam::aws:policy/AmazonS3FullAccess" 
    "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
)

# --- Validación de Argumentos y Carga de Configuración ---

# Variables para almacenar el PATH y el modo destroy
SERVICE_PATH=""
DESTROY_MODE=false
SKIP_TABLE_CREATION=false
SKIP_CODE_UPDATE=false

# Parsear argumentos
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        --path)
            SERVICE_PATH="$2"
            shift
            ;;
        --destroy)
            DESTROY_MODE=true
            ;;
        --skip-table-creation)
            SKIP_TABLE_CREATION=true
            ;;
        --skip-code-update)
            SKIP_CODE_UPDATE=true
            ;;
        *)
            echo "Uso: $0 --path <ruta_al_microservicio> [--destroy] [--skip-table-creation] [--skip-code-update]"
            echo "Ejemplo: $0 --path /Users/rafael/Work/projects/back/SmartBear/services/files"
            echo "Ejemplo para destruir: $0 --path /Users/rafael/Work/projects/back/SmartBear/services/files --destroy"
            echo "Ejemplo para saltar creación de tabla y actualización de código: $0 --path /Users/rafael/Work/projects/back/SmartBear/services/files --skip-table-creation --skip-code-update"
            exit 1
            ;;
    esac
    shift
done

# Verificar si se proporcionó la ruta
if [ -z "$SERVICE_PATH" ]; then
    echo "Error: El parámetro --path es requerido."
    echo "Uso: $0 --path <ruta_al_microservicio> [--destroy]"
    exit 1
fi

# Navegar al directorio del microservicio
echo "Cambiando al directorio del microservicio: $SERVICE_PATH"
cd "$SERVICE_PATH" || { echo "Error: No se pudo navegar al directorio '$SERVICE_PATH'."; exit 1; }

# --- Cargar Variables desde deploy.config ---
DEPLOY_CONFIG_FILE="./deploy.config"

if [ -f "$DEPLOY_CONFIG_FILE" ]; then
    echo "Cargando variables de despliegue desde '$DEPLOY_CONFIG_FILE'..."
    set -a
    source "$DEPLOY_CONFIG_FILE"
    set +a
else
    echo "Error: Archivo de configuración de despliegue '$DEPLOY_CONFIG_FILE' no encontrado en '$SERVICE_PATH'."
    exit 1
fi

# --- Asegurar que las variables esenciales del deploy.config estén definidas ---
# Después de sourcer el deploy.config, validamos que las variables esperadas existan.
: "${FUNCTION_NAME:?Error: FUNCTION_NAME no definida en deploy.config}"
: "${ROLE_NAME:?Error: ROLE_NAME no definida en deploy.config}"
: "${ZIP_FILE:?Error: ZIP_FILE no definida en deploy.config}"
: "${API_NAME:?Error: API_NAME no definida en deploy.config}"
: "${REGION:?Error: REGION no definida en deploy.config}"
: "${TIMEOUT:?Error: TIMEOUT no definida en deploy.config}"
: "${MEMORY_SIZE:?Error: MEMORY_SIZE no definida en deploy.config}"
: "${PROFILE:?Error: PROFILE no definida en deploy.config}"
: "${S3_ARTIFACTS_BUCKET:?Error: S3_ARTIFACTS_BUCKET no definida en deploy.config}"
: "${DOCKER_IMAGE_NAME:?Error: DOCKER_IMAGE_NAME no definida en deploy.config}"

if [[ "$SKIP_TABLE_CREATION" == false && "$DESTROY_MODE" == false ]]; then
    : "${DYNAMODB_TABLE_NAME:?Error: DYNAMODB_TABLE_NAME no definida en deploy.config}"
    # Nuevas validaciones para la clave primaria dinámica
    : "${DYNAMODB_PRIMARY_KEY_NAME:?Error: DYNAMODB_PRIMARY_KEY_NAME (nombre de la clave primaria) no definida en deploy.config.}"
    : "${DYNAMODB_PRIMARY_KEY_TYPE:?Error: DYNAMODB_PRIMARY_KEY_TYPE (tipo de la clave primaria, Ej: S, N) no definida en deploy.config.}"

    # Validación condicional para TTL
    # Asumimos DYNAMODB_TTL_ENABLED por defecto es 'false' si no se define o es diferente de 'true'
    if [[ "$DYNAMODB_TTL_ENABLED" == "true" ]]; then
        : "${DYNAMODB_TTL_ATTRIBUTE_NAME:?Error: DYNAMODB_TTL_ATTRIBUTE_NAME (nombre del atributo TTL) no definida en deploy.config, pero DYNAMODB_TTL_ENABLED es 'true'.}"
    fi


fi

# Función para imprimir mensajes de sección
log_section() {
    echo "---------------------------------------------------------------------------"
    echo "| $1 |"
    echo "---------------------------------------------------------------------------"
    echo ""
}

# Función para obtener el Account ID de AWS
get_aws_account_id() {
    aws sts get-caller-identity --query Account --output text --profile "$PROFILE" || { echo "Error: No se pudo obtener el Account ID de AWS. ¿Credenciales configuradas o perfil '$PROFILE' incorrecto?"; exit 1; }
}

destroy_resources() {
    log_section "MODO DESTRUCCIÓN ACTIVADO"
    ACCOUNT_ID=$(get_aws_account_id)

    # Definición de la política de acceso a DynamoDB (necesaria para construir el ARN de la política a eliminar)
    local DYNAMODB_POLICY_NAME="DynamoDB${DYNAMODB_TABLE_NAME}AccessPolicy"
    local DYNAMODB_POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${DYNAMODB_POLICY_NAME}"

    echo "Eliminando función Lambda '$FUNCTION_NAME'..."
    aws lambda delete-function --function-name "$FUNCTION_NAME" --region "$REGION" --profile "$PROFILE" 2>/dev/null || true

    # Lógica de eliminación de políticas y rol IAM
    # Primero, desadjuntar la política personalizada de DynamoDB si existe
    if aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query "AttachedPolicies[?PolicyName=='$DYNAMODB_POLICY_NAME'].PolicyName" --output text --profile "$PROFILE" | grep -q "$DYNAMODB_POLICY_NAME"; then
        echo "Desadjuntando la política personalizada '$DYNAMODB_POLICY_NAME' del rol '$ROLE_NAME'..."
        aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$DYNAMODB_POLICY_ARN" --profile "$PROFILE" || { echo "Error al desadjuntar la política '$DYNAMODB_POLICY_NAME'."; }
    else
        echo "Política IAM personalizada '$DYNAMODB_POLICY_NAME' no existe en el rol '$ROLE_NAME'."
    fi

    # Finalmente, eliminar la política personalizada de DynamoDB
    if aws iam get-policy --policy-arn "$DYNAMODB_POLICY_ARN" --profile "$PROFILE" > /dev/null 2>&1; then
        echo "Eliminando política IAM personalizada '$DYNAMODB_POLICY_NAME'..."
        aws iam delete-policy --policy-arn "$DYNAMODB_POLICY_ARN" --profile "$PROFILE" || { echo "Error al eliminar la política IAM personalizada '$DYNAMODB_POLICY_NAME'."; }
    else
        echo "Política IAM personalizada '$DYNAMODB_POLICY_NAME' no encontrada, no es necesario eliminarla."
    fi

    echo "Eliminando políticas adjuntas del rol IAM '$ROLE_NAME'..."
    for POLICY in "${POLICIES[@]}"; do
        aws iam detach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY" --profile "$PROFILE" 2>/dev/null || echo "Política '$POLICY' no adjunta al rol '$ROLE_NAME' o ya eliminada."
    done

    echo "Eliminando rol IAM '$ROLE_NAME'..."
    aws iam delete-role --role-name "$ROLE_NAME" --profile "$PROFILE" 2>/dev/null || echo "Rol IAM '$ROLE_NAME' no encontrado o ya eliminado."

    echo "Eliminando archivo ZIP local '$ZIP_FILE'..."
    rm -f "./$ZIP_FILE" 2>/dev/null || true

    echo "Todos los recursos eliminados con éxito."
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    echo ""
    exit 0

}

# --- Modo Destrucción ---
# Permite eliminar todos los recursos creados por el script.
if [[ "$DESTROY_MODE" == true ]]; then
    destroy_resources
fi

# --- Construcción del Paquete Lambda con Docker ---
build_lambda_package() {
    log_section "CONSTRUYENDO EL PAQUETE DEL SERVICIO LAMBDA CON DOCKER"

    local DOCKERFILE_PATH="./Dockerfile"

    if docker images -q "$DOCKER_IMAGE_NAME" | grep -q .; then
        echo "La imagen '$DOCKER_IMAGE_NAME' ya existe."
    else
        echo "Construyendo la imagen Docker '$DOCKER_IMAGE_NAME' desde '$DOCKERFILE_PATH'..."
        docker build -t "$DOCKER_IMAGE_NAME" . || { echo "Error: Falló la construcción de la imagen Docker '$DOCKER_IMAGE_NAME'."; exit 1; }
    fi
    echo ""

    echo "Copiando el archivo ZIP del servicio Lambda desde el contenedor..."
    local CONTAINER_ID
    CONTAINER_ID=$(docker create "$DOCKER_IMAGE_NAME") || { echo "Error: No se pudo crear un contenedor temporal desde '$DOCKER_IMAGE_NAME'."; exit 1; }
    docker cp "$CONTAINER_ID:/app/lambda_function.zip" "./$ZIP_FILE" || { echo "Error: No se pudo copiar el archivo '$ZIP_FILE' del contenedor. Verifica la ruta en el Dockerfile."; exit 1; }
    docker rm "$CONTAINER_ID" > /dev/null # Limpiar el contenedor temporal
    echo "Paquete ZIP generado localmente: $ZIP_FILE "
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    echo ""
}

# --- Subida del Paquete ZIP a S3 ---
upload_zip_to_s3() {
    log_section "SUBIENDO '$ZIP_FILE' A S3://$S3_ARTIFACTS_BUCKET/$FUNCTION_NAME/"

    aws s3 cp "./$ZIP_FILE" "s3://$S3_ARTIFACTS_BUCKET/$FUNCTION_NAME/$ZIP_FILE" --profile "$PROFILE" --region "$REGION" || { echo "Error: Falló la subida del ZIP a S3."; exit 1; }
    echo "Paquete ZIP subido a S3 con éxito."
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    echo ""
}

# --- Creación/Verificación del Rol IAM ---
manage_iam_role() {
    log_section "VERIFICANDO ROL IAM '$ROLE_NAME'"
    ACCOUNT_ID=$(get_aws_account_id)

    # Definición de la política de acceso a DynamoDB
    # Usa el nombre de la tabla de DynamoDB para que la política sea específica
    local DYNAMODB_POLICY_NAME="DynamoDB${DYNAMODB_TABLE_NAME}AccessPolicy"
    local DYNAMODB_POLICY_ARN="arn:aws:iam::${ACCOUNT_ID}:policy/${DYNAMODB_POLICY_NAME}"

    DYNAMODB_ACCESS_POLICY_JSON=$(cat << EOF_DYNAMODB_POLICY
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:${REGION}:${ACCOUNT_ID}:table/${DYNAMODB_TABLE_NAME}"
        }
    ]
}
EOF_DYNAMODB_POLICY
)

    ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text --profile "$PROFILE" 2>/dev/null || true)
    if [ -z "$ROLE_ARN" ]; then
        echo "Rol '$ROLE_NAME' no existe. Creando..."
        aws iam create-role \
            --role-name "$ROLE_NAME" \
            --assume-role-policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": { "Service": "lambda.amazonaws.com" },
                "Action": "sts:AssumeRole"
            },
            {
                "Effect": "Allow",
                "Principal": { "Service": "sqs.amazonaws.com" },
                "Action": "sts:AssumeRole"
            }]
            }' \
            --profile "$PROFILE" > /dev/null || { echo "Error: Falló la creación del rol IAM '$ROLE_NAME'."; exit 1; }

        echo "Esperando que el rol '$ROLE_NAME' esté disponible en IAM..."
        if ! aws iam wait role-exists --role-name "$ROLE_NAME" --profile "$PROFILE"; then
            echo "Error: El rol '$ROLE_NAME' no se creó correctamente o no está disponible después de esperar."
            exit 1
        fi

        echo "Adjuntando políticas al rol IAM '$ROLE_NAME'..."
        for POLICY in "${POLICIES[@]}"; do
            aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY" --profile "$PROFILE" || { echo "Error: Falló al adjuntar la política '$POLICY'."; exit 1; }
        done

        echo "Esperando propagación de políticas para el rol '$ROLE_NAME' (se recomienda 30-90 segundos)..."
        sleep 90
        echo ""

        ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text --profile "$PROFILE")
        if [ -z "$ROLE_ARN" ]; then
            echo "Error: No se pudo obtener el ARN del rol '$ROLE_NAME' después de la creación y espera."
            exit 1
        fi
    else
        echo "Rol IAM existente: $ROLE_ARN"
        echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
        echo ""
    fi

   # --- GESTIÓN DE POLÍTICAS DE ACCESO A DYNAMODB ---
    echo "Configurando política de acceso a DynamoDB para el rol '$ROLE_NAME'..."

    # Normalizar el JSON de la política deseada para una comparación fiable
    # Esto elimina espacios en blanco inconsistentes y ordena las claves
    echo "$DYNAMODB_ACCESS_POLICY_JSON" >&2
    
    NORMALIZED_DESIRED_POLICY_JSON=$(echo "$DYNAMODB_ACCESS_POLICY_JSON" | jq -S -c .)
    if [ $? -ne 0 ]; then
        echo "Error: El JSON de la política deseada para DynamoDB está malformado (ERROR DE JQ EN POLÍTICA DESEADA). Por favor, revisa la sintaxis." >&2
        echo "Contenido del JSON que causó el error (POLÍTICA DESEADA):" >&2
        echo "$DYNAMODB_ACCESS_POLICY_JSON" >&2
        exit 1
    fi

    # 1. Verificar/Crear la política de acceso a DynamoDB
    if aws iam get-policy --policy-arn "$DYNAMODB_POLICY_ARN" --profile "$PROFILE" > /dev/null 2>&1; then
        echo "Política IAM '$DYNAMODB_POLICY_NAME' para DynamoDB ya existe."

        # Obtener la versión por defecto de la política actual
        CURRENT_DEFAULT_VERSION_ID=$(aws iam get-policy --policy-arn "$DYNAMODB_POLICY_ARN" --profile "$PROFILE" --query 'Policy.DefaultVersionId' --output text 2>/dev/null)
        
        local NORMALIZED_CURRENT_POLICY_JSON="" # Inicializamos a vacío para el caso de error

        if [ -z "$CURRENT_DEFAULT_VERSION_ID" ]; then
            echo "Advertencia: No se pudo obtener la versión por defecto de la política '$DYNAMODB_POLICY_NAME'. Forzando una actualización." >&2
        else
            # Obtener el contenido del documento de la versión por defecto
            local CURRENT_POLICY_DOCUMENT_ENCODED=""
            CURRENT_POLICY_DOCUMENT_ENCODED=$(aws iam get-policy-version \
                --policy-arn "$DYNAMODB_POLICY_ARN" \
                --version-id "$CURRENT_DEFAULT_VERSION_ID" \
                --profile "$PROFILE" \
                --query 'PolicyVersion.Document' --output json 2>/dev/null)

            if [ -z "$CURRENT_POLICY_DOCUMENT_ENCODED" ]; then
                echo "Advertencia: No se pudo recuperar el documento de la política actual de AWS para la versión '$CURRENT_DEFAULT_VERSION_ID'. Forzando una actualización." >&2
            else
                # Decodificar y normalizar el JSON actual de AWS
                echo "$CURRENT_POLICY_DOCUMENT_ENCODED" >&2

                # Decodificar y normalizar el JSON actual de AWS
                NORMALIZED_CURRENT_POLICY_JSON=$(echo "$CURRENT_POLICY_DOCUMENT_ENCODED" | jq -r '.' 2>/dev/null | jq -S -c '.')
                
                if [ $? -ne 0 ]; then
                    echo "ERROR AL PARSEAR POLÍTICA ACTUAL DE AWS CON JQ." >&2
                    echo "JSON ORIGINAL RECUPERADO DE AWS (posiblemente codificado):" >&2
                    echo "$CURRENT_POLICY_DOCUMENT_ENCODED" >&2
                    echo "FIN DEL JSON ORIGINAL." >&2
                    echo "Advertencia: Falló la normalización del JSON de la política actual en AWS. El JSON recuperado podría estar corrupto o no ser válido. Se forzará la actualización." >&2
                    NORMALIZED_CURRENT_POLICY_JSON="" # Para forzar la desigualdad y la creación de una nueva versión
                fi
            fi
        fi

        # Comparar el contenido normalizado
        if [ "$NORMALIZED_DESIRED_POLICY_JSON" = "$NORMALIZED_CURRENT_POLICY_JSON" ]; then
            echo "El contenido de la política IAM '$DYNAMODB_POLICY_NAME' ya está actualizado. No se requiere acción."
        else
            echo "El contenido de la política IAM '$DYNAMODB_POLICY_NAME' ha cambiado. Creando una nueva versión..."
            
            # Crear nueva versión de la política y establecerla como predeterminada
            # ¡Usamos DYNAMODB_ACCESS_POLICY_JSON aquí!
            NEW_VERSION_ID=$(aws iam create-policy-version \
                --policy-arn "$DYNAMODB_POLICY_ARN" \
                --policy-document "$DYNAMODB_ACCESS_POLICY_JSON" \
                --set-as-default \
                --profile "$PROFILE" \
                --query 'PolicyVersion.VersionId' --output text) || { echo "Error: Falló la creación de una nueva versión para la política '$DYNAMODB_POLICY_NAME'."; exit 1; }
            echo "Nueva versión de la política '$DYNAMODB_POLICY_NAME' creada y establecida como predeterminada: $NEW_VERSION_ID."

            # Limpiar versiones antiguas para no exceder el límite de 5
            OLD_VERSIONS_JSON=$(aws iam list-policy-versions \
                --policy-arn "$DYNAMODB_POLICY_ARN" \
                --profile "$PROFILE" \
                --output json) || { echo "Advertencia: Falló al listar las versiones de la política para limpieza."; }

            # Usar jq para filtrar y obtener los VersionId, excluyendo la nueva versión y manteniendo las más recientes
            OLD_VERSIONS_TO_DELETE=$(echo "$OLD_VERSIONS_JSON" | \
                jq -r --arg new_version "$NEW_VERSION_ID" '
                    .Versions |
                    sort_by(.CreateDate) |
                    .[] |
                    select(.IsDefault == false and .VersionId != $new_version) |
                    .VersionId
                '
            )

            VERSION_COUNT_TO_CONSIDER=0
            if [ -n "$OLD_VERSIONS_TO_DELETE" ]; then
                VERSION_COUNT_TO_CONSIDER=$(echo "$OLD_VERSIONS_TO_DELETE" | wc -l)
            fi

            if [ "$VERSION_COUNT_TO_CONSIDER" -ge 2 ]; then
                echo "Detectadas $VERSION_COUNT_TO_CONSIDER versiones antiguas a limpiar. Manteniendo las más recientes..."
                OLD_VERSIONS_ARRAY=($OLD_VERSIONS_TO_DELETE)
                NUM_TO_KEEP=3
                NUM_TO_DELETE=$(expr ${#OLD_VERSIONS_ARRAY[@]} - $NUM_TO_KEEP)
                
                if [ "$NUM_TO_DELETE" -gt 0 ]; then
                    for (( i=0; i<NUM_TO_DELETE; i++ )); do
                        OLD_VERSION_ID="${OLD_VERSIONS_ARRAY[$i]}"
                        echo "Eliminando versión antigua de política: $OLD_VERSION_ID"
                        aws iam delete-policy-version \
                            --policy-arn "$DYNAMODB_POLICY_ARN" \
                            --version-id "$OLD_VERSION_ID" \
                            --profile "$PROFILE" || echo "Advertencia: No se pudo eliminar la versión de política antigua $OLD_VERSION_ID."
                    done
                fi
            fi
        fi
    else
        echo "Política IAM '$DYNAMODB_POLICY_NAME' para DynamoDB no existente. Creando política..."
        aws iam create-policy \
            --policy-name "$DYNAMODB_POLICY_NAME" \
            --policy-document "$DYNAMODB_ACCESS_POLICY_JSON" \
            --description "Allows Lambda role to access DynamoDB table ${DYNAMODB_TABLE_NAME}" \
            --profile "$PROFILE" || { echo "Error: Falló la creación de la política IAM '$DYNAMODB_POLICY_NAME'." >&2; exit 1; }
        echo "Política IAM '$DYNAMODB_POLICY_NAME' para DynamoDB creada con éxito."
    fi

    # 2. Verificar/Adjuntar la política de DynamoDB al rol
    if aws iam list-attached-role-policies --role-name "$ROLE_NAME" --query "AttachedPolicies[?PolicyName=='$DYNAMODB_POLICY_NAME'].PolicyName" --output text --profile "$PROFILE" | grep -q "$DYNAMODB_POLICY_NAME"; then
        echo "Política IAM '$DYNAMODB_POLICY_NAME' ya adjunta al rol '$ROLE_NAME'."
    else
        echo "Adjuntando política IAM '$DYNAMODB_POLICY_NAME' al rol '$ROLE_NAME'..."
        aws iam attach-role-policy \
            --role-name "$ROLE_NAME" \
            --policy-arn "$DYNAMODB_POLICY_ARN" \
            --profile "$PROFILE" || { echo "Error: Falló al adjuntar la política IAM '$DYNAMODB_POLICY_NAME' al rol '$ROLE_NAME'." >&2; exit 1; }
        echo "Política IAM '$DYNAMODB_POLICY_NAME' adjunta con éxito al rol '$ROLE_NAME'."
    fi

}

# --- Procesamiento de Variables de Entorno (.env) ---
get_environment_variables() {
    # log_section "LEYENDO VARIABLES DE ENTORNO DESDE .ENV (SI EXISTE)"
    echo "---------------------------------------------------------------------------" >&2
    echo "| LEYENDO VARIABLES DE ENTORNO DESDE .ENV (SI EXISTE) |" >&2
    echo "---------------------------------------------------------------------------" >&2
    echo "" >&2

    env_string=""
    local first_pair=true

    if [ -f ".env" ]; then
        # Leer el archivo .env línea por línea
        while IFS='=' read -r key value; do
            # Eliminar espacios en blanco alrededor de la clave y el valor
            key=$(echo "$key" | xargs)
            value=$(echo "$value" | xargs)

            # Ignorar comentarios y líneas vacías
            if [[ -n "$key" && ! "$key" =~ ^# ]]; then
                # Escapar comillas dobles y barras invertidas en el valor para que sea JSON válido
                # Utilizamos printf para evitar problemas con carácteres especiales como nueva línea
                escaped_value=$(printf '%s' "$value" | sed 's/\\/\\\\/g; s/"/\\"/g')

               # Añadir coma si no es el primer par
                if [[ "$first_pair" == false ]]; then
                    env_string+=","
                fi
                
                # Añadir el par clave-valor
                env_string+="$key=$escaped_value"
                first_pair=false

            fi
        done < ".env"

        # Formato esperado por --environment "Variables={...}"
        env_string="Variables={$env_string}" 
        echo "Variables de entorno procesadas para Lambda: $env_string" >&2

    else
        # echo "Advertencia: Archivo .env no encontrado. No se configurarán variables de entorno para Lambda."
        echo "Advertencia: Archivo .env no encontrado. No se configurarán variables de entorno para Lambda." >&2
    fi
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++" >&2
    echo "" >&2 # Redirigir a stderr

    # echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    # echo ""
    echo "$env_string" # Devuelve el JSON
}

# Se declara una variable global para las variables de entorno de Lambda.
LAMBDA_ENV_VARS_JSON=$(get_environment_variables)

# --- Creación y Gestión de la Tabla DynamoDB ---
manage_dynamodb_table() {
    log_section "VERIFICANDO Y CREANDO TABLA DYNAMODB '$DYNAMODB_TABLE_NAME'"

    # Construir AttributeDefinitions y KeySchema dinámicamente
    # La clave primaria siempre se incluye en AttributeDefinitions
    LOCAL_ATTR_DEFS="AttributeName=${DYNAMODB_PRIMARY_KEY_NAME},AttributeType=${DYNAMODB_PRIMARY_KEY_TYPE}"
    LOCAL_KEY_SCHEMA="AttributeName=${DYNAMODB_PRIMARY_KEY_NAME},KeyType=HASH"

    # Si TTL está habilitado, añadimos su atributo a las AttributeDefinitions
    # Asumimos que el atributo TTL siempre es de tipo Número (N) para timestamp Unix
    if [[ "$DYNAMODB_TTL_ENABLED" == "true" ]]; then
        LOCAL_ATTR_DEFS="${LOCAL_ATTR_DEFS} AttributeName=${DYNAMODB_TTL_ATTRIBUTE_NAME},AttributeType=N"
    fi

    if aws dynamodb describe-table --table-name "$DYNAMODB_TABLE_NAME" --region "$REGION" --profile "$PROFILE" > /dev/null 2>&1; then
        echo "Tabla DynamoDB '$DYNAMODB_TABLE_NAME' ya existe. Saltando creación."

        # Gestión de TTL para tablas existentes
        if [[ "$DYNAMODB_TTL_ENABLED" == "true" ]]; then
            echo "Verificando estado de TTL para la tabla '$DYNAMODB_TABLE_NAME'..."
            TTL_STATUS=$(aws dynamodb describe-time-to-live \
                         --table-name "$DYNAMODB_TABLE_NAME" \
                         --query 'TimeToLiveDescription.TimeToLiveStatus' \
                         --output text \
                         --region "$REGION" \
                         --profile "$PROFILE")

            if [ "$TTL_STATUS" != "ENABLING" ] && [ "$TTL_STATUS" != "ENABLED" ]; then
                echo "TTL no habilitado para la tabla '$DYNAMODB_TABLE_NAME'. Habilitando para el atributo '$DYNAMODB_TTL_ATTRIBUTE_NAME'..."
                aws dynamodb update-time-to-live \
                    --table-name "$DYNAMODB_TABLE_NAME" \
                    --time-to-live-specification "Enabled=true,AttributeName=${DYNAMODB_TTL_ATTRIBUTE_NAME}" \
                    --region "$REGION" \
                    --profile "$PROFILE" || { log_error "Falló la habilitación de TTL para la tabla '$DYNAMODB_TABLE_NAME'."; exit 1; }
                echo "TTL habilitado para la tabla '$DYNAMODB_TABLE_NAME'."
            else
                echo "TTL ya está '$TTL_STATUS' para la tabla '$DYNAMODB_TABLE_NAME'."
            fi
        else
            echo "TTL no requerido para la tabla '$DYNAMODB_TABLE_NAME' (DYNAMODB_TTL_ENABLED no es 'true')."
        fi

    else
        echo "Tabla DynamoDB '$DYNAMODB_TABLE_NAME' no encontrada. Creando..."
        aws dynamodb create-table \
            --table-name "$DYNAMODB_TABLE_NAME" \
            --attribute-definitions "$LOCAL_ATTR_DEFS" \
            --key-schema "$LOCAL_KEY_SCHEMA" \
            --billing-mode PAY_PER_REQUEST \
            --region "$REGION" \
            --profile "$PROFILE" || { echo "Error: Falló la creación de la tabla DynamoDB '$DYNAMODB_TABLE_NAME'."; exit 1; }

        echo "Esperando que la tabla '$DYNAMODB_TABLE_NAME' esté activa..."
        aws dynamodb wait table-exists --table-name "$DYNAMODB_TABLE_NAME" --region "$REGION" --profile "$PROFILE" || { echo "Error: La tabla '$DYNAMODB_TABLE_NAME' no se activó después de la creación."; exit 1; }
        echo "Tabla DynamoDB '$DYNAMODB_TABLE_NAME' creada y activa con éxito."

        # Habilitar TTL para el atributo 'ttl' después de la creación, si DYNAMODB_TTL_ENABLED es true
        if [[ "$DYNAMODB_TTL_ENABLED" == "true" ]]; then
            echo "Habilitando TTL para el atributo '$DYNAMODB_TTL_ATTRIBUTE_NAME' en la tabla '$DYNAMODB_TABLE_NAME'..."
            aws dynamodb update-time-to-live \
                --table-name "$DYNAMODB_TABLE_NAME" \
                --time-to-live-specification "Enabled=true,AttributeName=${DYNAMODB_TTL_ATTRIBUTE_NAME}" \
                --region "$REGION" \
                --profile "$PROFILE" || { log_error "Falló la habilitación de TTL para la tabla '$DYNAMODB_TABLE_NAME' después de la creación."; exit 1; }
            echo "TTL habilitado para la tabla '$DYNAMODB_TABLE_NAME'."
        else
            echo "TTL no requerido para la tabla '$DYNAMODB_TABLE_NAME' (DYNAMODB_TTL_ENABLED no es 'true')."
        fi
    fi
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    echo ""
}

# --- Creación o Actualización de la Función Lambda ---
manage_lambda_function() {
    log_section "VERIFICANDO FUNCIÓN LAMBDA '$FUNCTION_NAME' EN LA REGIÓN '$REGION'"

    local env_args=""
    if [ -n "$LAMBDA_ENV_VARS_JSON" ]; then
        env_args="--environment $LAMBDA_ENV_VARS_JSON"
    fi

    # Lógica de Configuración VPC (RESTAURADA)
    local vpc_config_args=""
    if [ -n "$VPC_ID" ] && [ -n "$PRIVATE_SUBNET_IDS" ] && [ -n "$INTERNAL_SG_ID" ]; then
        echo "Configuración VPC detectada. La función se desplegará en la red privada para acceder a RDS/MySQL."
        vpc_config_args="--vpc-config SubnetIds=$PRIVATE_SUBNET_IDS,SecurityGroupIds=$INTERNAL_SG_ID"
    else
        echo "Advertencia: Las variables de 'Configuración VPC' (VPC_ID, PRIVATE_SUBNET_IDS, INTERNAL_SG_ID) no están completamente configuradas."
        echo "La función Lambda se desplegará sin acceso a la VPC."
    fi
    # Fin de Lógica de Configuración VPC

    if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --profile "$PROFILE" > /dev/null 2>&1; then
        echo "Función Lambda existente. Actualizando código y configuración de '$FUNCTION_NAME'..."


        # Actualiza el código solo si no se ha especificado --skip-code-update
        if [[ "$SKIP_CODE_UPDATE" == false ]]; then
            echo "Actualizando código de '$FUNCTION_NAME'..."
            aws lambda update-function-code \
                --function-name "$FUNCTION_NAME" \
                --s3-bucket "$S3_ARTIFACTS_BUCKET" \
                --s3-key "$FUNCTION_NAME/$ZIP_FILE" \
                --region "$REGION" \
                --profile "$PROFILE" || { echo "Error: Falló la actualización del código de Lambda."; exit 1; }

            echo "Esperando que la actualización del código de Lambda '$FUNCTION_NAME' esté activa..."
            aws lambda wait function-active \
                --function-name "$FUNCTION_NAME" \
                --region "$REGION" \
                --profile "$PROFILE" || { echo "Error: La actualización del código de Lambda '$FUNCTION_NAME' no se activó."; exit 1; }
            sleep 45
        else
            echo "Saltando actualización del código de Lambda (--skip-code-update activado). Se usará el código existente."
        fi

        aws lambda update-function-configuration \
            --function-name "$FUNCTION_NAME" \
            --runtime "$RUNTIME" \
            --handler "$HANDLER" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY_SIZE" \
            --role "$ROLE_ARN" \
            --region "$REGION" \
            --profile "$PROFILE" \
            $vpc_config_args \
            $env_args || { echo "Error: Falló la actualización de la configuración de Lambda."; exit 1; }

        echo "Función Lambda '$FUNCTION_NAME' actualizada con éxito."
    else
        echo "Función Lambda no existente. Creando nueva función '$FUNCTION_NAME'..."

        aws lambda create-function \
            --function-name "$FUNCTION_NAME" \
            --runtime "$RUNTIME" \
            --role "$ROLE_ARN" \
            --handler "$HANDLER" \
            --code "S3Bucket=$S3_ARTIFACTS_BUCKET,S3Key=$FUNCTION_NAME/$ZIP_FILE" \
            --timeout "$TIMEOUT" \
            --memory-size "$MEMORY_SIZE" \
            --region "$REGION" \
            --profile "$PROFILE" \
            $vpc_config_args \
            $env_args || { echo "Error: Falló la creación de la Lambda '$FUNCTION_NAME'."; exit 1; }
        
        echo "Esperando que la función Lambda '$FUNCTION_NAME' esté activa después de la creación..."
        aws lambda wait function-active \
            --function-name "$FUNCTION_NAME" \
            --region "$REGION" \
            --profile "$PROFILE" || { echo "Error: La función Lambda '$FUNCTION_NAME' no se activó."; exit 1; }
        sleep 45

        echo "Función Lambda '$FUNCTION_NAME' creada y activa con éxito."
    fi
    echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
    echo ""
        
}

# --- Flujo Principal de Despliegue ---
main_deploy_flow() {
    # Paso 1: Construcción y Subida del Código Lambda (opcional)
    if [[ "$SKIP_CODE_UPDATE" == false ]]; then
        build_lambda_package # Se construye el ZIP localmente
        upload_zip_to_s3     # Se sube el ZIP a S3
    else
        echo "Saltando la construcción del paquete Lambda y la subida a S3 (--skip-code-update activado)."
    fi

    # Paso 2: Gestión del Rol IAM (siempre necesario)
    manage_iam_role

    # Paso 3: Gestión de la Tabla DynamoDB (opcional)
    if [[ "$SKIP_TABLE_CREATION" == false ]]; then
        manage_dynamodb_table
    else
        echo "Saltando la creación/verificación de la tabla DynamoDB (--skip-table-creation activado)."
    fi

    # Paso 4: Gestión de la Función Lambda
    manage_lambda_function

    # Paso 5: Limpieza del ZIP local (condicional)
    if [[ "$SKIP_CODE_UPDATE" == false ]]; then
        echo "Eliminando archivo ZIP local '$ZIP_FILE'..."
        rm -f "./$ZIP_FILE" 2>/dev/null || true
    fi

}

# Ejecutar el flujo principal
main_deploy_flow

# --- Mostrar URL Pública Final ---
log_section "DESPLIEGUE COMPLETADO CON ÉXITO."
echo "La función Lambda '$FUNCTION_NAME' está desplegada y lista para ser integrada en un API Gateway centralizado."
echo "+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++"
