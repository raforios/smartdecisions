#!/bin/bash

# 'setup_rds_instance.sh': Crea el Grupo de Subredes y la Instancia RDS MySQL.
# Lee las variables directamente desde infrastructure.config (debe existir).

set -e          # Terminar inmediatamente si un comando falla.
set -o pipefail # Terminar si un comando en un pipeline falla.

CONFIG_FILE="./infrastructure.config"

# --- 1. Cargar Variables desde el Archivo de Configuración ---
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
: ${SG_RDS_ID:?"Error: SG_RDS_ID (Security Group de RDS) no está configurado."}
: ${PUBLIC_SUBNET_IDS:?"Error: PUBLIC_SUBNET_IDS no está configurada (Lista de Subredes Públicas)."}

# --- 3. Variables Derivadas y Nomenclatura ---
PROJECT_TAG_SAFE=$(echo "$PROJECT_TAG" | tr '[:upper:]' '[:lower:]' | sed 's/_/-/g')
RDS_SUBNET_GROUP_NAME="${PROJECT_TAG_SAFE}-rds-subnet-group"
DB_INSTANCE_ID="${PROJECT_TAG_SAFE}-mysql-db"

# Aseguramos que solo se usen Subredes Públicas
DB_SUBNET_LIST=$(echo "$PUBLIC_SUBNET_IDS" | tr ',' ' ')
echo "Usando Subredes PÚBLICAS (final): $DB_SUBNET_LIST para RDS Subnet Group." 


# --- Funciones de Utilidad (Mantenidas) ---
log_section() { echo ""; echo "--------------------------------------------------------------------------------"; echo "| $1 |"; echo "--------------------------------------------------------------------------------"; echo ""; }
read_credentials() {
    log_section "AUTENTICACIÓN DE BASE DE DATOS"
    echo -n "Ingrese la contraseña de $DB_USERNAME para RDS (mín. 8 caracteres): "
    read -s DB_PASSWORD
    echo "" 
    if [ -z "$DB_PASSWORD" ]; then echo "Error: La contraseña no puede estar vacía."; exit 1; fi
    export DB_PASSWORD
}

# Crea el grupo de subredes de RDS.
manage_rds_subnet_group() {
    log_section "GESTIÓN DEL GRUPO DE SUBREDES RDS"

    # Buscar el grupo por nombre.
    SUBNET_GROUP_EXISTS=$(aws rds describe-db-subnet-groups \
        --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
        --query 'DBSubnetGroups[0].DBSubnetGroupArn' \
        --output text \
        --region "$REGION" 2>/dev/null || true)

    if [ -n "$SUBNET_GROUP_EXISTS" ]; then
        # 🚨 CORRECCIÓN 1: Si el Subnet Group existe, NO intentamos eliminarlo si está en uso por la DB.
        # Solo lo modificamos para asegurar que las Subnets sean las correctas (es el método más seguro
        # para idempotencia cuando la instancia ya existe).
        echo "Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' ya existe. Verificando y modificando Subnets si es necesario."

        # Intentar modificar el grupo. Si no hay cambios, no pasa nada (idempotencia).
        if aws rds modify-db-subnet-group \
            --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
            --subnet-ids $DB_SUBNET_LIST \
            --region "$REGION" 2>/dev/null; then
            echo "Grupo de Subredes modificado/verificado exitosamente."
        else
            echo "Advertencia: No se pudo modificar el Subnet Group. Asumiendo configuración correcta."
        fi
        
    else
        # Primera creación
        echo "Creando Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' con Subredes Públicas: $DB_SUBNET_LIST..."
        
        aws rds create-db-subnet-group \
            --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
            --db-subnet-group-description "Subnet group for ${PROJECT_TAG} DB instance" \
            --subnet-ids $DB_SUBNET_LIST \
            --tags Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"

        echo "Grupo de Subredes '$RDS_SUBNET_GROUP_NAME' creado exitosamente con Subredes Públicas."
    fi
}

# Crea o verifica la instancia de base de datos RDS.
manage_rds_instance() {
    log_section "GESTIÓN DE LA INSTANCIA RDS MYSQL"
    
    # Recuperación del SG de RDS desde AWS
    SG_RDS_ID_FETCH=$(aws ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Name,Values=${PROJECT_TAG}-rds-mysql-sg" \
        --query 'SecurityGroups[0].GroupId' \
        --output text \
        --region "$REGION" 2>/dev/null)

    if [[ ! "$SG_RDS_ID_FETCH" =~ ^sg-[a-f0-9]+$ ]]; then
        echo "Error FATAL: No se pudo recuperar el Security Group ID válido para RDS. SG actual: $SG_RDS_ID_FETCH" >&2
        exit 1
    fi
    
    local CURRENT_RDS_SG_ID="$SG_RDS_ID_FETCH"
    echo "Recuperación exitosa. Usando el ID: $CURRENT_RDS_SG_ID"

    # Verificar si la instancia ya existe
    DB_STATUS=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].DBInstanceStatus' \
        --output text \
        --region "$REGION" 2>/dev/null || echo "not-found")

    if [ "$DB_STATUS" = "not-found" ] || [ "$DB_STATUS" = "deleted" ]; then
        echo "Instancia RDS '$DB_INSTANCE_ID' no encontrada. Creando..."

        # Creación con la configuración de Subnet Group público y sin acceso público inicial
        aws rds create-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --db-instance-class "$RDS_INSTANCE_TYPE" \
            --engine "mysql" \
            --master-username "$DB_USERNAME" \
            --master-user-password "$DB_PASSWORD" \
            --allocated-storage "$RDS_STORAGE_GB" \
            --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
            --vpc-security-group-ids "$CURRENT_RDS_SG_ID" \
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
        
        # BYPASS DEL BUG: Modificar a Publicly Accessible DEBE hacerse después de que esté disponible
        echo "Modificando instancia RDS para habilitar acceso público (CRÍTICO)."
        
        aws rds modify-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --publicly-accessible \
            --apply-immediately \
            --region "$REGION" 
            
        echo "Modificación enviada. Esperando a que la instancia RDS esté lista de nuevo..."
        aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION"
        
        echo "Instancia RDS modificada y ahora es Publicly Accessible. ¡Conexión externa garantizada!"

    elif [ "$DB_STATUS" != "available" ]; then
        # Lógica de recuperación
        echo "Instancia RDS '$DB_INSTANCE_ID' existe con estado: $DB_STATUS. Esperando a que esté disponible..."
        aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION"
        echo "Instancia RDS disponible."
    
    else
        # 🚨 CORRECCIÓN 2: Lógica de verificación/modificación si ya está disponible (BLOQUE IDEMPOTENTE)
        echo "Instancia RDS '$DB_INSTANCE_ID' ya existe y está disponible."
        echo "Verificando/actualizando Security Group y acceso público (Publicly Accessible)..."
        
        # Forzar la actualización de SG y acceso público.
        # Quitamos --db-subnet-group-name para evitar InvalidVPCNetworkStateFault.
        aws rds modify-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --vpc-security-group-ids "$CURRENT_RDS_SG_ID" \
            --publicly-accessible \
            --apply-immediately \
            --region "$REGION"
        
        echo "Modificación de SG/Acceso Público enviada. Esperando estado 'available'..."
        aws rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION"
        echo "Instancia RDS verificada/modificada (Publicly Accessible y SG correctos)."
    fi

    # Recuperar el Endpoint
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
