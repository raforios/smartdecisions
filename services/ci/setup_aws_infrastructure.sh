#!/bin/bash

# 'setup_aws_infrastructure.sh': Crea la red central de AWS (VPC, Subnets, SGs)
# para la arquitectura de microservicios, excluyendo la creación automática de RDS.

set -e          # Terminar inmediatamente si un comando falla.
set -o pipefail # Terminar si un comando en un pipeline falla.

# --- Verificación de Variables (Cargadas por manage_infrastructure.sh) ---
: ${REGION:?"Error: REGION no está configurada en el entorno."}
: ${VPC_CIDR:?"Error: VPC_CIDR no está configurada en el entorno."}
: ${PROJECT_TAG:?"Error: PROJECT_TAG no está configurada en el entorno."}

# --- Configuración Derivada (AÑADIDAS AZ C y AZ D) ---
AZ_A="${REGION}a"
AZ_B="${REGION}b"
AZ_C="${REGION}c" # Nueva AZ para aumentar capacidad RDS
AZ_D="${REGION}d" # Nueva AZ para aumentar capacidad RDS

# Nombres de recursos dinámicos
VPC_NAME="${PROJECT_TAG}-VPC"
INTERNAL_SG_NAME="${PROJECT_TAG}-lambda-to-rds-sg"
RDS_SG_NAME="${PROJECT_TAG}-rds-mysql-sg"
PUBLIC_SG_NAME="${PROJECT_TAG}-ec2-public-sg"

# --- Derivación de CIDR de Subredes (Lógica Interna) ---
VPC_BASE_PREFIX=$(echo "$VPC_CIDR" | cut -d'.' -f1-2)
VPC_BASE_OCTET=$(echo "$VPC_CIDR" | cut -d'.' -f4 | cut -d'/' -f1)

# Asignación de CIDR fijos para una red de ejemplo (ej. 192.168.X.0/24)
PUBLIC_SUBNET_A_CIDR="${VPC_BASE_PREFIX}.1.0/24"
PUBLIC_SUBNET_B_CIDR="${VPC_BASE_PREFIX}.2.0/24"
PRIVATE_SUBNET_A_CIDR="${VPC_BASE_PREFIX}.10.0/24"
PRIVATE_SUBNET_B_CIDR="${VPC_BASE_PREFIX}.11.0/24"
# CIDRS ADICIONALES PARA MÁS CAPACIDAD RDS
PRIVATE_SUBNET_C_CIDR="${VPC_BASE_PREFIX}.12.0/24" 
PRIVATE_SUBNET_D_CIDR="${VPC_BASE_PREFIX}.13.0/24"

# --- Funciones de Utilidad (sin cambios) ---

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

get_public_ip() {
    local user_ip
    user_ip=$(curl -s http://checkip.amazonaws.com)/32
    if [ $? -ne 0 ] || [ -z "$user_ip" ]; then
        echo "Error: 'No se pudo obtener la dirección IP pública.'" >&2
        exit 1
    fi
    echo "$user_ip"
}

get_resource_id() {
    local resource_type="$1"
    local name_tag="$2"
    local query_string
    local aws_subcommand
    
    case "$resource_type" in
        "vpc")
            aws_subcommand="vpcs"
            query_string="Vpcs[0].VpcId"
            ;;
        "subnet")
            aws_subcommand="subnets"
            query_string="Subnets[0].SubnetId"
            ;;
        "sg")
            aws_subcommand="security-groups"
            query_string="SecurityGroups[0].GroupId"
            ;;
        "rtb")
            aws_subcommand="route-tables"
            query_string="RouteTables[0].RouteTableId"
            ;;
        *)
            echo "Error: 'Tipo de recurso no soportado $resource_type'." >&2
            return 1
            ;;
    esac

    # Se ejecuta el comando de búsqueda con el filtro de nombre.
    aws ec2 describe-"$aws_subcommand" \
        --filters "Name=tag:Name,Values=$name_tag" \
        --query "$query_string" \
        --output text \
        --region "$REGION" | tr -d '\n' | sed 's/None//g'
}

# --- Funciones Principales ---

manage_vpc() {
# (Sin cambios, tu lógica es correcta aquí)
    log_section "CONFIGURACIÓN DE VPC Y GATEWAY DE INTERNET"

    VPC_ID=$(get_resource_id "vpc" "$VPC_NAME")
    
    if [ -z "$VPC_ID" ]; then
        echo "VPC '$VPC_NAME' no encontrada. Creando..."
        VPC_ID=$(aws ec2 create-vpc \
            --cidr-block "$VPC_CIDR" \
            --query 'Vpc.VpcId' \
            --output text \
            --region "$REGION")

        aws ec2 create-tags \
            --resources "$VPC_ID" \
            --tags Key=Name,Value="$VPC_NAME" Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"
        echo "VPC '$VPC_ID' creada."

        # 4. Habilitar DNS Support y DNS Hostnames (CRÍTICO para VPC Endpoints de Interface)
        echo "Habilitando DNS en VPC..."
        aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-support "{\"Value\":true}" --region "$REGION"
        aws ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames "{\"Value\":true}" --region "$REGION"
        echo "DNS Support y Hostnames habilitados en VPC."

    else
        echo "VPC '$VPC_NAME' ya existe con ID: $VPC_ID."
    fi

    # Create and attach Internet Gateway (IGW)
    IGW_ID=$(aws ec2 describe-internet-gateways \
        --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
        --query 'InternetGateways[0].InternetGatewayId' \
        --output text \
        --region "$REGION" | tr -d '\n' | sed 's/None//g')

    if [ -z "$IGW_ID" ]; then
        echo "Internet Gateway no encontrado para VPC. Creando y adjuntando..."
        IGW_ID=$(aws ec2 create-internet-gateway \
            --query 'InternetGateway.InternetGatewayId' \
            --output text \
            --region "$REGION")

        aws ec2 attach-internet-gateway \
            --internet-gateway-id "$IGW_ID" \
            --vpc-id "$VPC_ID" \
            --region "$REGION"
        
        aws ec2 create-tags \
            --resources "$IGW_ID" \
            --tags Key=Name,Value="${PROJECT_TAG}-IGW" Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"
        echo "Internet Gateway '$IGW_ID' creado y adjuntado."
        
        export IGW_ID

    else
        echo "Internet Gateway '$IGW_ID' ya adjuntado."
    fi

    export VPC_ID
}

manage_subnets() {
    log_section "CREACIÓN DE SUBREDES"

    # Definir array de subredes: "NombreDescriptivo:CIDR:AZ:Tipo"
    # AÑADIDAS PRIVATE-C Y PRIVATE-D PARA MAYOR CAPACIDAD RDS
    SUBNET_CONFIG=(
        "Public-A:${PUBLIC_SUBNET_A_CIDR}:${AZ_A}:Public"
        "Public-B:${PUBLIC_SUBNET_B_CIDR}:${AZ_B}:Public"
        "Private-A:${PRIVATE_SUBNET_A_CIDR}:${AZ_A}:Private"
        "Private-B:${PRIVATE_SUBNET_B_CIDR}:${AZ_B}:Private"
        "Private-C:${PRIVATE_SUBNET_C_CIDR}:${AZ_C}:Private"
        "Private-D:${PRIVATE_SUBNET_D_CIDR}:${AZ_D}:Private"
    )

    PUBLIC_SUBNETS=()
    PRIVATE_SUBNETS=()

    for config in "${SUBNET_CONFIG[@]}"; do
        IFS=':' read -r NAME CIDR AZ TYPE <<< "$config"
        SUBNET_TAG_NAME="${PROJECT_TAG}-Subnet-$NAME"
        
        SUBNET_ID=$(get_resource_id "subnet" "$SUBNET_TAG_NAME")

        if [ -z "$SUBNET_ID" ]; then
            echo "Subnet '$SUBNET_TAG_NAME' no encontrada. Creando con CIDR $CIDR..."
            SUBNET_ID=$(aws ec2 create-subnet \
                --vpc-id "$VPC_ID" \
                --cidr-block "$CIDR" \
                --availability-zone "$AZ" \
                --query 'Subnet.SubnetId' \
                --output text \
                --region "$REGION")

            aws ec2 create-tags \
                --resources "$SUBNET_ID" \
                --tags Key=Name,Value="$SUBNET_TAG_NAME" Key=Project,Value="$PROJECT_TAG" \
                --region "$REGION" > /dev/null

            if [ "$TYPE" = "Public" ]; then
                aws ec2 modify-subnet-attribute \
                    --subnet-id "$SUBNET_ID" \
                    --map-public-ip-on-launch \
                    --region "$REGION" > /dev/null
                
                echo "Asignación automática de IP pública habilitada en Subred '$SUBNET_TAG_NAME'."
            fi
            
        else
            echo "Subnet '$SUBNET_TAG_NAME' ya existe con ID: $SUBNET_ID."
        fi

        # --- Etiqueta de convención para RDS DB Subnet Group (CRÍTICO para que RDS acepte las subredes) ---
        aws ec2 create-tags \
            --resources "$SUBNET_ID" \
            --tags Key=Purpose,Value=rds-db-subnet-group-tagging \
            --region "$REGION" > /dev/null

        if [ "$TYPE" = "Public" ]; then
            PUBLIC_SUBNETS+=("$SUBNET_ID")
        else
            PRIVATE_SUBNETS+=("$SUBNET_ID")
        fi
    done

    # Exportar IDs de Subredes
    # El uso de 'echo "${ARRAY[@]}"' convierte el array en una lista separada por espacios, 
    # lo cual es útil para pasar a scripts posteriores.
    export PUBLIC_SUBNET_IDS=$(echo "${PUBLIC_SUBNETS[@]}")
    export PRIVATE_SUBNET_IDS=$(echo "${PRIVATE_SUBNETS[@]}")
    export PUBLIC_SUBNET_A="${PUBLIC_SUBNETS[0]}"
    export PRIVATE_SUBNET_A="${PRIVATE_SUBNETS[0]}"
}

manage_route_tables() {
    log_section "TABLAS DE RUTA Y NAT GATEWAY"

    # Obtener IGW ID 
    if [ -z "$IGW_ID" ]; then 
        echo "Error: IGW ID no encontrado. La creación falló en manage_vpc o la variable no se exportó." >&2
        exit 1
    fi

    # --- Tabla de Ruta Pública (RTB) ---
    PUB_RTB_NAME="${PROJECT_TAG}-Public-RTB"
    PUB_RTB_ID=$(get_resource_id "rtb" "$PUB_RTB_NAME")

    if [ -z "$PUB_RTB_ID" ]; then
        echo "Tabla de Ruta Pública '$PUB_RTB_NAME' no encontrada. Creando..."
        PUB_RTB_ID=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --query 'RouteTable.RouteTableId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$PUB_RTB_ID" --tags Key=Name,Value="$PUB_RTB_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"
        
        # Añadir ruta a IGW
        aws ec2 create-route --route-table-id "$PUB_RTB_ID" --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" --region "$REGION" > /dev/null
        echo "Ruta a IGW añadida a RTB Pública."
        echo "Esperando 10 segundos para que la ruta IGW se propague..."
        sleep 10 

        # 1. Obtener el ID de la asociación de la Tabla de Ruta Principal actual
        local MAIN_RTB_ASSOC_ID=$(aws ec2 describe-route-tables \
            --filters Name=vpc-id,Values="$VPC_ID" Name=association.main,Values=true \
            --query 'RouteTables[0].Associations[0].RouteTableAssociationId' \
            --output text --region "$REGION" | tr -d '\n')
        
        # 2. Reemplazar la asociación de la Tabla de Ruta Principal por nuestra RTB Pública
        if [ -n "$MAIN_RTB_ASSOC_ID" ]; then
            aws ec2 replace-route-table-association \
                --association-id "$MAIN_RTB_ASSOC_ID" \
                --route-table-id "$PUB_RTB_ID" \
                --region "$REGION" > /dev/null
            echo "RTB Pública '$PUB_RTB_NAME' reemplazó la Tabla de Ruta Principal (Main) de la VPC."
        else
            # Si no había una asociación principal (lo cual es raro), simplemente asociamos la nuestra
            aws ec2 associate-route-table --route-table-id "$PUB_RTB_ID" --vpc-id "$VPC_ID" --region "$REGION" > /dev/null
            echo "RTB Pública '$PUB_RTB_NAME' establecida como Tabla de Ruta Principal (Main) de la VPC."
        fi
        # ***************************************************************


    else
        echo "Tabla de Ruta Pública '$PUB_RTB_NAME' ya existe."
    fi
    
    # Asociar RTB Pública con Subredes Públicas
    # NOTA: PUBLIC_SUBNET_IDS ahora es una cadena separada por espacios
    for subnet_id in $PUBLIC_SUBNET_IDS; do
        if aws ec2 describe-route-tables --route-table-id "$PUB_RTB_ID" --filters "Name=association.subnet-id,Values=$subnet_id" --query 'RouteTables[].Associations[].RouteTableAssociationId' --output text --region "$REGION" | grep -q 'rtbassoc'; then
            echo "RTB Pública ya asociada con Subred '$subnet_id'."
        else
            aws ec2 associate-route-table --route-table-id "$PUB_RTB_ID" --subnet-id "$subnet_id" --region "$REGION" > /dev/null
            echo "RTB Pública asociada con Subred '$subnet_id'."
        fi
    done
    
    # --- NAT Gateway ---
    NAT_GW_NAME="${PROJECT_TAG}-NAT-GW-A"
    NAT_GW_ID=$(aws ec2 describe-nat-gateways \
        --filter "Name=tag:Name,Values=$NAT_GW_NAME" "Name=vpc-id,Values=$VPC_ID" \
        --query 'NatGateways[0].NatGatewayId' \
        --output text \
        --region "$REGION" | tr -d '\n' | sed 's/None//g' || true)

    if [ -z "$NAT_GW_ID" ]; then
        echo "NAT Gateway '$NAT_GW_NAME' no encontrado. Asignando EIP y creando NAT Gateway..."
         
        # Asignar EIP
        EIP_ALLOCATION_ID=$(aws ec2 allocate-address --domain vpc --query 'AllocationId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$EIP_ALLOCATION_ID" --tags Key=Name,Value="${PROJECT_TAG}-NAT-EIP" Key=Project,Value="$PROJECT_TAG" --region "$REGION"

        # Crear NAT Gateway en Subred Pública A
        NAT_GW_ID=$(aws ec2 create-nat-gateway \
            --subnet-id "$PUBLIC_SUBNET_A" \
            --allocation-id "$EIP_ALLOCATION_ID" \
            --query 'NatGateway.NatGatewayId' \
            --output text \
            --region "$REGION")
        
        aws ec2 create-tags --resources "$NAT_GW_ID" --tags Key=Name,Value="$NAT_GW_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"

        echo "Esperando a que NAT Gateway '$NAT_GW_ID' esté disponible..."
        aws ec2 wait nat-gateway-available --nat-gateway-ids "$NAT_GW_ID" --region "$REGION"

        echo "NAT Gateway '$NAT_GW_ID' creado y activo."
    else
        echo "NAT Gateway '$NAT_GW_NAME' ya existe con ID: $NAT_GW_ID."
    fi

    # --- Tabla de Ruta Privada (RTB) ---
    PRIV_RTB_NAME="${PROJECT_TAG}-Private-RTB"
    PRIV_RTB_ID=$(get_resource_id "rtb" "$PRIV_RTB_NAME")

    if [ -z "$PRIV_RTB_ID" ]; then
        echo "Tabla de Ruta Privada '$PRIV_RTB_NAME' no encontrada. Creando..."
        PRIV_RTB_ID=$(aws ec2 create-route-table --vpc-id "$VPC_ID" --query 'RouteTable.RouteTableId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$PRIV_RTB_ID" --tags Key=Name,Value="$PRIV_RTB_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"
        
        # Añadir ruta a NAT Gateway
        aws ec2 create-route --route-table-id "$PRIV_RTB_ID" --destination-cidr-block 0.0.0.0/0 --nat-gateway-id "$NAT_GW_ID" --region "$REGION" > /dev/null
        echo "Ruta a NAT Gateway añadida a RTB Privada."
    else
        echo "Tabla de Ruta Privada '$PRIV_RTB_NAME' ya existe."
    fi
    
    # Asociar RTB Privada con TODAS las Subredes Privadas (ahora hay 4)
    # NOTA: PRIVATE_SUBNET_IDS ahora es una cadena separada por espacios
    for subnet_id in $PRIVATE_SUBNET_IDS; do
        if aws ec2 describe-route-tables --route-table-id "$PRIV_RTB_ID" --filters "Name=association.subnet-id,Values=$subnet_id" --query 'RouteTables[].Associations[].RouteTableAssociationId' --output text --region "$REGION" | grep -q 'rtbassoc'; then
            echo "RTB Privada ya asociada con Subred '$subnet_id'."
        else
            aws ec2 associate-route-table --route-table-id "$PRIV_RTB_ID" --subnet-id "$subnet_id" --region "$REGION" > /dev/null
            echo "RTB Privada asociada con Subred '$subnet_id'."
        fi
    done
    
    export NAT_GW_ID
}

manage_private_endpoints() {
# (Sin cambios, tu lógica es correcta aquí)
    log_section "CONFIGURACIÓN DE VPC ENDPOINTS"
    
    # ---------------------------------------------------------------------------------
    # 1. CONFIGURACIÓN DEL VPC ENDPOINT DE GATEWAY S3
    # ---------------------------------------------------------------------------------
    local S3_ENDPOINT_NAME="API_BINARIA-S3-Endpoint"
    local PRIVATE_RTB_NAME="${PROJECT_TAG}-Private-RTB"

    local PRIVATE_RTB_ID=$(get_resource_id "rtb" "$PRIVATE_RTB_NAME")

    # Verificar si el Endpoint de S3 Gateway ya existe
    local S3_ENDPOINT_ID=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-endpoint-type,Values=Gateway" "Name=service-name,Values=com.amazonaws.$REGION.s3" \
        --query "VpcEndpoints[?Tags[?Key=='Name' && Value=='$S3_ENDPOINT_NAME']].VpcEndpointId" \
        --output text --region "$REGION" 2>/dev/null)

    if [ -z "$S3_ENDPOINT_ID" ]; then
        echo "VPC Endpoint S3 Gateway no encontrado. Creando y asociando a RTB privada..."
        
        local CREATE_OUTPUT=$(aws ec2 create-vpc-endpoint \
            --vpc-id "$VPC_ID" \
            --vpc-endpoint-type Gateway \
            --service-name "com.amazonaws.$REGION.s3" \
            --route-table-ids "$PRIVATE_RTB_ID" \
            --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=$S3_ENDPOINT_NAME}, {Key=Project,Value=$PROJECT_TAG}]" \
            --region "$REGION" 2>&1)
            
        if [ $? -ne 0 ]; then
            echo "Error fatal al crear el VPC Endpoint de S3 Gateway:" >&2
            echo "$CREATE_OUTPUT" >&2
            exit 1
        fi
        
        S3_ENDPOINT_ID=$(echo "$CREATE_OUTPUT" | grep 'VpcEndpointId' | awk -F': ' '{print $2}' | tr -d '",')
        
        echo "VPC Endpoint S3 '$S3_ENDPOINT_ID' creado. Esperando 10 segundos para la propagación de la ruta..."
        sleep 10
        echo "VPC Endpoint S3 disponible."
        
    else
        echo "VPC Endpoint S3 Gateway '$S3_ENDPOINT_ID' ya existe. Verificando asociación con RTB privada..."
        
        local RTB_ASSOCIATED=$(aws ec2 describe-vpc-endpoints \
            --vpc-endpoint-ids "$S3_ENDPOINT_ID" \
            --query "VpcEndpoints[0].RouteTableIds[]" \
            --output text --region "$REGION" 2>/dev/null | grep "$PRIVATE_RTB_ID")
            
        if [ -z "$RTB_ASSOCIATED" ]; then
            echo "Asociando VPC Endpoint S3 con RTB Privada '$PRIVATE_RTB_ID'..."
            aws ec2 modify-vpc-endpoint \
                --vpc-endpoint-id "$S3_ENDPOINT_ID" \
                --add-route-table-ids "$PRIVATE_RTB_ID" \
                --region "$REGION"
            echo "Asociación completada."
        else
            echo "VPC Endpoint S3 ya está asociado con RTB Privada."
        fi
    fi

    # ---------------------------------------------------------------------------------
    # 2. CONFIGURACIÓN DEL VPC ENDPOINT DE INTERFAZ EC2 (Necesario para la validación de red en Subredes Privadas)
    # ---------------------------------------------------------------------------------
    log_section "CONFIGURACIÓN DE VPC ENDPOINT EC2 INTERFACE"

    local EC2_ENDPOINT_NAME="API_BINARIA-EC2-Endpoint"
    local EC2_SERVICE_NAME="com.amazonaws.${REGION}.ec2"
    local INTERNAL_SG_NAME="${PROJECT_TAG}-lambda-to-rds-sg"
    
    # Obtener el ID del SG de Lambda para asociarlo al Endpoint
    local INTERNAL_SG_ID=$(get_resource_id "sg" "$INTERNAL_SG_NAME")

    # Requerir la lista de IDs de Subredes Privadas (separados por espacio)
    if [ -z "$PRIVATE_SUBNET_IDS" ]; then
        echo "Error: Las IDs de subredes privadas no están configuradas (PRIVATE_SUBNET_IDS). Fallando." >&2
        exit 1
    fi
    # El ID de las subredes se pasa como múltiples argumentos (sin comillas)
    local SUBNET_LIST_SPACED=$(echo "$PRIVATE_SUBNET_IDS")
    
    # Verificar si el Endpoint de EC2 Interface ya existe
    local EC2_ENDPOINT_ID=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-endpoint-type,Values=Interface" "Name=service-name,Values=$EC2_SERVICE_NAME" \
        --query "VpcEndpoints[?Tags[?Key=='Name' && Value=='$EC2_ENDPOINT_NAME']].VpcEndpointId" \
        --output text \
        --region "$REGION" 2>/dev/null)

    if [ -z "$EC2_ENDPOINT_ID" ]; then
        echo "VPC Endpoint EC2 Interface no encontrado. Creando en subredes privadas con SG de Lambda..."
        
        # CRÍTICO: Se eliminan las comillas de $SUBNET_LIST_SPACED para que el shell lo divida en múltiples IDs.
        local CREATE_OUTPUT=$(aws ec2 create-vpc-endpoint \
            --vpc-id "$VPC_ID" \
            --vpc-endpoint-type Interface \
            --service-name "$EC2_SERVICE_NAME" \
            --subnet-ids $SUBNET_LIST_SPACED \
            --security-group-ids "$INTERNAL_SG_ID" \
            --tag-specifications "ResourceType=vpc-endpoint,Tags=[{Key=Name,Value=$EC2_ENDPOINT_NAME}, {Key=Project,Value=$PROJECT_TAG}]" \
            --query 'VpcEndpoint.VpcEndpointId' \
            --output text \
            --region "$REGION" 2>&1)
            
        if [ $? -ne 0 ]; then
            echo "Error fatal al crear el VPC Endpoint de EC2 Interface:" >&2
            echo "$CREATE_OUTPUT" >&2
            exit 1
        fi
        
        EC2_ENDPOINT_ID="$CREATE_OUTPUT"
        
        echo "VPC Endpoint EC2 '$EC2_ENDPOINT_ID' creado. Esperando 10 segundos para la propagación..."
        sleep 10
        echo "VPC Endpoint EC2 disponible."
        
    else
        echo "VPC Endpoint EC2 Interface '$EC2_ENDPOINT_ID' ya existe."
    fi
    
    return 0
}

manage_security_groups() {
# (Sin cambios, tu lógica es correcta aquí)
    log_section "CONFIGURACIÓN DE GRUPOS DE SEGURIDAD (SG)"

    USER_PUBLIC_IP=$(get_public_ip)
    echo "Su IP pública para reglas de acceso es: $USER_PUBLIC_IP"

    # --- 1. SG Interno Lambda a RDS ---
    INT_SG_ID=$(get_resource_id "sg" "$INTERNAL_SG_NAME")

    if [ -z "$INT_SG_ID" ]; then
        echo "SG '$INTERNAL_SG_NAME' no encontrado. Creando..."
        INT_SG_ID=$(aws ec2 create-security-group \
            --group-name "$INTERNAL_SG_NAME" \
            --description "SG interno para ENIs de Lambda para conectar a RDS" \
            --vpc-id "$VPC_ID" \
            --query 'GroupId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$INT_SG_ID" --tags Key=Name,Value="$INTERNAL_SG_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"
        echo "SG '$INTERNAL_SG_NAME' creado con ID: $INT_SG_ID."
    else
        echo "SG '$INTERNAL_SG_NAME' ya existe con ID: $INT_SG_ID."
    fi

    # --- 2. SG de RDS MySQL ---
    RDS_SG_ID=$(get_resource_id "sg" "$RDS_SG_NAME")


    if [ -z "$RDS_SG_ID" ]; then
        echo "SG '$RDS_SG_NAME' no encontrado. Creando..."
        RDS_SG_ID=$(aws ec2 create-security-group \
            --group-name "$RDS_SG_NAME" \
            --description "Acceso RDS MySQL para Lambda y GUI externo" \
            --vpc-id "$VPC_ID" \
            --query 'GroupId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$RDS_SG_ID" --tags Key=Name,Value="$RDS_SG_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"
        echo "SG '$RDS_SG_NAME' creado con ID: $RDS_SG_ID."
    else
        echo "SG '$RDS_SG_NAME' ya existe con ID: $RDS_SG_ID."
    fi
    
    # Regla 1: Permitir Lambda (origen: INT_SG_ID) a puerto 3306 (Preparación para RDS manual)
    if ! aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --filters Name=ip-permission.protocol,Values=tcp Name=ip-permission.from-port,Values=3306 Name=ip-permission.to-port,Values=3306 Name=ip-permission.group-id,Values="$INT_SG_ID" \
        --query 'SecurityGroups[].IpPermissions[].UserIdGroupPairs[]' \
        --output text \
        --region "$REGION" | grep -q 'sg-' ; then 
        
        aws ec2 authorize-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 3306 \
            --source-group "$INT_SG_ID" \
            --region "$REGION" > /dev/null
        echo "Regla Ingress añadida a '$RDS_SG_NAME': Permitir desde Lambda SG '$INTERNAL_SG_NAME' (3306)."
    else
        echo "Regla Ingress ya existe en '$RDS_SG_NAME': Permitir desde Lambda SG '$INTERNAL_SG_NAME'."
    fi

    # Regla 2: Permitir IP pública del usuario a puerto 3306 (Preparación para RDS manual)
    if [ -z "$(aws ec2 describe-security-groups \
        --group-ids "$RDS_SG_ID" \
        --filters Name=ip-permission.protocol,Values=tcp Name=ip-permission.from-port,Values=3306 Name=ip-permission.to-port,Values=3306 Name=ip-permission.cidr,Values="$USER_PUBLIC_IP" \
        --query 'SecurityGroups[0].IpPermissions[0].IpRanges[0].CidrIp' \
        --output text \
        --region "$REGION" 2>/dev/null)" ]; then
        
        aws ec2 authorize-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 3306 \
            --cidr "$USER_PUBLIC_IP" \
            --region "$REGION" > /dev/null
        echo "Regla Ingress añadida a '$RDS_SG_NAME': Permitir desde IP pública del usuario '$USER_PUBLIC_IP' (3306)."
    else
        echo "Regla Ingress ya existe en '$RDS_SG_NAME': Permitir desde IP pública del usuario."
    fi

    # --- 3. SG Público de EC2 ---
    PUB_SG_ID=$(get_resource_id "sg" "$PUBLIC_SG_NAME")

    if [ -z "$PUB_SG_ID" ]; then
        echo "SG '$PUBLIC_SG_NAME' no encontrado. Creando..."
        PUB_SG_ID=$(aws ec2 create-security-group \
            --group-name "$PUBLIC_SG_NAME" \
            --description "Acceso publico para EC2 (SSH/HTTP/HTTPS)" \
            --vpc-id "$VPC_ID" \
            --query 'GroupId' --output text --region "$REGION")
        aws ec2 create-tags --resources "$PUB_SG_ID" --tags Key=Name,Value="$PUBLIC_SG_NAME" Key=Project,Value="$PROJECT_TAG" --region "$REGION"
        echo "SG '$PUBLIC_SG_NAME' creado con ID: $PUB_SG_ID."
    else
        echo "SG '$PUBLIC_SG_NAME' ya existe con ID: $PUB_SG_ID."
    fi
    
    # Regla 1: SSH (22) desde IP pública del usuario
    if [ -z "$(aws ec2 describe-security-groups \
        --group-ids "$PUB_SG_ID" \
        --filters Name=ip-permission.protocol,Values=tcp Name=ip-permission.from-port,Values=22 Name=ip-permission.to-port,Values=22 Name=ip-permission.cidr,Values="$USER_PUBLIC_IP" \
        --query 'SecurityGroups[0].IpPermissions[0].IpRanges[0].CidrIp' \
        --output text \
        --region "$REGION" 2>/dev/null)" ]; then
        
        aws ec2 authorize-security-group-ingress \
            --group-id "$PUB_SG_ID" \
            --protocol tcp \
            --port 22 \
            --cidr "$USER_PUBLIC_IP" \
            --region "$REGION" > /dev/null
        echo "Regla Ingress añadida a '$PUBLIC_SG_NAME': Permitir SSH desde IP pública del usuario."
    else
        echo "Regla Ingress ya existe en '$PUBLIC_SG_NAME': Permitir SSH desde IP pública del usuario."
    fi

    # Regla 2: HTTP (80) y HTTPS (443) desde cualquier lugar
    if [ -z "$(aws ec2 describe-security-groups \
        --group-ids "$PUB_SG_ID" \
        --filters Name=ip-permission.protocol,Values=tcp Name=ip-permission.from-port,Values=80 Name=ip-permission.to-port,Values=80 Name=ip-permission.cidr,Values=0.0.0.0/0 \
        --query 'SecurityGroups[0].IpPermissions[0].IpRanges[0].CidrIp' \
        --output text \
        --region "$REGION" 2>/dev/null)" ]; then
        
        # HTTP
        aws ec2 authorize-security-group-ingress \
            --group-id "$PUB_SG_ID" \
            --protocol tcp \
            --port 80 \
            --cidr "0.0.0.0/0" \
            --region "$REGION" > /dev/null
        # HTTPS
        aws ec2 authorize-security-group-ingress \
            --group-id "$PUB_SG_ID" \
            --protocol tcp \
            --port 443 \
            --cidr "0.0.0.0/0" \
            --region "$REGION" > /dev/null
        echo "Reglas Ingress añadidas a '$PUBLIC_SG_NAME': Permitir HTTP/HTTPS desde cualquier lugar."
    else
        echo "Reglas Ingress ya existen en '$PUBLIC_SG_NAME': Permitir HTTP/HTTPS."
    fi

    export INT_SG_ID
    export RDS_SG_ID
    export PUB_SG_ID
}


# --- Flujo de Ejecución Principal ---

# 1. Infraestructura de Red
manage_vpc
manage_subnets
manage_security_groups
manage_route_tables
manage_private_endpoints

export SG_RDS_ID="$RDS_SG_ID"
# --- Salida Final ---
log_section "CREACIÓN DE INFRAESTRUCTURA CORE COMPLETADA"
echo "VPC ID: $VPC_ID"
echo "Internal Lambda SG ID: $INT_SG_ID (Usar en la configuración VPC de Lambda!)"
echo "EC2 Public SG ID: $PUB_SG_ID"
echo "Private Subnets for RDS/Lambda: $PRIVATE_SUBNET_IDS (Ahora incluye C y D)"
echo "--------------------------------------------------------------------------------"
echo "NOTA: Los IDs de SG y Subredes Privadas son necesarios para la creación manual de RDS."
echo "SG de RDS (Necesario para la creación manual): $RDS_SG_ID"
echo "--------------------------------------------------------------------------------"
echo "Próximo Paso: Ahora el script 'manage_infrastructure.sh' actualizará los IDs"
echo "en 'infrastructure.config' para el despliegue de Lambdas y API Gateway."
