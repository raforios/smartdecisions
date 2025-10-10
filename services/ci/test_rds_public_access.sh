#!/bin/bash

# --- Configuración ---
REGION="us-east-1"
PROFILE="deploy_binaria"
DB_INSTANCE_ID="temp-test-db-rafael"
DB_NAME="testdb"
MASTER_USERNAME="tester"
MASTER_PASSWORD="mySecureTestPassword123" # CONTRASEÑA DE PRUEBA
VPC_CIDR="10.10.0.0/16"
SUBNET_CIDR_1="10.10.1.0/24" # AZ A
SUBNET_CIDR_2="10.10.2.0/24" # AZ B
SG_NAME="temp-test-rds-sg"
SUBNET_NAME="temp-test-subnet"
RDS_SUBNET_GROUP_NAME="temp-test-rds-group"

# --- Variables Globales para Guardar IDs ---
VPC_ID=""
IGW_ID=""
SUBNET_ID_1=""
SUBNET_ID_2=""
RTB_ID=""
SG_ID=""
DB_ENDPOINT=""

# --- Funciones de Utilidad ---
log_section() {
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
}

# --- Paso 1: Crear Recursos Mínimos de Red (VPC y DOS Subredes Públicas) ---
setup_network() {
    log_section "PASO 1/5: CREANDO VPC Y DOS SUBREDES PÚBLICAS (2 AZs)"

    # 1. Crear VPC
    VPC_ID=$(aws ec2 create-vpc --cidr-block "$VPC_CIDR" --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=TempTestVPC}]" --query 'Vpc.VpcId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    echo "VPC Creada: $VPC_ID"
    
    # CRÍTICO: Habilitar DNS Hostnames y Resolution (SOLUCIÓN AL ERROR InvalidVPCNetworkStateFault)
    aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support "{\"Value\":true}" --region "$REGION" --profile "$PROFILE"
    aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames "{\"Value\":true}" --region "$REGION" --profile "$PROFILE"
    echo "DNS Support y DNS Hostnames habilitados para VPC: $VPC_ID"
    
    # 2. Crear Internet Gateway y adjuntarlo
    IGW_ID=$(aws ec2 create-internet-gateway --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=TempTestIGW}]" --query 'InternetGateway.InternetGatewayId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    aws ec2 attach-internet-gateway --vpc-id "$VPC_ID" --internet-gateway-id "$IGW_ID" --region "$REGION" --profile "$PROFILE"
    echo "Internet Gateway Creado: $IGW_ID"

    # 3. Crear Subred Pública 1 (AZ A)
    SUBNET_ID_1=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$SUBNET_CIDR_1" --availability-zone "${REGION}a" --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${SUBNET_NAME}A}]" --query 'Subnet.SubnetId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    echo "Subred 1 Creada (AZ A): $SUBNET_ID_1"

    # 4. Crear Subred Pública 2 (AZ B)
    SUBNET_ID_2=$(aws ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$SUBNET_CIDR_2" --availability-zone "${REGION}b" --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${SUBNET_NAME}B}]" --query 'Subnet.SubnetId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    echo "Subred 2 Creada (AZ B): $SUBNET_ID_2"

    # Habilitar Auto-Assign Public IP
    aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID_1" --map-public-ip-on-launch --region "$REGION" --profile "$PROFILE"
    aws ec2 modify-subnet-attribute --subnet-id "$SUBNET_ID_2" --map-public-ip-on-launch --region "$REGION" --profile "$PROFILE"

    # 5. Crear Tabla de Ruta y Regla por Defecto (0.0.0.0/0 a IGW)
    RTB_ID=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=TempTestRTB}]" --query 'RouteTable.RouteTableId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    aws ec2 create-route --route-table-id "$RTB_ID" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" --region "$REGION" --profile "$PROFILE"
    
    # Asociar RTB con ambas subredes
    aws ec2 associate-route-table --subnet-id "$SUBNET_ID_1" --route-table-id "$RTB_ID" --region "$REGION" --profile "$PROFILE"
    aws ec2 associate-route-table --subnet-id "$SUBNET_ID_2" --route-table-id "$RTB_ID" --region "$REGION" --profile "$PROFILE"
    echo "Tabla de Ruta Creada: $RTB_ID (asociada a ambas subredes)"
}

# --- Paso 2: Crear Security Group Abierto ---
setup_security_group() {
    log_section "PASO 2/5: CREANDO SECURITY GROUP ABIERTO A 0.0.0.0/0"
    
    SG_ID=$(aws ec2 create-security-group --group-name "$SG_NAME" --description "SG for temporary public RDS test" --vpc-id "$VPC_ID" --query 'GroupId' --output text --region "$REGION" --profile "$PROFILE" || exit 1)
    echo "Security Group Creado: $SG_ID"

    # Autorizar acceso global (0.0.0.0/0) en el puerto MySQL (3306)
    aws ec2 authorize-security-group-ingress \
        --group-id "$SG_ID" \
        --protocol tcp \
        --port 3306 \
        --cidr 0.0.0.0/0 \
        --region "$REGION" --profile "$PROFILE" || exit 1
    echo "Regla Ingress (3306/TCP desde 0.0.0.0/0) añadida a $SG_ID."
}

# --- Paso 3: Crear DB Subnet Group ---
setup_rds_subnet_group() {
    log_section "PASO 3/5: CREANDO GRUPO DE SUBREDES RDS (2 AZs)"

    # Usar ambas subredes para cumplir con el requisito de 2 AZs.
    aws rds create-db-subnet-group \
        --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
        --db-subnet-group-description "Temporary public test group" \
        --subnet-ids "$SUBNET_ID_1" "$SUBNET_ID_2" \
        --region "$REGION" --profile "$PROFILE" || exit 1
    echo "DB Subnet Group Creado: $RDS_SUBNET_GROUP_NAME (Cubriendo us-east-1a y us-east-1b)"
}

# --- Paso 4: Crear RDS MySQL Pública (CRÍTICO) ---
create_rds_instance() {
    log_section "PASO 4/5: CREANDO INSTANCIA RDS PÚBLICA"

    aws rds create-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --db-instance-class db.t3.micro \
        --engine mysql \
        --allocated-storage 20 \
        --master-username "$MASTER_USERNAME" \
        --master-user-password "$MASTER_PASSWORD" \
        --db-name "$DB_NAME" \
        --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" \
        --vpc-security-group-ids "$SG_ID" \
        --publicly-accessible \
        --region "$REGION" --profile "$PROFILE" || exit 1
    
    echo "Instancia RDS '$DB_INSTANCE_ID' solicitada. Esto tomará ~5-10 minutos..."
    echo "Esperando que el estado de la instancia sea 'available'..."

    aws rds wait db-instance-available \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --region "$REGION" --profile "$PROFILE" || { echo "Error: RDS no disponible."; exit 1; }
    
    echo "Instancia RDS disponible."

    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "$REGION" --profile "$PROFILE")

    log_section "PRUEBA LISTA PARA CONEXIÓN"
    echo "ENDPOINT: $DB_ENDPOINT"
    echo "USUARIO: $MASTER_USERNAME"
    echo "CONTRASEÑA: $MASTER_PASSWORD"
    echo "PUERTO: 3306"
    echo "--------------------------------------------------------------------------------"
    echo "¡Intenta conectarte con MySQL Workbench o nc AHORA!"
}

# --- Paso 5: Función de Limpieza (busca IDs al inicio si es destroy) ---
cleanup_resources() {
    log_section "PASO 5/5: INICIANDO LIMPIEZA DE RECURSOS TEMPORALES"

    # Recuperar IDs si no están definidos (solo ocurre en modo destroy)
    if [ -z "$VPC_ID" ]; then
        VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=TempTestVPC" --query 'Vpcs[0].VpcId' --output text --region "$REGION" --profile "$PROFILE" || echo "")
    fi
    if [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=$SG_NAME" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION" --profile "$PROFILE" || echo "")
    fi
    if [ -z "$IGW_ID" ]; then
        IGW_ID=$(aws ec2 describe-internet-gateways --filters "Name=tag:Name,Values=TempTestIGW" --query 'InternetGateways[0].InternetGatewayId' --output text --region "$REGION" --profile "$PROFILE" || echo "")
    fi
    
    # 1. Eliminar RDS
    echo "Eliminando Instancia RDS '$DB_INSTANCE_ID'..."
    aws rds delete-db-instance \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --skip-final-snapshot \
        --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "RDS ya eliminado o no encontrado."
    
    echo "Esperando que el RDS se elimine..."
    aws rds wait db-instance-deleted \
        --db-instance-identifier "$DB_INSTANCE_ID" \
        --region "$REGION" --profile "$PROFILE" 2>/dev/null || true

    # 2. Eliminar DB Subnet Group
    echo "Eliminando DB Subnet Group '$RDS_SUBNET_GROUP_NAME'..."
    aws rds delete-db-subnet-group --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "DB Subnet Group ya eliminado o no encontrado."

    # 3. Eliminar Security Group
    if [ -n "$SG_ID" ]; then
        echo "Eliminando Security Group '$SG_ID'..."
        aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "SG ya eliminado o no encontrado."
    fi

    # 4. Desasociar y eliminar Tabla de Ruta, Subredes, IGW y VPC
    if [ -n "$VPC_ID" ]; then
        # Subredes (obtener IDs en modo destroy)
        SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query 'Subnets[].SubnetId' --output text --region "$REGION" --profile "$PROFILE")

        # Tabla de Ruta (obtener IDs en modo destroy)
        RTB_ID=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" --query 'RouteTables[0].RouteTableId' --output text --region "$REGION" --profile "$PROFILE" || echo "")

        # Eliminar Rutas y Desasociar/Eliminar RTB
        if [ -n "$RTB_ID" ]; then
            for SUBNET in $SUBNETS; do
                RTB_ASSOC_ID=$(aws ec2 describe-route-tables --route-table-ids "$RTB_ID" --query "RouteTables[0].Associations[?SubnetId=='$SUBNET'].RouteTableAssociationId" --output text --region "$REGION" --profile "$PROFILE" 2>/dev/null)
                if [ -n "$RTB_ASSOC_ID" ]; then
                    aws ec2 disassociate-route-table --association-id "$RTB_ASSOC_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null
                fi
            done
            aws ec2 delete-route --route-table-id "$RTB_ID" --destination-cidr-block 0.0.0.0/0 --region "$REGION" --profile "$PROFILE" 2>/dev/null || true
            aws ec2 delete-route-table --route-table-id "$RTB_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "Tabla de Ruta ya eliminada o no encontrada."
        fi

        # Eliminar Subredes
        for SUBNET in $SUBNETS; do
            echo "Eliminando Subred '$SUBNET'..."
            aws ec2 delete-subnet --subnet-id "$SUBNET" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "Subred ya eliminada o no encontrada."
        done

        # Eliminar Internet Gateway
        if [ -n "$IGW_ID" ]; then
            echo "Desadjuntando y eliminando Internet Gateway '$IGW_ID'..."
            aws ec2 detach-internet-gateway --vpc-id "$VPC_ID" --internet-gateway-id "$IGW_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null
            aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "IGW ya eliminado o no encontrado."
        fi

        # Eliminar VPC
        echo "Eliminando VPC '$VPC_ID'..."
        aws ec2 delete-vpc --vpc-id "$VPC_ID" --region "$REGION" --profile "$PROFILE" 2>/dev/null || echo "VPC ya eliminada o no encontrada."
    fi

    log_section "LIMPIEZA COMPLETA"
    echo "Todos los recursos temporales han sido eliminados."
    echo "--------------------------------------------------------------------------------"
}

# --- Flujo de Ejecución Principal ---
if [ "$1" == "destroy" ]; then
    cleanup_resources
else
    setup_network
    setup_security_group
    setup_rds_subnet_group
    create_rds_instance
fi
