#!/bin/bash

# 'manage_infrastructure.sh': Script maestro para orquestar la creación y destrucción 
# de la infraestructura AWS utilizando la configuración definida en 'infrastructure.config'.

set -e          # 'Terminar' el script si un comando falla.
set -o pipefail # 'Terminar' si un comando en un pipeline falla.

# --- Constantes Globales ---
CONFIG_FILE="./infrastructure.config"

# --- Funciones de Utilidad ---

# 'log_section': Imprime un encabezado claro para una sección.
log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# 'load_config': Carga las variables de entorno desde el archivo de configuración.
# NOTA: Se llama explícitamente en la lógica principal y en la función de actualización.
load_config() {
    log_section "CARGANDO CONFIGURACIÓN"
    if [ ! -f "$CONFIG_FILE" ]; then
        echo "Error: 'Archivo de configuración '$CONFIG_FILE' no encontrado. Por favor, créalo primero.'" >&2
        exit 1
    fi
    # 'Source' el archivo de configuración para exportar variables
    source "$CONFIG_FILE"
    echo "Configuración cargada para la región: $REGION y perfil: $AWS_PROFILE"
}

# --- FUNCIÓN DE RECUPERACIÓN Y ACTUALIZACIÓN (AHORA COMPLETA) ---
retrieve_and_update_config() {
    log_section "PASO DE RECUPERACIÓN: RECUPERANDO IDs DE RECURSOS DE RED (Públicos y Privados)"
    
    # Configuramos el endpoint RDS como vacío ya que la creación es manual
    local RDS_DB_ENDPOINT=""

    # 1. Recuperar VPC ID
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=${PROJECT_TAG}-VPC" --query 'Vpcs[0].VpcId' --output text --region $REGION)
    echo "VPC ID: $VPC_ID"

    # 2. Recuperar SG ID Interno (Lambda a RDS)
    INTERNAL_SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=${PROJECT_TAG}-lambda-to-rds-sg" --query 'SecurityGroups[0].GroupId' --output text --region $REGION)
    echo "Internal SG ID (Lambda): $INTERNAL_SG_ID"
    
    # 2.5. Recuperar SG ID Público (EC2)
    # Asumimos que el SG público se llama *-ec2-public-sg
    PUB_SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=${PROJECT_TAG}-ec2-public-sg" --query 'SecurityGroups[0].GroupId' --output text --region $REGION)
    echo "Public SG ID (EC2): $PUB_SG_ID"

    # 2.75. Recuperar SG ID de RDS
    SG_RDS_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=${PROJECT_TAG}-rds-mysql-sg" --query 'SecurityGroups[0].GroupId' --output text --region $REGION)
    echo "SG de RDS: $SG_RDS_ID"

    # 3. Recuperar IDs de Subredes Privadas (Usando un filtro más robusto por el Tag Name)
    PRIVATE_SUBNET_IDS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "Subnets[?starts_with(Tags[?Key=='Name'].Value|[0], '${PROJECT_TAG}-Subnet-Private')].SubnetId" \
        --output text \
        --region $REGION | tr '\t' ',')
    echo "Private Subnet IDs (Lambda): $PRIVATE_SUBNET_IDS"

    # 3.5. Recuperar IDs de Subredes Públicas (Usando un filtro más robusto por el Tag Name)
    PUBLIC_SUBNET_IDS=$(aws ec2 describe-subnets \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "Subnets[?starts_with(Tags[?Key=='Name'].Value|[0], '${PROJECT_TAG}-Subnet-Public')].SubnetId" \
        --output text \
        --region $REGION | tr '\t' ',')
    echo "Public Subnet IDs (RDS/EC2): $PUBLIC_SUBNET_IDS"
    
    # La variable PUBLIC_SUBNET_A sigue siendo necesaria para la creación del NAT Gateway
    PUBLIC_SUBNET_A=$(echo "$PUBLIC_SUBNET_IDS" | cut -d',' -f1)
    
    # 4. Omisión del RDS Endpoint (Creación manual)
    echo "NOTA: El endpoint RDS se establecerá como vacío."
    
    # 5. ACTUALIZAR EL ARCHIVO DE CONFIGURACIÓN
    log_section "ACTUALIZANDO INFRASTRUCTURE.CONFIG"

    # Asegurar que todas las variables existan en el archivo de configuración antes de usar sed
    for var_name in VPC_ID PRIVATE_SUBNET_IDS INTERNAL_SG_ID PUB_SG_ID PUBLIC_SUBNET_A RDS_DB_ENDPOINT; do
        if ! grep -q "^export $var_name=" $CONFIG_FILE; then
            echo "export $var_name=\"\"" >> "$CONFIG_FILE"
        fi
    done

    # Reemplazar valores en el archivo usando sed (macOS/BSD sed -i.bak)
    sed -i.bak -e "s/^export VPC_ID=.*/export VPC_ID=\"$VPC_ID\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export PRIVATE_SUBNET_IDS=.*/export PRIVATE_SUBNET_IDS=\"$PRIVATE_SUBNET_IDS\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export PUBLIC_SUBNET_IDS=.*/export PUBLIC_SUBNET_IDS=\"$PUBLIC_SUBNET_IDS\"/" "$CONFIG_FILE" # <--- ¡AÑADIR ESTA LÍNEA!
    sed -i.bak -e "s/^export INTERNAL_SG_ID=.*/export INTERNAL_SG_ID=\"$INTERNAL_SG_ID\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export PUB_SG_ID=.*/export PUB_SG_ID=\"$PUB_SG_ID\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export SG_RDS_ID=.*/export SG_RDS_ID=\"$SG_RDS_ID\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export PUBLIC_SUBNET_A=.*/export PUBLIC_SUBNET_A=\"$PUBLIC_SUBNET_A\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export RDS_DB_ENDPOINT=.*/export RDS_DB_ENDPOINT=\"$DB_ENDPOINT\"/" "$CONFIG_FILE"
    sed -i.bak -e "s/^export EC2_INSTANCE_ID=.*/export EC2_INSTANCE_ID=\"$EC2_ID\"/" "$CONFIG_FILE"
    # Eliminar el backup de sed
    rm -f "$CONFIG_FILE".bak
    
    echo "Configuración de red persistida exitosamente en '$CONFIG_FILE'."

    # Recargar la configuración para que los pasos subsiguientes utilicen los valores correctos
    load_config
}
# --- FIN DE LA FUNCIÓN DE RECUPERACIÓN Y ACTUALIZACIÓN ---

# 'run_setup': Ejecuta los scripts de creación en el orden correcto.
run_setup() {
    log_section "INICIANDO CREACIÓN COMPLETA DE INFRAESTRUCTURA"
    
    # 'Establecer' el perfil de AWS CLI globalmente
    export AWS_DEFAULT_PROFILE="$AWS_PROFILE"

    # 1. Configuración de Red y Seguridad
    echo "Paso 1/6: 'Ejecutando setup_aws_infrastructure.sh' (VPC, Subnets, SGs)..."
    ./setup_aws_infrastructure.sh
    
    # Llamar a la función de recuperación que actualiza el archivo con IDs de red.
    # (Necesario para que el script de RDS tenga los IDs de Subredes y SG de RDS)
    retrieve_and_update_config
    
    # 2. Configuración de Instancia RDS
    echo "Paso 2/6: 'Ejecutando setup_rds_instance.sh' (Base de Datos MySQL)..."
    # Este script creará la instancia y, CRÍTICO, exportará la variable DB_ENDPOINT.
    ./setup_rds_instance.sh

    # Repetir la recuperación para PERSISTIR el Endpoint de RDS recién creado.
    retrieve_and_update_config
    
    # 3. Configuración de Instancia EC2
    echo "Paso 3/6: 'Ejecutando setup_ec2_instance.sh' (Instancia EC2, Par de Claves)..."
    ./setup_ec2_instance.sh
    
    # 4. Configuración de reglas de INDBOUND Y OUTBOND para EC2 y RDS
    echo "Paso 4/6: 'Ejecutando configure_security_groups.sh' (Refuerzo de Reglas de SG)..."
    ./configure_security_groups.sh

    # 5. Configuración del ALB (¡NUEVO PASO!)
    echo "Paso 5/6: 'Ejecutando setup_alb.sh' (Application Load Balancer para EC2)..."
    ./setup_alb.sh

    # 6. Configuración de API Gateway
    echo "Paso 6/6: 'Ejecutando setup_api_gateway.sh' (API Gateway Único, Integraciones)..."
    ./setup_api_gateway.sh

    log_section "CREACIÓN DE TODA LA INFRAESTRUCTURA COMPLETADA"
}

# 'run_destroy': Ejecuta el script de destrucción.
run_destroy() {
    log_section "INICIANDO DESTRUCCIÓN COMPLETA DE INFRAESTRUCTURA"
    export AWS_DEFAULT_PROFILE="$AWS_PROFILE"
    
    # 1. 'Destruir' Recursos de IaC (EC2, RDS, API GW, Red)
    ./destroy_aws_infrastructure.sh
    
    # 2. 'Eliminar' el archivo de clave privada local
    if [ -f "./${KEY_PAIR_NAME}.pem" ]; then
        echo "Eliminando archivo de clave privada local: ./${KEY_PAIR_NAME}.pem"
        rm -f "./${KEY_PAIR_NAME}.pem"
    fi
    
    log_section "PROCESO DE DESTRUCCIÓN FINALIZADO"
    echo "Recuerde ejecutar './build_and_deploy.sh --destroy' para cada microservicio para limpiar Lambdas, S3 y DynamoDB."
}


# --- Lógica Principal ---

# 'Verificar' el argumento requerido
if [ "$#" -ne 1 ]; then
    echo "Uso: ./manage_infrastructure.sh <comando>"
    echo "Comandos:"
    echo "  setup     'Crea' la infraestructura completa (VPC, SG, EC2, API GW). RDS se crea manualmente."
    echo "  destroy   'Elimina' la infraestructura completa."
    exit 1
fi

# 'Cargar' la configuración antes de la ejecución
load_config

# 'Ejecutar' el comando basado en el argumento
COMMAND="$1"
case "$COMMAND" in
    setup)
        run_setup
        ;;
    destroy)
        # 'Confirmar' la destrucción
        read -r -p "ADVERTENCIA: ¿Está seguro de que desea destruir TODOS los recursos de la infraestructura de '$PROJECT_TAG' en $REGION (sí/no)? " confirmation
        if [[ "$confirmation" = "si" ]]; then
            run_destroy
        else
            echo "Operación cancelada por el usuario."
        fi
        ;;
    *)
        echo "Error: 'Comando inválido'. Use 'setup' o 'destroy'." >&2
        exit 1
        ;;
esac 
