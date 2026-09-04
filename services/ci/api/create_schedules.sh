#!/bin/bash

# Crea las reglas de EventBridge que disparan tareas programadas en los Lambdas.
# Es idempotente: puedes ejecutarlo múltiples veces sin errores.

# Detiene la ejecución si algún comando falla
set -e

# --- Configuración de las Reglas ---
# Sintaxis: "regla|lambda|cron|payload|descripción"
#
# El cron de EventBridge va SIEMPRE en UTC. Bolivia es UTC-4, así que para que
# algo corra a las 09:00 de La Paz hay que escribir 13:00 acá.
#
# El payload es lo que recibe el handler del Lambda. `task` es la marca que el
# main.py del servicio usa para distinguir esta invocación de un evento HTTP de
# API Gateway: sin ella, Mangum buscaría una petición que un evento programado
# nunca trae.

RULES=(
    # El BCB publica el tipo de cambio en la mañana. Corremos a las 09:00 de
    # La Paz para que la cotización del día ya esté en la tabla cuando alguien
    # abra una pantalla. La ventana que repara la corrida está en el servicio
    # (SCHEDULED_SYNC_DAYS), no acá: el disparador dice CUÁNDO, el dominio dice
    # CUÁNTO reparar.
    "quotes-daily-rate-sync|quotes-handler-service|cron(0 13 * * ? *)|{\"task\":\"sync_rates\"}|Sync diario del tipo de cambio oficial del BCB"
)

REGION="us-east-1"
PROFILE="deploy_ml"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "$PROFILE")

echo "Iniciando la gestión de reglas programadas de EventBridge..."

for rule_config in "${RULES[@]}"; do
    IFS='|' read -r RULE_NAME FUNCTION_NAME CRON PAYLOAD DESCRIPTION <<< "$rule_config"

    FUNCTION_ARN="arn:aws:lambda:${REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME}"

    echo ""
    echo "Regla: '$RULE_NAME' -> $FUNCTION_NAME"

    if ! aws lambda get-function --function-name "$FUNCTION_NAME" \
            --region "$REGION" --profile "$PROFILE" &>/dev/null; then
        echo "  ERROR: el Lambda '$FUNCTION_NAME' no existe. Despliégalo primero."
        exit 1
    fi

    # put-rule crea o actualiza; correrlo dos veces deja el mismo estado.
    aws events put-rule \
        --name "$RULE_NAME" \
        --schedule-expression "$CRON" \
        --description "$DESCRIPTION" \
        --state ENABLED \
        --region "$REGION" \
        --profile "$PROFILE" \
        --output text --query 'RuleArn'

    RULE_ARN="arn:aws:events:${REGION}:${ACCOUNT_ID}:rule/${RULE_NAME}"

    # El permiso se identifica por StatementId. Si ya está, add-permission falla
    # con ResourceConflictException y no hay nada que hacer: ya estaba dado.
    if aws lambda add-permission \
            --function-name "$FUNCTION_NAME" \
            --statement-id "eventbridge-${RULE_NAME}" \
            --action 'lambda:InvokeFunction' \
            --principal events.amazonaws.com \
            --source-arn "$RULE_ARN" \
            --region "$REGION" \
            --profile "$PROFILE" &>/dev/null; then
        echo "  Permiso de invocación concedido a EventBridge."
    else
        echo "  El permiso de invocación ya existía."
    fi

    # El Id del target es fijo, así que put-targets reemplaza en vez de duplicar.
    # Va en JSON y no en la sintaxis abreviada `Id=1,Arn=...,Input=...`: el
    # Input es a su vez JSON y sus comillas rompen el parser de la forma corta.
    TARGETS_JSON=$(python3 -c "import json,sys; print(json.dumps([{'Id':'1','Arn':sys.argv[1],'Input':sys.argv[2]}]))" "$FUNCTION_ARN" "$PAYLOAD")

    aws events put-targets \
        --rule "$RULE_NAME" \
        --targets "$TARGETS_JSON" \
        --region "$REGION" \
        --profile "$PROFILE" \
        --output text --query 'FailedEntryCount'

    echo "  Programada: $CRON (UTC)"
done

echo ""
echo "Proceso de creación de reglas finalizado con éxito. ✅"
echo ""
echo "Para probar una sin esperar al horario:"
echo "  aws lambda invoke --function-name quotes-handler-service \\"
echo "      --payload '{\"task\":\"sync_rates\"}' --cli-binary-format raw-in-base64-out \\"
echo "      --profile $PROFILE /dev/stdout"
