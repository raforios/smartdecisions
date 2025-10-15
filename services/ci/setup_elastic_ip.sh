#!/bin/bash

# 'setup_elastic_ip.sh': Asigna una IP Elástica y la asocia a la instancia EC2.

set -e
set -o pipefail

# --- Verificación y Carga de Variables ---
CONFIG_FILE="./infrastructure.config"
source "$CONFIG_FILE"

: ${REGION:?"Error: REGION no está configurada."}
: ${EC2_INSTANCE_ID:?"Error: EC2_INSTANCE_ID no está configurada."}

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# --- Funciones Principales ---

manage_elastic_ip() {
    log_section "GESTIÓN DE LA IP ELÁSTICA (EIP)"

    # Intenta describir la EIP si ya está asignada (búsqueda por tag o asociación, pero es más fácil por la IP)
    # Para este script, vamos a simplificar asumiendo que SIEMPRE se crea una nueva EIP si no existe una variable.
    # En un ambiente real, se recomienda guardar el AllocationId.

    # 1. Verificar si ya existe una EIP asociada (mirando la interfaz de red, no solo el ID de la instancia)
    EIP_ALLOCATION_ID=$(aws ec2 describe-addresses \
        --filters "Name=instance-id,Values=$EC2_INSTANCE_ID" \
        --query 'Addresses[0].AllocationId' \
        --output text \
        --region "$REGION" 2>/dev/null || true)
        
    EIP_ALLOCATION_ID=$(echo "$EIP_ALLOCATION_ID" | sed 's/None//g' | tr -d '\n')

    if [ -z "$EIP_ALLOCATION_ID" ]; then
        echo "No se encontró EIP asociada. Asignando nueva IP Elástica..."
        
        # 2. Asignar (reservar) una nueva IP Elástica
        EIP_ALLOCATION_ID=$(aws ec2 allocate-address \
            --domain vpc \
            --query 'AllocationId' \
            --output text \
            --region "$REGION")
        
        # 3. Asociar la EIP a la instancia EC2
        aws ec2 associate-address \
            --instance-id "$EC2_INSTANCE_ID" \
            --allocation-id "$EIP_ALLOCATION_ID" \
            --region "$REGION"
            
        echo "EIP asignada y asociada al EC2: $EC2_INSTANCE_ID."

    else
        echo "EIP ya está asociada a la instancia con Allocation ID: $EIP_ALLOCATION_ID."
    fi
    
    # 4. Obtener la IP pública final
    ELASTIC_IP=$(aws ec2 describe-addresses \
        --allocation-ids "$EIP_ALLOCATION_ID" \
        --query 'Addresses[0].PublicIp' \
        --output text \
        --region "$REGION")
        
    # Guardar la nueva IP estática para referencia
    export ELASTIC_IP
    echo "IP Elástica final para SSH/acceso directo: $ELASTIC_IP"
}

# --- Flujo de Ejecución Principal ---
manage_elastic_ip

log_section "CONFIGURACIÓN DE LA IP ELÁSTICA COMPLETADA"
echo "La dirección IP pública de su EC2 ahora es: $ELASTIC_IP"
echo "Asegúrese de actualizar su comando SSH con esta nueva IP estática."
echo "--------------------------------------------------------------------------------"
