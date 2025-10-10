#!/bin/bash

# 'setup_rds_instance.sh': Crea el Grupo de Subredes y la Instancia RDS MySQL.
# Lee las variables directamente desde infrastructure.config (debe existir).

set -e          # Terminar inmediatamente si un comando falla.
set -o pipefail # Terminar si un comando en un pipeline falla.

CONFIG_FILE="./infrastructure.config"

# --- 1. Cargar Variables desde el Archivo de Configuración (CORREGIDO) ---
if [ -f "$CONFIG_FILE" ]; then
    echo "Cargando configuración desde $CONFIG_FILE..."
    while IFS='=' read -r key value; do
        # 1. Quitar comentarios y líneas vacías
        if [[ "$key" =~ ^# ]] || [ -z "$key" ]; then
            continue
        fi

        # 2. Limpiar la palabra clave 'export' y trim (MÉTODO SEGURO sin xargs)
        # Quita 'export ' y espacios iniciales/finales usando SED.
        CLEAN_KEY=$(echo "$key" | sed -e 's/^[[:space:]]*export[[:space:]]*//g' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')
        
        # 3. Limpiar el valor (Quitar comillas y espacios iniciales/finales)
        CLEAN_VALUE=$(echo "$value" | sed -e 's/^[[:space:]]*"//' -e 's/"[[:space:]]*$//' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')

        # 4. Exportar la variable
        export "$CLEAN_KEY=$CLEAN_VALUE"

    done < "$CONFIG_FILE"    

else
    echo "Error: Archivo de configuración '$CONFIG_FILE' no encontrado."
    exit 1
fi
# --- 2. Verificación de Variables Críticas ---
: ${REGION:?"Error: REGION no está configurada."}
: ${PROJECT_TAG:?"Error: PROJECT_TAG no está configurada."}
: ${RDS_INSTANCE_TYPE:?"Error: RDS_INSTANCE_TYPE no está configurada. (Revisar infrastructure.config)"}
: ${RDS_STORAGE_GB:?"Error: RDS_STORAGE_GB no está configurada."}
: ${DB_NAME:?"Error: DB_NAME no está configurada."}
: ${DB_USERNAME:?"Error: DB_USERNAME no está configurada."}
: ${SG_RDS_ID:?"Error: SG_RDS_ID (Security Group de RDS) no está configurado. (Ejecute setup_aws_infrastructure.sh primero)"}
: ${PRIVATE_SUBNET_IDS:?"Error: PRIVATE_SUBNET_IDS no está configurada (Lista de Subredes Privadas)."}

# --- 3. Variables Derivadas y Nomenclatura (Minúsculas y sanitización) ---
# Creamos una etiqueta de proyecto segura (sin guiones bajos) para todos los identificadores de RDS, 
# ya que son sensibles a caracteres especiales.
PROJECT_TAG_SAFE=$(echo "$PROJECT_TAG" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g')

# Ahora definimos los nombres de los recursos usando la etiqueta segura.
RDS_SUBNET_GROUP_NAME="${PROJECT_TAG_SAFE}-rds-subnet-group"
DB_INSTANCE_ID="${PROJECT_TAG_SAFE}-mysql-db"

# Limpiar la lista de subredes para asegurar un formato simple (espacios)
# PRIVATE_SUBNET_IDS=$(echo "$PRIVATE_SUBNET_IDS" | tr ',' ' ')

DB_SUBNET_LIST=$(echo "$PRIVATE_SUBNET_IDS" | tr ',' ' ' | xargs)
echo "Usando Subredes Privadas: $DB_SUBNET_LIST para RDS Subnet Group." 

# Configurar el perfil de AWS para esta sesión
export AWS_DEFAULT_PROFILE="$AWS_PROFILE"

# --- Funciones de Utilidad ---
log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# 'read_credentials': Solicita la contraseña de RDS de forma segura.
read_credentials() {
    log_section "AUTENTICACIÓN DE BASE DE DATOS"
    # Solicitar la contraseña de forma segura (sin eco)
    echo -n "Ingrese la contraseña de $DB_USERNAME para RDS (mín. 8 caracteres): "
    read -s DB_PASSWORD
    echo "" # Salto de línea después de la entrada oculta
    
    if [ -z "$DB_PASSWORD" ]; then
        echo "Error: La contraseña no puede estar vacía."
        exit 1
    fi
    export DB_PASSWORD # Exportar para el aws cli
}

# 'manage_rds_subnet_group': Crea o verifica el grupo de subredes de RDS.
manage_rds_subnet_group() {
    log_section "GESTIÓN DEL GRUPO DE SUBREDES RDS"

    # Buscar el grupo por nombre.
    SUBNET_GROUP_EXISTS=$(aws rds describe-db-subnet-groups \
        --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
        --query 'DBSubnetGroups[0].DBSubnetGroupArn' \
        --output text \
        --region "$REGION" 2>/dev/null || true)

    if [ -z "$SUBNET_GROUP_EXISTS" ]; then
        echo "Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' no encontrado. Creando..."
        
        # CRÍTICO: Pasar los IDs como una lista simple (espacios) combinando públicas y privadas
        aws rds create-db-subnet-group \
            --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
            --db-subnet-group-description "Subnet group for ${PROJECT_TAG} DB instance" \
            --subnet-ids $DB_SUBNET_LIST \
            --tags Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"

        echo "Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' creado."
    else
        echo "Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' ya existe."
    fi
}

# Crea o verifica la instancia de base de datos RDS.
manage_rds_instance() {
    log_section "GESTIÓN DE LA INSTANCIA RDS MYSQL"
    
    # Recuperamos el ID del SG de RDS FRESH (el creado en el Paso 1)
    SG_RDS_ID=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=API_BINARIA-rds-mysql-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region "$REGION" \
        --profile "$PROFILE" 2>/dev/null)

    if [[ ! "$SG_RDS_ID" =~ ^sg-[a-f0-9]+$ ]]; then
        echo "Error FATAL: No se pudo recuperar un Security Group ID válido para RDS. SG actual: $SG_RDS_ID" >&2
        exit 1
    fi
    echo "Recuperación exitosa. Usando el ID: $SG_RDS_ID"
    
    # Verificar si la instancia ya existe y está disponible
    DB_STATUS=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text \
        --region "$REGION" 2>/dev/null || echo "not-found")

    if [ "$DB_STATUS" = "not-found" ] || [ "$DB_STATUS" = "deleted" ]; then
        echo "Instancia RDS '$DB_INSTANCE_ID' no encontrada. Creando con SG: $SG_RDS_ID..."

        # Comando de creación de la instancia
        aws rds create-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --db-instance-class "$RDS_INSTANCE_TYPE" \
            --engine "mysql" \
            --master-username "$DB_USERNAME" \
            --master-user-password "$DB_PASSWORD" \
            --allocated-storage "$RDS_STORAGE_GB" \
            --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
            --vpc-security-group-ids "$SG_RDS_ID" \
            --db-name "$DB_NAME" \
            --no-publicly-accessible \
            --backup-retention-period 7 \
            --tags Key=Name,Value="$DB_INSTANCE_ID" Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"

        echo "Instancia RDS '$DB_INSTANCE_ID' creada. Esperando estado 'available' (esto puede tardar 10-20 min)..."
        
        # Esperar a que la instancia esté disponible antes de continuar
        aws rds wait db-instance-available \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --region "$REGION"

        echo "Instancia RDS disponible (Inicialmente privada)."
        
        # BYPASS DEFINITIVO DEL BUG DE AWS: Modificar a Publicly Accessible después de la creación
        echo "Modificando instancia RDS para habilitar acceso público..."
        
        aws rds modify-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --publicly-accessible \
            --apply-immediately \
            --region "$REGION" 
            
        echo "Modificación enviada. Esperando a que la instancia RDS esté lista de nuevo..."
        aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION"
        
        echo "Instancia RDS modificada y ahora es Publicly Accessible."

    else
        echo "Instancia RDS '$DB_INSTANCE_ID' ya existe con estado: $DB_STATUS."
    fi

    # Recuperar el Endpoint después de la creación/verificación
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "$REGION")
    
    export DB_ENDPOINT
}

# --- Flujo de Ejecución Principal ---

# 4. Leer la contraseña
read_credentials

# 5. Gestión del Grupo de Subredes
manage_rds_subnet_group

# 6. Gestión de la Instancia RDS
manage_rds_instance

# --- Salida Final ---
log_section "CONFIGURACIÓN DE RDS COMPLETADA"
echo "RDS Instance ID: $DB_INSTANCE_ID"
echo "RDS Subnet Group: $RDS_SUBNET_GROUP_NAME"
echo "RDS Endpoint: $DB_ENDPOINT"
echo "RDS Database: $DB_NAME"
echo "--------------------------------------------------------------------------------"
