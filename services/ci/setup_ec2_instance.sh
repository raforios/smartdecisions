#!/bin/bash

# 'setup_ec2_instance.sh': Crea la instancia EC2, Par de Claves y la asocia a 
# los componentes de red públicos.
# 'La configuración se carga desde las variables de entorno de infrastructure.config'.

set -e
set -o pipefail

# --- Verificación de Variables (Cargadas por manage_infrastructure.sh) ---
# Si el script se ejecuta de forma independiente, fallará si estas variables no están exportadas.
: ${REGION:?"Error: REGION no está configurada en el entorno."}
: ${EC2_AMI_ID:?"Error: EC2_AMI_ID no está configurada."}
: ${EC2_INSTANCE_TYPE:?"Error: EC2_INSTANCE_TYPE no está configurada."}
: ${EC2_VOLUME_SIZE_GB:?"Error: EC2_VOLUME_SIZE_GB no está configurada."}
: ${KEY_PAIR_NAME:?"Error: KEY_PAIR_NAME no está configurada."}
: ${PROJECT_TAG:?"Error: PROJECT_TAG no está configurada."}

# --- Dependencias de Red (Exportadas desde setup_aws_infrastructure.sh) ---
: ${PUB_SG_ID:?"Error: PUB_SG_ID no está configurado. Ejecute setup_aws_infrastructure.sh primero."}
: ${PUBLIC_SUBNET_A:?"Error: PUBLIC_SUBNET_A no está configurado. Ejecute setup_aws_infrastructure.sh primero."}

# 'Nombre de Instancia Dinámico'
EC2_INSTANCE_NAME="${PROJECT_TAG}-Frontend-EC2"

# --- Funciones de Utilidad ---

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# --- Funciones Principales ---

# 'manage_key_pair': Crea un nuevo Par de Claves o verifica uno existente.
manage_key_pair() {
    log_section "GESTIÓN DEL PAR DE CLAVES (KEY PAIR)"
    
    KEY_FILE_PATH="./${KEY_PAIR_NAME}.pem"

    if [ -f "$KEY_FILE_PATH" ]; then
        echo "Archivo de clave privada '$KEY_FILE_PATH' ya existe. Omitiendo la generación."
    else
        echo "Generando nuevo par de claves: '$KEY_PAIR_NAME'..."
        # 'Crear' el par de claves usando la variable $KEY_PAIR_NAME
        aws ec2 create-key-pair \
            --key-name "$KEY_PAIR_NAME" \
            --query 'KeyMaterial' \
            --output text \
            --region "$REGION" > "$KEY_FILE_PATH"

        # 'Asignar' permisos de seguridad
        chmod 400 "$KEY_FILE_PATH"
        echo "Par de claves '$KEY_PAIR_NAME' creado. Clave privada guardada en: $KEY_FILE_PATH"
    fi
}

# 'manage_ec2_instance': Crea o verifica la instancia EC2.
manage_ec2_instance() {
    log_section "GESTIÓN DE LA INSTANCIA EC2"
    
    # Verificar si la instancia ya existe
    EC2_ID=$(aws ec2 describe-instances \
        --filters "Name=tag:Name,Values=$EC2_INSTANCE_NAME" "Name=instance-state-name,Values=running,pending" \
        --query 'Reservations[0].Instances[0].InstanceId' \
        --output text \
        --region "$REGION" | tr -d '\n' | sed 's/None//g' | xargs || true)

    if [ -z "$EC2_ID" ]; then
        echo "Instancia EC2 '$EC2_INSTANCE_NAME' no encontrada. Creando..."
        
        # 'Lanzar' la instancia usando las variables parametrizadas
        EC2_ID=$(aws ec2 run-instances \
            --image-id "$EC2_AMI_ID" \
            --instance-type "$EC2_INSTANCE_TYPE" \
            --count 1 \
            --key-name "$KEY_PAIR_NAME" \
            --security-group-ids "$PUB_SG_ID" \
            --subnet-id "$PUBLIC_SUBNET_A" \
            --associate-public-ip-address \
            --block-device-mappings "DeviceName=/dev/sda1,Ebs={VolumeSize=$EC2_VOLUME_SIZE_GB,VolumeType=gp3}" \
            --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$EC2_INSTANCE_NAME},{Key=Project,Value=$PROJECT_TAG}]" \
            --query 'Instances[0].InstanceId' \
            --output text \
            --region "$REGION")

        echo "Instancia EC2 '$EC2_ID' creada. Esperando estado 'running'..."
        
        # 'Esperar' hasta que la instancia esté activa
        aws ec2 wait instance-running --instance-ids "$EC2_ID" --region "$REGION"

        echo "Instancia activa. Obteniendo dirección IP..."
    else
        echo "Instancia EC2 '$EC2_INSTANCE_NAME' ya existe con ID: $EC2_ID."
    fi
    
    # 'Obtener' la IP pública
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids "$EC2_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text \
        --region "$REGION")
        
    export EC2_ID
    export PUBLIC_IP
}

# --- Flujo de Ejecución Principal ---

# 1. 'Gestión' del Par de Claves SSH
manage_key_pair

# 2. 'Gestión' de la Instancia EC2
manage_ec2_instance

# --- Salida Final ---
log_section "CONFIGURACIÓN DE EC2 COMPLETADA"
echo "ID de Instancia EC2: $EC2_ID"
echo "IP Pública de EC2: $PUBLIC_IP"
echo "Grupo de Seguridad Público Usado: $PUB_SG_ID"
echo "Comando de Conexión SSH (usuario 'ec2-user' para AlmaLinux):"
echo "ssh -i $KEY_PAIR_NAME.pem ec2-user@$PUBLIC_IP"
echo "--------------------------------------------------------------------------------"
echo "RECORDATORIO: La configuración de CloudFront y DNS es un paso posterior."
