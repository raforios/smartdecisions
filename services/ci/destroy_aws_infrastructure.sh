#!/bin/bash

# 'destroy_aws_infrastructure.sh': Elimina todos los recursos de AWS creados por los scripts de IaC.
# 'Nota': Este script se basa en la variable de entorno '$PROJECT_TAG' para la identificación.

set -e
set -o pipefail

# --- Verificación de Variables (Cargadas por manage_infrastructure.sh) ---
: ${REGION:?"Error: REGION no está configurada en el entorno."}
: ${PROJECT_TAG:?"Error: PROJECT_TAG no está configurada en el entorno."}
: ${KEY_PAIR_NAME:?"Error: KEY_PAIR_NAME no está configurada."}

# --- Configuración Derivada (debe coincidir con setup_aws_infrastructure.sh y setup_api_gateway.sh) ---
PROJECT_TAG_FILTER="Project=${PROJECT_TAG}"
DB_INSTANCE_ID="${PROJECT_TAG}-mysql-db"
RDS_SUBNET_GROUP_NAME="${PROJECT_TAG}-rds-subnet-group"

# API Gateway y IAM (Nombres de recursos fijos)
API_NAME="${PROJECT_TAG}-ApiGateway-Microservices"
API_SERVICE_ROLE_NAME="ApiGatewayLambdaInvocationRole"
INVOCATION_POLICY_NAME="ApiGatewayInvokeLambdasPolicy"

# --- Funciones de Utilidad ---
log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# --- Funciones Principales: Destrucción en Orden Inverso ---

# 'destroy_ec2_resources': Termina la instancia EC2 y elimina el Key Pair.
destroy_ec2_resources() {
    log_section "ELIMINANDO INSTANCIAS EC2 Y PAR DE CLAVES"
    
    # Buscar instancias EC2 por la etiqueta PROJECT_TAG
    local INSTANCE_IDS=$(aws ec2 describe-instances \
        --filters "Name=tag-key,Values=Project" "Name=tag-value,Values=$PROJECT_TAG" "Name=instance-state-name,Values=running,pending,stopped" \
        --query 'Reservations[].Instances[].InstanceId' \
        --output text \
        --region "$REGION" || true)

    if [ -n "$INSTANCE_IDS" ]; then
        echo "Terminando instancias EC2: $INSTANCE_IDS"
        aws ec2 terminate-instances --instance-ids "$INSTANCE_IDS" --region "$REGION" > /dev/null
        echo "Esperando a que las instancias EC2 terminen..."
        aws ec2 wait instance-terminated --instance-ids "$INSTANCE_IDS" --region "$REGION"
    else
        echo "No se encontraron instancias EC2 etiquetadas con '$PROJECT_TAG'."
    fi

    # Eliminar Par de Claves (usando la variable $KEY_PAIR_NAME)
    if aws ec2 describe-key-pairs --key-names "$KEY_PAIR_NAME" --region "$REGION" 2>/dev/null; then
        echo "Eliminando Par de Claves: $KEY_PAIR_NAME"
        aws ec2 delete-key-pair --key-name "$KEY_PAIR_NAME" --region "$REGION"
        rm -f "./${KEY_PAIR_NAME}.pem" 2>/dev/null
    else
        echo "Par de Claves '$KEY_PAIR_NAME' no encontrado."
    fi
}

# 'destroy_rds_resources': Elimina la instancia RDS y el Subnet Group.
destroy_rds_resources() {
    log_section "ELIMINANDO INSTANCIA RDS Y GRUPO DE SUBRED"
    
    # Usar variable $DB_INSTANCE_ID
    if aws rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION" 2>/dev/null; then
        echo "Eliminando instancia RDS '$DB_INSTANCE_ID'. 'Omitir instantánea final' activado."
        aws rds delete-db-instance \
            --db-instance-identifier "$DB_INSTANCE_ID" \
            --skip-final-snapshot \
            --region "$REGION" > /dev/null
        
        echo "Esperando a que la instancia RDS sea eliminada (5-10 minutos)..."
        aws rds wait db-instance-deleted --db-instance-identifier "$DB_INSTANCE_ID" --region "$REGION"
    else
        echo "Instancia RDS '$DB_INSTANCE_ID' no encontrada."
    fi

    # Usar variable $RDS_SUBNET_GROUP_NAME
    if aws rds describe-db-subnet-groups --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" --region "$REGION" 2>/dev/null; then
        echo "Eliminando Grupo de Subred RDS: $RDS_SUBNET_GROUP_NAME"
        aws rds delete-db-subnet-group --db-subnet-group-name "$RDS_SUBNET_GROUP_NAME" --region "$REGION"
    else
        echo "Grupo de Subred RDS '$RDS_SUBNET_GROUP_NAME' no encontrado."
    fi
}

# 'destroy_api_gateway': Elimina el API Gateway REST y el rol/política IAM asociado.
destroy_api_gateway() {
    log_section "ELIMINANDO API GATEWAY Y ROL IAM"

    # 1. Eliminar API Gateway (usando la variable $API_NAME)
    local API_ID=$(aws apigateway get-rest-apis \
        --query "items[?name=='$API_NAME'].id" \
        --output text \
        --region "$REGION" || true)

    if [ -n "$API_ID" ]; then
        echo "Eliminando API Gateway '$API_ID'..."
        aws apigateway delete-rest-api --rest-api-id "$API_ID" --region "$REGION"
    else
        echo "API Gateway '$API_NAME' no encontrado."
    fi
    
    # 2. Eliminar Política y Rol IAM para API Gateway (usando nombres fijos)
    if aws iam get-role --role-name "$API_SERVICE_ROLE_NAME" --region "$REGION" 2>/dev/null; then
        echo "Eliminando Rol y Política IAM para API Gateway..."
        
        # Desasociar y eliminar política
        local POLICY_ARN=$(aws iam list-policies --scope Local --query "Policies[?PolicyName=='$INVOCATION_POLICY_NAME'].Arn" --output text --region "$REGION" || true)
        if [ -n "$POLICY_ARN" ]; then
            aws iam detach-role-policy --role-name "$API_SERVICE_ROLE_NAME" --policy-arn "$POLICY_ARN" --region "$REGION"
            aws iam delete-policy --policy-arn "$POLICY_ARN" --region "$REGION"
        fi
        
        # Eliminar rol
        aws iam delete-role --role-name "$API_SERVICE_ROLE_NAME" --region "$REGION"
    else
        echo "Rol IAM '$API_SERVICE_ROLE_NAME' no encontrado."
    fi
}

# 'destroy_network_resources': Elimina NAT, Tablas de Ruta, SG, Subredes, y VPC.
destroy_network_resources() {
    log_section "ELIMINANDO RECURSOS DE RED (NAT, RTB, SG, SUBNETS, VPC)"

    # Buscar VPC por la etiqueta PROJECT_TAG
    local VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Project,Values=$PROJECT_TAG" --query 'Vpcs[0].VpcId' --output text --region "$REGION" || true)
    if [ -z "$VPC_ID" ]; then
        echo "VPC etiquetada con '$PROJECT_TAG' no encontrada. Se omite la limpieza de red."
        return
    fi
    echo "VPC ID encontrado: $VPC_ID. Iniciando limpieza..."

    # 1. Eliminar NAT Gateway (y EIP asociado)
    local NAT_GW_ID=$(aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=$PROJECT_TAG" --query 'NatGateways[0].NatGatewayId' --output text --region "$REGION" || true)
    if [ -n "$NAT_GW_ID" ]; then
        local EIP_ALLOCATION_ID=$(aws ec2 describe-nat-gateways --nat-gateway-ids "$NAT_GW_ID" --query 'NatGateways[0].NatGatewayAddresses[0].AllocationId' --output text --region "$REGION" || true)
        
        echo "Eliminando NAT Gateway: $NAT_GW_ID"
        aws ec2 delete-nat-gateway --nat-gateway-id "$NAT_GW_ID" --region "$REGION" > /dev/null
        echo "Esperando a que NAT Gateway sea eliminado..."
        aws ec2 wait nat-gateway-deleted --nat-gateway-ids "$NAT_GW_ID" --region "$REGION" 2>/dev/null || true

        if [ -n "$EIP_ALLOCATION_ID" ]; then
            echo "Liberando EIP: $EIP_ALLOCATION_ID"
            aws ec2 release-address --allocation-id "$EIP_ALLOCATION_ID" --region "$REGION" 2>/dev/null || true
        fi
    fi
    
    # 1.5. Eliminar VPC Endpoints (CRÍTICO para eliminar la VPC)
    echo "Buscando y eliminando VPC Endpoints (S3 Gateway y EC2 Interface)..."

    # Buscar todos los Endpoints asociados a esta VPC por la etiqueta Project
    local VPCE_IDS=$(aws ec2 describe-vpc-endpoints \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=$PROJECT_TAG" \
        --query 'VpcEndpoints[].VpcEndpointId' \
        --output text \
        --region "$REGION" || true)

    if [ -n "$VPCE_IDS" ]; then
        for VPCE_ID in $VPCE_IDS; do
            echo "Eliminando VPC Endpoint: $VPCE_ID"
            # La eliminación es asíncrona, pero debe ser el primer paso de dependencia
            aws ec2 delete-vpc-endpoints --vpc-endpoint-ids "$VPCE_ID" --region "$REGION"
        done
        echo "Esperando 5 segundos para que los Endpoints sean eliminados completamente..."
        sleep 5
        cleanup_all_enis
    else
        echo "No se encontraron VPC Endpoints etiquetados con '$PROJECT_TAG'."
    fi

    # 2. Eliminar Asociaciones y Tablas de Ruta (RTB)
    local RTB_IDS=$(aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=$PROJECT_TAG" --query 'RouteTables[].RouteTableId' --output text --region "$REGION" || true)
    for RTB_ID in $RTB_IDS; do
        echo "Procesando Tabla de Ruta: $RTB_ID"
        # Desasociar subredes primero
        local ASSOC_IDS=$(aws ec2 describe-route-tables --route-table-ids "$RTB_ID" --query 'RouteTables[].Associations[].RouteTableAssociationId' --output text --region "$REGION" || true)
        for ASSOC_ID in $ASSOC_IDS; do
            if [[ "$ASSOC_ID" != *"main"* ]]; then # Evitar desasociar la asociación RTB principal
                aws ec2 disassociate-route-table --association-id "$ASSOC_ID" --region "$REGION" > /dev/null
            fi
        done
        # Eliminar rutas (excepto la ruta local de la VPC)
        local VPC_CIDR_BLOCK=$(aws ec2 describe-vpcs --vpc-ids "$VPC_ID" --query 'Vpcs[0].CidrBlock' --output text --region "$REGION" 2>/dev/null)
        local ROUTE_DESTS=$(aws ec2 describe-route-tables --route-table-ids "$RTB_ID" --query 'RouteTables[].Routes[].DestinationCidrBlock' --output text --region "$REGION" || true)
        for ROUTE_DEST in $ROUTE_DESTS; do
            if [[ "$ROUTE_DEST" != "$VPC_CIDR_BLOCK" ]]; then
                # Intentar eliminar la ruta
                aws ec2 delete-route --route-table-id "$RTB_ID" --destination-cidr-block "$ROUTE_DEST" --region "$REGION" 2>/dev/null || true
                
                # Para Endpoints de Gateway (como S3), la ruta usa el Endpoint ID. Intentar eliminar por Endpoint ID si falla por CIDR.
                local ENDPOINT_GATEWAY_ID=$(aws ec2 describe-route-tables --route-table-ids "$RTB_ID" --query "RouteTables[0].Routes[?DestinationCidrBlock=='$ROUTE_DEST'].VpcEndpointId" --output text --region "$REGION" 2>/dev/null)
                if [ -n "$ENDPOINT_GATEWAY_ID" ]; then
                    aws ec2 delete-vpc-endpoints --vpc-endpoint-ids "$ENDPOINT_GATEWAY_ID" --region "$REGION" 2>/dev/null || true
                fi
            fi
        done
        
        # Eliminar la Tabla de Ruta
        aws ec2 delete-route-table --route-table-id "$RTB_ID" --region "$REGION" 2>/dev/null || true
    done
    
    # ==============================================================================
    # 3. LIMPIEZA DE DEPENDENCIAS DE GRUPOS DE SEGURIDAD
    # ==============================================================================
    
    # 3.1. Obtener IDs específicos
    local INTERNAL_SG_NAME="${PROJECT_TAG}-lambda-to-rds-sg"
    local RDS_SG_NAME="${PROJECT_TAG}-rds-mysql-sg"
    local INTERNAL_SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=$INTERNAL_SG_NAME" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION" | tr -d '\n' | sed 's/None//g')
    local RDS_SG_ID=$(aws ec2 describe-security-groups --filters "Name=tag:Name,Values=$RDS_SG_NAME" --query 'SecurityGroups[0].GroupId' --output text --region "$REGION" | tr -d '\n' | sed 's/None//g')
    
    # 3.2. Revocar la regla Ingress cruzada (RDS SG permite tráfico desde Lambda SG)
    if [ -n "$RDS_SG_ID" ] && [ -n "$INTERNAL_SG_ID" ]; then
        echo "Revocando regla Ingress SG-a-SG (RDS $RDS_SG_ID <- Lambda $INTERNAL_SG_ID)..."
        aws ec2 revoke-security-group-ingress \
            --group-id "$RDS_SG_ID" \
            --protocol tcp \
            --port 3306 \
            --source-group "$INTERNAL_SG_ID" \
            --region "$REGION" 2>/dev/null || true
    fi

    # 3.3. Eliminar Interfaces de Red (ENIs) huérfanas
    echo "Buscando y eliminando ENIs de Lambda huérfanas..."
    aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$VPC_ID" "Name=description,Values=*AWS Lambda ENI*" \
        --query 'NetworkInterfaces[].NetworkInterfaceId' \
        --output text \
        --region "$REGION" | tr ' ' '\n' | while read ENI_ID; do
            if [ -n "$ENI_ID" ]; then
                echo "  - Eliminando ENI huérfana: $ENI_ID"
                aws ec2 delete-network-interface --network-interface-id "$ENI_ID" --region "$REGION" 2>/dev/null || true
            fi
        done
        
    echo "Pausa de 20 segundos para que AWS resuelva las referencias de dependencias antes de borrar los SG..."
    sleep 20
    
    # 4. Eliminar Grupos de Seguridad (solo SGs etiquetados con PROJECT_TAG)
    local SG_IDS=$(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=$PROJECT_TAG" --query 'SecurityGroups[].GroupId' --output text --region "$REGION" || true)
    for SG_ID in $SG_IDS; do
        echo "Eliminando Grupo de Seguridad: $SG_ID"
        aws ec2 delete-security-group --group-id "$SG_ID" --region "$REGION" 2>/dev/null || echo "Advertencia: El SG $SG_ID aún no pudo ser eliminado. Reintente si es necesario."
    done

    # 5. Eliminar Subredes
    local SUBNET_IDS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" "Name=tag:Project,Values=$PROJECT_TAG" --query 'Subnets[].SubnetId' --output text --region "$REGION" || true)
    for SUBNET_ID in $SUBNET_IDS; do
        echo "Eliminando Subred: $SUBNET_ID"
        aws ec2 delete-subnet --subnet-id "$SUBNET_ID" --region "$REGION"
    done

    # 6. Desasociar y Eliminar Internet Gateway
    # CRÍTICO: Capturamos el ID y limpiamos el output para evitar "None"
    local IGW_ID=$(aws ec2 describe-internet-gateways \
        --filters "Name=attachment.vpc-id,Values=$VPC_ID" \
        --query 'InternetGateways[0].InternetGatewayId' \
        --output text \
        --region "$REGION" | tr -d '\n' | sed 's/None//g') # <--- CORRECCIÓN APLICADA AQUÍ

    if [ -n "$IGW_ID" ]; then
        echo "Desasociando Internet Gateway: $IGW_ID"
        aws ec2 detach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID" --region "$REGION"
        echo "Eliminando Internet Gateway: $IGW_ID"
        aws ec2 delete-internet-gateway --internet-gateway-id "$IGW_ID" --region "$REGION"
    else
        # Esto imprimirá un mensaje si no se encuentra el IGW, lo que ahora está bien.
        echo "Internet Gateway no encontrado o ya desasociado de la VPC."
    fi

    # 7. Eliminar VPC
    echo "Eliminando VPC: $VPC_ID"
    # El comando fallará si aún hay dependencias, pero con las correcciones debería pasar.
    aws ec2 delete-vpc --vpc-id "$VPC_ID" --region "$REGION" 2>/dev/null || echo "Error: La VPC $VPC_ID aún tiene dependencias. Intente ejecutar 'destroy' nuevamente."
    echo "VPC '$VPC_ID' procesada."
}

# --- NUEVA FUNCIÓN: Limpieza agresiva de ENIs ---
cleanup_all_enis() {
    log_section "BUSCANDO Y ELIMINANDO ENIs DEPENDIENTES EN VPC"
    
    # 1. Buscar todas las ENIs en la VPC, excepto aquellas usadas por recursos que se manejan por separado (como NAT GW)
    ENI_IDS=$(aws ec2 describe-network-interfaces \
        --filters "Name=vpc-id,Values=$VPC_ID" \
        --query 'NetworkInterfaces[].NetworkInterfaceId' \
        --output text --region "$REGION" | tr '\t' ' ')

    if [ -z "$ENI_IDS" ]; then
        echo "No se encontraron ENIs en la VPC '$VPC_ID'."
        return 0
    fi
    
    echo "ENIs encontradas para limpieza: $ENI_IDS"

    for ENI_ID in $ENI_IDS; do
        # Intentar desasociar si tiene una asociación activa (necesario para ENIs de Lambda huérfanas)
        ASSOCIATION_ID=$(aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --query 'NetworkInterfaces[0].Attachment.AttachmentId' --output text --region "$REGION" 2>/dev/null)
        if [ "$ASSOCIATION_ID" != "None" ] && [ -n "$ASSOCIATION_ID" ]; then
            echo "Desasociando ENI '$ENI_ID'..."
            # Usar --force para asegurar el desprendimiento
            aws ec2 detach-network-interface --attachment-id "$ASSOCIATION_ID" --force --region "$REGION" || true
            sleep 3 # Dar tiempo a AWS para registrar el desprendimiento
        fi

        # Eliminar la ENI
        echo "Eliminando ENI: $ENI_ID"
        aws ec2 delete-network-interface --network-interface-id "$ENI_ID" --region "$REGION" || echo "Advertencia: Fallo al eliminar ENI '$ENI_ID'. Puede estar siendo usada."
    done
    
    echo "Pausa de 10 segundos para la propagación de la eliminación de ENIs..."
    sleep 10
}

# --- Flujo de Ejecución Principal ---
log_section "INICIANDO DESTRUCCIÓN DE INFRAESTRUCTURA CORE (VPC, RDS, EC2, API GW)"

# 1. 'Terminar' Instancias EC2 y eliminar Par de Claves
destroy_ec2_resources

# 2. 'Eliminar' Instancia RDS y Grupo de Subred (Este paso ahora será de limpieza, ya que la creación es manual)
destroy_rds_resources

# 3. 'Eliminar' API Gateway y su Rol de Servicio IAM
destroy_api_gateway

# 4. 'Eliminar' Recursos de Red (NAT, RTB, SG, Subredes, IGW, VPC)
destroy_network_resources

log_section "DESTRUCCIÓN CORE COMPLETADA"
echo "Nota: Las Lambdas, tablas de DynamoDB y buckets S3 deben eliminarse utilizando el comando 'build_and_deploy.sh --destroy' para cada microservicio."
