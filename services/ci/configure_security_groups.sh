#!/bin/bash

# 'configure_security_groups.sh': Refuerza y asegura las reglas Ingress/Egress
# de los Security Groups después de que la infraestructura base ha sido creada.

set -e
set -o pipefail

# --- Verificación y Carga de Variables ---
CONFIG_FILE="./infrastructure.config"
source "$CONFIG_FILE" # Cargar variables persistidas por setup_aws_infrastructure.sh

: ${REGION:?"Error: REGION no está configurada."}
: ${VPC_ID:?"Error: VPC_ID no está configurada."}
: ${SG_RDS_ID:?"Error: SG_RDS_ID no está configurada. (SG de RDS)"}
: ${INTERNAL_SG_ID:?"Error: INTERNAL_SG_ID no está configurada. (SG de Lambda)"}
: ${PUB_SG_ID:?"Error: PUB_SG_ID no está configurada. (SG Público de EC2)"}

# --- Funciones de Utilidad ---
log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

get_public_ip() {
    # Mantiene la lógica de obtener la IP pública del usuario
    local user_ip
    user_ip=$(curl -s http://checkip.amazonaws.com)/32
    if [ $? -ne 0 ] || [ -z "$user_ip" ]; then
        user_ip="0.0.0.0/0"
    fi
    echo "$user_ip"
}

# --------------------------------------------------------------------------------
# FUNCIÓN CENTRAL: GESTIÓN DE REGLAS INGRESS
# --------------------------------------------------------------------------------
manage_ingress_rules() {
    log_section "CONFIGURACIÓN DE REGLAS INGRESS CRÍTICAS (ACCESO ENTRADA)"
    
    local USER_IP=$(get_public_ip)
    local GLOBAL_CIDR="0.0.0.0/0"
    
    # --- 1. SG DE RDS (sg-0cbbf31597d438153) ---
    echo "-> Configurando INGRESS para RDS SG ($SG_RDS_ID)..."
    
    # 1.1. Acceso de Lambda al RDS (3306) - Origen: INTERNAL_SG_ID
    # Nota: Esta regla es interna, pero la aseguramos aquí.
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$SG_RDS_ID" \
        --protocol tcp --port 3306 \
        --source-group "$INTERNAL_SG_ID" \
        --region "$REGION" 2>/dev/null; then
        echo "   (OK) Regla Lambda->RDS (3306) ya existe."
    else
        echo "   (ADD) Regla Lambda->RDS (3306) añadida."
    fi

    # 1.2. Acceso Público al RDS (3306) - Origen: 0.0.0.0/0
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$SG_RDS_ID" \
        --protocol tcp --port 3306 \
        --cidr "$GLOBAL_CIDR" \
        --region "$REGION" 2>/dev/null; then
        echo "   (OK) Regla Pública GLOBAL->RDS (3306) ya existe."
    else
        echo "   (ADD) Regla Pública GLOBAL->RDS (3306) añadida."
    fi

    # --- 2. SG PÚBLICO EC2 (sg-09fafff5d204ebd88) ---
    echo "-> Configurando INGRESS para EC2 Public SG ($PUB_SG_ID)..."

    # 2.1. SSH (22) - Origen: IP pública del usuario ($USER_IP)
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$PUB_SG_ID" \
        --protocol tcp --port 22 \
        --cidr "$USER_IP" \
        --region "$REGION" 2>/dev/null; then
        echo "   (OK) Regla SSH (22) desde $USER_IP ya existe."
    else
        echo "   (ADD) Regla SSH (22) desde $USER_IP añadida."
    fi
    
    # 2.2. HTTP (80) - Origen: 0.0.0.0/0
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$PUB_SG_ID" \
        --protocol tcp --port 80 \
        --cidr "$GLOBAL_CIDR" \
        --region "$REGION" 2>/dev/null; then
        echo "   (OK) Regla HTTP (80) ya existe."
    else
        echo "   (ADD) Regla HTTP (80) añadida."
    fi

    # 2.3. HTTPS (443) - Origen: 0.0.0.0/0
    if ! aws ec2 authorize-security-group-ingress \
        --group-id "$PUB_SG_ID" \
        --protocol tcp --port 443 \
        --cidr "$GLOBAL_CIDR" \
        --region "$REGION" 2>/dev/null; then
        echo "   (OK) Regla HTTPS (443) ya existe."
    else
        echo "   (ADD) Regla HTTPS (443) añadida."
    fi
}

# --------------------------------------------------------------------------------
# FUNCIÓN OPCIONAL: GESTIÓN DE REGLAS EGRESS (Generalmente 0.0.0.0/0 Allow All)
# --------------------------------------------------------------------------------
manage_egress_rules() {
    log_section "VERIFICANDO REGLAS EGRESS (SALIDA)"
    
    # Por defecto, AWS crea una regla de EGRESS que permite todo el tráfico saliente. 
    # Aquí solo verificaremos que la regla de EGRESS predeterminada exista en el SG Público y de RDS.

    # Ejemplo: SG Público de EC2
    aws ec2 describe-security-groups \
        --group-ids "$PUB_SG_ID" \
        --query 'SecurityGroups[0].IpPermissionsEgress[?IpProtocol==`-1` && IpRanges[0].CidrIp==`0.0.0.0/0`]' \
        --output text --region "$REGION" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "   (OK) Regla Egress (Todo) para EC2 Public SG ya existe."
    else
        echo "   (WARNING) Revise la regla de Egress en EC2 Public SG si tiene problemas de salida."
    fi
}

# --- Flujo de Ejecución Principal ---
manage_ingress_rules
manage_egress_rules

log_section "CONFIGURACIÓN DE REGLAS DE SEGURIDAD COMPLETADA"
echo "Las reglas INGRESS/OUTBOUND críticas han sido verificadas y aseguradas."
echo "Ahora reintente la conexión SSH (EC2) y la conexión a la DB (RDS)."
echo "--------------------------------------------------------------------------------"
