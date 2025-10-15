#!/bin/bash

# 'configure_https.sh': Añade un Listener HTTPS (443) al ALB usando un certificado ACM.

set -e
set -o pipefail

# --- Verificación y Carga de Variables ---
CONFIG_FILE="./infrastructure.config"
source "$CONFIG_FILE"

# Las variables ALB_ARN y TG_ARN deben ser exportadas por setup_alb.sh
: ${REGION:?"Error: REGION no está configurada."}
: ${ALB_ARN:?"Error: ALB_ARN no está configurada. Ejecute setup_alb.sh primero."}
# NOTA CRÍTICA: Debe reemplazar esto con el ARN REAL de su certificado
: ${CERTIFICATE_ARN:?"Error: CERTIFICATE_ARN no está configurada. Debe obtener un certificado ACM."} 
: ${TG_ARN:?"Error: TG_ARN no está configurada."}

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
    echo ""
}

# --- Funciones Principales ---

manage_https_listener() {
    log_section "CONFIGURACIÓN DEL LISTENER HTTPS (PUERTO 443)"

    local LISTENER_ARN=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --query "Listeners[?Port==\`443\`].ListenerArn" \
        --output text \
        --region "$REGION" 2>/dev/null || true)
        
    LISTENER_ARN=$(echo "$LISTENER_ARN" | sed 's/None//g' | tr -d '\n')

    if [ -z "$LISTENER_ARN" ]; then
        echo "Listener HTTPS (443) no encontrado. Creando..."

        # 1. Crear el Listener HTTPS en el puerto 443
        LISTENER_ARN=$(aws elbv2 create-listener \
            --load-balancer-arn "$ALB_ARN" \
            --protocol HTTPS \
            --port 443 \
            --certificates CertificateArn="$CERTIFICATE_ARN" \
            --default-actions Type=forward,TargetGroupArn="$TG_ARN" \
            --query 'Listeners[0].ListenerArn' \
            --output text \
            --region "$REGION")
            
        echo "Listener HTTPS (443) creado con ARN: $LISTENER_ARN."

        # 2. Opcional: Modificar el Listener HTTP (80) para redirigir a HTTPS
        # Este paso garantiza que todos los usuarios que entren por HTTP sean automáticamente redirigidos
        
        local HTTP_LISTENER_ARN=$(aws elbv2 describe-listeners \
            --load-balancer-arn "$ALB_ARN" \
            --query "Listeners[?Port==\`80\`].ListenerArn" \
            --output text \
            --region "$REGION" 2>/dev/null || true)
            
        if [ ! -z "$HTTP_LISTENER_ARN" ]; then
            echo "Configurando Listener HTTP (80) para redirigir a HTTPS..."
            
            aws elbv2 modify-listener \
                --listener-arn "$HTTP_LISTENER_ARN" \
                --default-actions Type=redirect,RedirectConfig='{\"Protocol\":\"HTTPS\",\"Port\":\"443\",\"StatusCode\":\"HTTP_301\"}' \
                --region "$REGION"
            
            echo "¡Redirección HTTP -> HTTPS configurada correctamente!"
        fi

    else
        echo "Listener HTTPS (443) ya existe con ARN: $LISTENER_ARN."
    fi
}

# --- Flujo de Ejecución Principal ---
manage_https_listener

log_section "CONFIGURACIÓN HTTPS COMPLETADA"
echo "Pruebe el acceso usando HTTPS en su dominio asociado."
echo "--------------------------------------------------------------------------------"
