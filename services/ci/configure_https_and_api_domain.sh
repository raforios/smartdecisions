#!/bin/bash

# Script de configuración de infraestructura - HTTPS y Dominio de API
# Asegura HTTPS en el ALB y crea el dominio base para los microservicios Lambda.

set -e
set -o pipefail

# --- 1. CONFIGURACIÓN Y VARIABLES CRÍTICAS ---
REGION="us-east-1"  # Asegúrate de que esta sea la región correcta
AWS_PROFILE="deploy_binaria" 
CUSTOM_DOMAIN="api.binaria.app"
CERTIFICATE_ARN="arn:aws:acm:us-east-1:195250648991:certificate/66a4461a-71b0-45a3-82ee-4dc550acb990" # ARN obtenido de tu imagen
# Necesitas estas variables del script setup_alb.sh
ALB_ARN="arn:aws:elasticloadbalancing:us-east-1:195250648991:loadbalancer/app/API-BINARIA-Frontend-ALB/3e4e229ff3599408" # Reemplaza con tu ALB ARN
TG_ARN="arn:aws:elasticloadbalancing:us-east-1:195250648991:targetgroup/API-BINARIA-Frontend-TG/9db642eb2527397f" # Reemplaza con tu TG ARN

# --- Funciones Auxiliares ---

log_section() {
    echo ""
    echo "--------------------------------------------------------------------------------"
    echo "| $1 |"
    echo "--------------------------------------------------------------------------------"
}

# --- 2. GESTIÓN DEL LISTENER HTTPS (443) EN EL ALB ---

manage_https_listener() {
    log_section "PASO 1/2: CONFIGURACIÓN DEL LISTENER HTTPS (PUERTO 443)"

    local LISTENER_ARN_443=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --query "Listeners[?Port==\`443\`].ListenerArn" \
        --output text \
        --region "$REGION" --profile "$AWS_PROFILE" 2>/dev/null || true)
        
    LISTENER_ARN_443=$(echo "$LISTENER_ARN_443" | sed 's/None//g' | tr -d '\n')

    if [ -z "$LISTENER_ARN_443" ]; then
        echo "Listener HTTPS (443) no encontrado. Creando con certificado ACM..."

        # 2a. Crear el Listener HTTPS en el puerto 443
        LISTENER_ARN_443=$(aws elbv2 create-listener \
            --load-balancer-arn "$ALB_ARN" \
            --protocol HTTPS \
            --port 443 \
            --certificates CertificateArn="$CERTIFICATE_ARN" \
            --default-actions Type=forward,TargetGroupArn="$TG_ARN" \
            --query 'Listeners[0].ListenerArn' \
            --output text \
            --region "$REGION" --profile "$AWS_PROFILE")
            
        echo "✅ Listener HTTPS (443) creado con ARN: $LISTENER_ARN_443."
    else
        echo "Listener HTTPS (443) ya existe. ARN: $LISTENER_ARN_443."
    fi

    # 2b. Modificar el Listener HTTP (80) para redirigir a HTTPS
    local HTTP_LISTENER_ARN=$(aws elbv2 describe-listeners \
        --load-balancer-arn "$ALB_ARN" \
        --query "Listeners[?Port==\`80\`].ListenerArn" \
        --output text \
        --region "$REGION" --profile "$AWS_PROFILE" 2>/dev/null || true)
        
    if [ ! -z "$HTTP_LISTENER_ARN" ]; then
        echo "Configurando Listener HTTP (80) para redirigir a HTTPS..."
        
        # Sintaxis robusta para el shell
        aws elbv2 modify-listener \
            --listener-arn "$HTTP_LISTENER_ARN" \
            --default-actions '[{"Type":"redirect", "RedirectConfig":{"Protocol":"HTTPS","Port":"443","StatusCode":"HTTP_301"}}]' \
            --region "$REGION" --profile "$AWS_PROFILE"
        
        echo "✅ Redirección HTTP -> HTTPS configurada correctamente!"
    fi
}

# --- 3. CONFIGURACIÓN DEL DOMINIO DE API GATEWAY (BACKEND) ---

setup_api_custom_domain() {
    log_section "PASO 2/2: CONFIGURACIÓN DEL DOMINIO ESTÁTICO DE API ($CUSTOM_DOMAIN)"
    
    # 3a. Intentar encontrar el dominio personalizado existente
    local EXISTING_DOMAIN=$(aws apigatewayv2 get-domain-names \
        --query "Items[?DomainName=='$CUSTOM_DOMAIN'].DomainName" \
        --output text \
        --region "$REGION" --profile "$AWS_PROFILE" 2>/dev/null || true)
        
    if [ -z "$EXISTING_DOMAIN" ]; then
        echo "Dominio personalizado $CUSTOM_DOMAIN no encontrado. Creando..."

        # 3b. Crear el nombre de dominio en API Gateway
        DOMAIN_INFO=$(aws apigatewayv2 create-domain-name \
            --domain-name "$CUSTOM_DOMAIN" \
            --domain-name-configurations CertificateArn="$CERTIFICATE_ARN",EndpointType="REGIONAL" \
            --query '[DomainName,DomainNameConfigurations[0].ApiGatewayDomainName]' \
            --output text \
            --region "$REGION" --profile "$AWS_PROFILE")
            
        API_GATEWAY_HOST=$(echo "$DOMAIN_INFO" | awk '{print $2}')
        
        echo "✅ Dominio de API creado."
        echo "⚠️ ACCIÓN MANUAL REQUERIDA EN CLOUDFLARE:"
        echo "   Cree un registro CNAME en Cloudflare con:"
        echo "   - Nombre: api"
        echo "   - Objetivo: $API_GATEWAY_HOST"
        echo "   - Estado de Proxy: SOLO DNS (Gris)"
        
    else
        echo "Dominio $CUSTOM_DOMAIN ya existe. Saltar creación."
        # Si ya existe, recupera el host para recordar al usuario
        API_GATEWAY_HOST=$(aws apigatewayv2 get-domain-names \
            --query "Items[?DomainName=='$CUSTOM_DOMAIN'].DomainNameConfigurations[0].ApiGatewayDomainName" \
            --output text \
            --region "$REGION" --profile "$AWS_PROFILE")
            
        echo "Host de API Gateway: $API_GATEWAY_HOST"
    fi
}

# --- LÓGICA PRINCIPAL ---

manage_https_listener
setup_api_custom_domain

log_section "PROCESO COMPLETADO"
echo "Todo el tráfico de binaria.app ahora es HTTPS y la base de la API está lista."
echo "--------------------------------------------------------------------------------"
echo "⚠️ Siguientes pasos CRÍTICOS (MANUALES):"
echo "1. Configurar el CNAME 'api' en Cloudflare apuntando a: $API_GATEWAY_HOST"
echo "2. Ejecutar la función 'update_lambda_env' con la nueva URL base: https://api.binaria.app/"