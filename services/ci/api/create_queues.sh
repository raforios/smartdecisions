#!/bin/bash

# Crea las colas SQS entre servicios, sus colas de fallidos, los permisos de
# quien envía y de quien consume, y el disparador de la cola hacia el Lambda
# que la vacía. Es idempotente: puedes ejecutarlo múltiples veces sin errores;
# lo que existe se deja como dice esta lista.
#
# Va DESPUÉS de desplegar los Lambdas que nombra: los roles se leen de ellos, y
# el consumidor tiene que saber atender los mensajes antes de que el disparador
# se los entregue.

# Detiene la ejecución si algún comando falla
set -e

# --- Configuración de las Colas ---
# Sintaxis: "cola|lambda_que_consume|lambda_que_envía|visibilidad_s|retención_s|recepciones|descripción"
#
# Todas son FIFO: el nombre termina en .fifo y la cola de fallidos se llama
# igual con -dlq. Un mensaje que no se atiende se reintenta hasta
# `recepciones` veces y después espera en la de fallidos 14 días.
#
# La visibilidad es el tiempo que un mensaje queda oculto mientras se atiende:
# AWS pide al menos 6 veces el tiempo máximo del Lambda consumidor (120 s).

QUEUES=(
    # SmartBilling → SmartDecisions (6-nov-2026). Cada venta y cada producto de
    # un comercio con «Enviar a SmartDecisions» activado se deja acá como la
    # petición HTTP que es (ruta, cuerpo y token del cajero), en la fila de su
    # comercio: COMMERCIAL las atiende en orden, así dos ventas del mismo
    # comercio nunca reescriben su dataset a la vez. Cola y no llamada HTTP:
    # un Lambda se congela al responder y la llamada puede no salir.
    "commercial-live-requests.fifo|commercial-handler-service|billing-handler-service|720|345600|3|Peticiones de SmartBilling que COMMERCIAL atiende en orden"
)

DLQ_RETENTION_SECONDS=1209600
REGION="us-east-1"
PROFILE="deploy_ml"

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "$PROFILE")

# Crea la cola o, si ya existe, le deja los atributos de esta lista.
ensure_queue() {
    local name="$1" attributes="$2" url
    if url=$(aws sqs get-queue-url --queue-name "$name" --region "$REGION" \
            --profile "$PROFILE" --query QueueUrl --output text 2>/dev/null); then
        # FifoQueue no se puede cambiar después de creada: se quita al actualizar.
        local updatable
        updatable=$(python3 -c "import json,sys; a=json.loads(sys.argv[1]); a.pop('FifoQueue'); print(json.dumps(a))" "$attributes")
        aws sqs set-queue-attributes --queue-url "$url" --attributes "$updatable" \
            --region "$REGION" --profile "$PROFILE"
        echo "  Ya existía, atributos al día: $name"
    else
        aws sqs create-queue --queue-name "$name" --attributes "$attributes" \
            --region "$REGION" --profile "$PROFILE" --output text --query QueueUrl >/dev/null
        echo "  Creada: $name"
    fi
}

# El nombre del rol de ejecución de un Lambda, leído del Lambda mismo.
role_of() {
    aws lambda get-function-configuration --function-name "$1" --region "$REGION" \
        --profile "$PROFILE" --query Role --output text | sed 's#.*/##'
}

echo "Iniciando la gestión de colas SQS..."

for queue_config in "${QUEUES[@]}"; do
    IFS='|' read -r QUEUE CONSUMER PRODUCER VISIBILITY RETENTION RECEIVES DESCRIPTION <<< "$queue_config"

    DLQ="${QUEUE%.fifo}-dlq.fifo"
    QUEUE_ARN="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${QUEUE}"
    DLQ_ARN="arn:aws:sqs:${REGION}:${ACCOUNT_ID}:${DLQ}"

    echo ""
    echo "Cola: '$QUEUE' ($DESCRIPTION)"
    echo "  $PRODUCER -> cola -> $CONSUMER"

    for function in "$CONSUMER" "$PRODUCER"; do
        if ! aws lambda get-function --function-name "$function" \
                --region "$REGION" --profile "$PROFILE" &>/dev/null; then
            echo "  ERROR: el Lambda '$function' no existe. Despliégalo primero."
            exit 1
        fi
    done

    ensure_queue "$DLQ" "{\"FifoQueue\":\"true\",\"MessageRetentionPeriod\":\"${DLQ_RETENTION_SECONDS}\"}"
    REDRIVE=$(python3 -c "import json,sys; print(json.dumps({'deadLetterTargetArn': sys.argv[1], 'maxReceiveCount': sys.argv[2]}))" "$DLQ_ARN" "$RECEIVES")
    ATTRIBUTES=$(python3 -c "import json,sys; print(json.dumps({'FifoQueue':'true','VisibilityTimeout':sys.argv[1],'MessageRetentionPeriod':sys.argv[2],'RedrivePolicy':sys.argv[3]}))" "$VISIBILITY" "$RETENTION" "$REDRIVE")
    ensure_queue "$QUEUE" "$ATTRIBUTES"

    # put-role-policy crea o reemplaza la política por su nombre: repetirlo
    # deja el mismo permiso, nunca uno duplicado.
    aws iam put-role-policy --role-name "$(role_of "$PRODUCER")" \
        --policy-name "${QUEUE%.fifo}-send" --profile "$PROFILE" \
        --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":\"sqs:SendMessage\",\"Resource\":\"${QUEUE_ARN}\"}]}"
    aws iam put-role-policy --role-name "$(role_of "$CONSUMER")" \
        --policy-name "${QUEUE%.fifo}-consume" --profile "$PROFILE" \
        --policy-document "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"sqs:ReceiveMessage\",\"sqs:DeleteMessage\",\"sqs:GetQueueAttributes\",\"sqs:ChangeMessageVisibility\"],\"Resource\":\"${QUEUE_ARN}\"}]}"
    echo "  Permisos: $PRODUCER envía, $CONSUMER consume."

    # Un mensaje por invocación, y el consumidor informa cuál falló
    # (ReportBatchItemFailures) para que sólo ése se reintente.
    MAPPING=$(aws lambda list-event-source-mappings --function-name "$CONSUMER" \
        --event-source-arn "$QUEUE_ARN" --region "$REGION" --profile "$PROFILE" \
        --query 'EventSourceMappings[0].UUID' --output text)
    if [ "$MAPPING" = "None" ] || [ -z "$MAPPING" ]; then
        # El permiso recién dado tarda unos segundos en verse en IAM.
        for attempt in 1 2 3 4 5 6; do
            if aws lambda create-event-source-mapping --function-name "$CONSUMER" \
                    --event-source-arn "$QUEUE_ARN" --batch-size 1 \
                    --function-response-types ReportBatchItemFailures --enabled \
                    --region "$REGION" --profile "$PROFILE" &>/dev/null; then
                echo "  Disparador creado y activado."
                break
            fi
            [ "$attempt" = 6 ] && { echo "  ERROR: no se pudo crear el disparador."; exit 1; }
            sleep 10
        done
    else
        aws lambda update-event-source-mapping --uuid "$MAPPING" --batch-size 1 \
            --function-response-types ReportBatchItemFailures --enabled \
            --region "$REGION" --profile "$PROFILE" --output text --query State >/dev/null
        echo "  Disparador ya existía, activado."
    fi
done

echo ""
echo "Proceso de creación de colas finalizado con éxito. ✅"
echo ""
echo "Para ver si algo quedó en una cola de fallidos:"
echo "  aws sqs get-queue-attributes --queue-url \\"
echo "      https://sqs.${REGION}.amazonaws.com/${ACCOUNT_ID}/commercial-live-requests-dlq.fifo \\"
echo "      --attribute-names ApproximateNumberOfMessages --profile $PROFILE"
