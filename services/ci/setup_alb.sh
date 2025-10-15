#!/bin/bash

# 'setup_alb.sh': Crea un Application Load Balancer (ALB) y lo configura
# para dirigir el tráfico del puerto 80 al puerto 8080 de la instancia EC2.

set -e
set -o pipefail

# --- Verificación y Carga de Variables ---
CONFIG_FILE="./infrastructure.config"
source "$CONFIG_FILE"

: ${REGION:?"Error: REGION no está configurada."}
: ${VPC_ID:?"Error: VPC_ID no está configurada."}
: ${PUB_SG_ID:?"Error: PUB_SG_ID no está configurada (SG Público de EC2)."}
: ${PUBLIC_SUBNET_IDS:?"Error: PUBLIC_SUBNET_IDS no está configurada."}
: ${EC2_INSTANCE_ID:?"Error: EC2_INSTANCE_ID no está configurada."}
: ${PROJECT_TAG:?"Error: PROJECT_TAG no está configurada."}

PROJECT_TAG_CLEANED=$(echo "$PROJECT_TAG" | tr '_' '-') 

# --- Nombres de Recursos ---
ALB_NAME="${PROJECT_TAG_CLEANED}-Frontend-ALB"
TG_NAME="${PROJECT_TAG_CLEANED}-Frontend-TG"
ALB_SG_NAME="${PROJECT_TAG_CLEANED}-ALB-SG" 
ALB_SG_ID=""

# --- Funciones de Utilidad (get_resource_id debe estar en el script principal o aquí) ---
# Asumo que get_resource_id está disponible o definido aquí, si no, debe copiarse de setup_aws_infrastructure.sh

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
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

manage_alb_security_group() {
    log_section "GESTIÓN DEL SECURITY GROUP PARA EL ALB"
    
    ALB_SG_ID=$(get_resource_id "sg" "$ALB_SG_NAME")
    local GLOBAL_CIDR="0.0.0.0/0"

    if [ -z "$ALB_SG_ID" ]; then
        echo "SG para ALB no encontrado. Creando..."
        ALB_SG_ID=$(aws ec2 create-security-group \
            --group-name "$ALB_SG_NAME" \
            --description "Acceso publico HTTP/HTTPS para el Application Load Balancer" \
            --vpc-id "$VPC_ID" \
            --query 'GroupId' --output text --region "$REGION")
            
        aws ec2 create-tags --resources "$ALB_SG_ID" \
            --tags Key=Name,Value="$ALB_SG_NAME" Key=Project,Value="$PROJECT_TAG" \
            --region "$REGION"
        
        # Añadir reglas de acceso HTTP/HTTPS desde cualquier lugar (0.0.0.0/0)
        echo "Añadiendo reglas Ingress HTTP (80) y HTTPS (443)..."
        aws ec2 authorize-security-group-ingress \
            --group-id "$ALB_SG_ID" --protocol tcp --port 80 --cidr "$GLOBAL_CIDR" --region "$REGION"
        aws ec2 authorize-security-group-ingress \
            --group-id "$ALB_SG_ID" --protocol tcp --port 443 --cidr "$GLOBAL_CIDR" --region "$REGION"
    else
        echo "SG para ALB '$ALB_SG_ID' ya existe."
    fi
    
    export ALB_SG_ID
}

manage_ec2_target_group_rule() {
    log_section "ACTUALIZANDO REGLA INGRESS DE EC2 PARA EL TRÁFICO DEL ALB"
    
    # CRÍTICO: El SG de EC2 ($PUB_SG_ID) debe permitir tráfico en el puerto 8080
    # solo desde el SG del ALB ($ALB_SG_ID)
    
    local TARGET_PORT="8080"
    
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$PUB_SG_ID" \
        --protocol tcp \
        --port "$TARGET_PORT" \
        --source-group "$ALB_SG_ID" \
        --region "$REGION" 2>/dev/null; then
        
        echo "   (OK) Regla en EC2 SG ya existe: Permitir tráfico en 8080 desde ALB SG."
    else
        echo "   (ADD) Regla en EC2 SG añadida: Permitir tráfico en $TARGET_PORT desde ALB SG '$ALB_SG_ID'."
    fi
}

manage_target_group() {
    log_section "GESTIÓN DEL TARGET GROUP"
    
    TG_ARN=$(aws elbv2 describe-target-groups \
        --names "$TG_NAME" \
        --query 'TargetGroups[0].TargetGroupArn' \
        --output text \
        --region "$REGION" 2>/dev/null \
        || true)

    # Limpiar cualquier residuo de salida si el comando anterior falló
    TG_ARN=$(echo "$TG_ARN" | sed 's/None//g' | tr -d '\n')

    if [ -z "$TG_ARN" ]; then
        echo "Target Group '$TG_NAME' no encontrado. Creando..."
        TG_ARN=$(aws elbv2 create-target-group \
            --name "$TG_NAME" \
            --protocol HTTP \
            --port 8080 \
            --vpc-id "$VPC_ID" \
            --target-type instance \
            --health-check-path / \
            --tags Key=Project,Value="$PROJECT_TAG" Key=Name,Value="$TG_NAME" \
            --query 'TargetGroups[0].TargetGroupArn' \
            --output text \
            --region "$REGION")
            
        # Registrar la instancia EC2 al Target Group
        aws elbv2 register-targets \
            --target-group-arn "$TG_ARN" \
            --targets Id="$EC2_INSTANCE_ID" \
            --region "$REGION" || true

        echo "Instancia EC2 '$EC2_INSTANCE_ID' registrada en el Target Group."
    else
        echo "Target Group '$TG_NAME' ya existe con ARN: $TG_ARN."

        aws elbv2 register-targets \
            --target-group-arn "$TG_ARN" \
            --targets Id="$EC2_INSTANCE_ID" \
            --region "$REGION" || true

    fi

    echo "Ajustando el Matcher del Health Check para aceptar códigos 200, 301 y 302..."

    aws elbv2 modify-target-group \
        --target-group-arn "$TG_ARN" \
        --health-check-path "/" \
        --matcher 'HttpCode="200,301,302"' \
        --region "$REGION"
        
    echo "Matcher del Health Check ajustado."

    export TG_ARN
}

manage_alb() {
    log_section "GESTIÓN DEL APPLICATION LOAD BALANCER (ALB)"
    
    ALB_ARN=$(aws elbv2 describe-load-balancers \
        --names "$ALB_NAME" \
        --query 'LoadBalancers[0].LoadBalancerArn' \
        --output text \
        --region "$REGION" 2>/dev/null \
        || true)
        
    # Limpiar cualquier residuo que pueda ser interpretado como ARN válido
    ALB_ARN=$(echo "$ALB_ARN" | sed 's/None//g' | tr -d '\n')
        
    local SUBNET_LIST_SPACED=$(echo "$PUBLIC_SUBNET_IDS" | tr ',' ' ')

    if [ -z "$ALB_ARN" ]; then
        echo "ALB '$ALB_NAME' no encontrado. Creando..."
        
        ALB_ARN=$(aws elbv2 create-load-balancer \
            --name "$ALB_NAME" \
            --subnets $SUBNET_LIST_SPACED \
            --security-groups "$ALB_SG_ID" \
            --scheme internet-facing \
            --tags Key=Project,Value="$PROJECT_TAG" Key=Name,Value="$ALB_NAME" \
            --query 'LoadBalancers[0].LoadBalancerArn' \
            --output text \
            --region "$REGION")
            
        echo "Esperando a que el ALB esté activo..."
        aws elbv2 wait load-balancer-available --load-balancer-arns "$ALB_ARN" --region "$REGION" || true
        
        # Crear Listener HTTP (80)
        aws elbv2 create-listener \
            --load-balancer-arn "$ALB_ARN" \
            --protocol HTTP \
            --port 80 \
            --default-actions Type=forward,TargetGroupArn="$TG_ARN" \
            --region "$REGION" > /dev/null
        echo "Listener HTTP (80) creado y asociado al Target Group."

    else
        echo "ALB '$ALB_NAME' ya existe con ARN: $ALB_ARN."
    fi
    
    # Obtener el DNS del ALB
    ALB_DNS=$(aws elbv2 describe-load-balancers \
        --load-balancer-arns "$ALB_ARN" \
        --query 'LoadBalancers[0].DNSName' \
        --output text \
        --region "$REGION" || true)
        
    export ALB_DNS
}

# --- Flujo de Ejecución Principal ---
manage_alb_security_group
manage_ec2_target_group_rule
manage_target_group
manage_alb

log_section "CONFIGURACIÓN DEL APPLICATION LOAD BALANCER COMPLETADA"
echo "ALB ARN: $ALB_ARN"
echo "Target Group ARN: $TG_ARN"
echo "URL de Acceso al Frontend (Puerto 80): http://$ALB_DNS"
echo "--------------------------------------------------------------------------------"
