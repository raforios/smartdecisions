#!/bin/bash

# Despliegue de la plataforma BearSoft (servicios base, SmartDecisions y
# SmartBilling) en un orden fijo, para que nada se pierda entre un despliegue y
# el siguiente.
#
# Uso:
#   ./start.sh                         # todo, desde cero o sobre lo existente
#   ./start.sh --redeploy              # redesplegar todos los servicios
#   ./start.sh --redeploy ingest ai    # sólo esos, en el orden canónico
#   ./start.sh --urls                  # pasar los .env al dominio y redesplegar
#                                      # sólo la configuración (sin reconstruir)
#
# ORDEN Y POR QUÉ
#   1. Tablas DynamoDB (create_dynamodb_tables.sh). Antes que los servicios: un
#      Lambda que arranca contra una tabla que no existe falla en la primera
#      petición, no en el despliegue.
#   2. Servicios BASE: AUTH, EVENTS, FILES, ML_FUNCTIONS. Todos los demás
#      validan el token contra AUTH, auditan en EVENTS y guardan en FILES.
#   3. INGEST y QUOTES. Son los dueños de los datos que otros piden por HTTP:
#      OPTIMIZATION le pide stock y vendedores a INGEST, ANALYTICS le pide el
#      tipo de cambio a QUOTES.
#   4. ANALYTICS, OPTIMIZATION, MINING_ANALYSIS, AI.
#   5. BILLING (SmartBilling).
#   6. Tareas programadas (create_schedules.sh): necesitan los Lambdas.
#   7. Dominio api.bearsoft.com.bo y sus mapeos (setup_api_domain.sh): necesitan
#      los API. Se repite en cada despliegue porque es idempotente y corrige el
#      mapeo si un API se recreó con otro ID.
#
# El CORS de cada API sale del deploy.config de su servicio (CORS_ALLOW_METHODS):
# el que expone PATCH lo declara ahí y build_and_deploy.sh lo aplica siempre.
#
# Los despliegues de frontend (portal) no van acá.

set -e

cd "$(dirname "$0")"
SERVICES_DIR="$(cd ../.. && pwd)"

# Orden canónico: "servicio:banderas de build_and_deploy.sh".
# FILES y ML_FUNCTIONS no tienen tabla propia.
ORDER=(
    "auth:"
    "events:"
    "files:--skip-table-creation"
    "ml_functions:--skip-table-creation"
    "ingest:"
    "quotes:"
    "analytics:"
    "optimization:"
    "mining_analysis:"
    "ai:"
    "billing:"
)

# Servicios cuyos .env llaman a otros servicios (ver update_service_urls.sh).
URL_CONSUMERS=(ai analytics billing ingest mining_analysis optimization quotes)

deploy_service() {
    local SERVICE="$1"
    local FLAGS="$2"
    echo ""
    echo "############ $SERVICE ############"
    # shellcheck disable=SC2086
    ./build_and_deploy.sh --path "$SERVICES_DIR/$SERVICE" $FLAGS
}

# Despliega, en el orden canónico, los servicios pedidos (todos si no se pide ninguno).
deploy_in_order() {
    local EXTRA_FLAGS="$1"
    shift
    local WANTED=" $* "
    for ENTRY in "${ORDER[@]}"; do
        local SERVICE="${ENTRY%%:*}"
        local FLAGS="${ENTRY#*:}"
        if [ $# -eq 0 ] || [[ "$WANTED" == *" $SERVICE "* ]]; then
            deploy_service "$SERVICE" "$FLAGS $EXTRA_FLAGS"
        fi
    done
}

# Dominio y mapeos. Un certificado pendiente (3) o una prueba de humo que no pasó
# (4) no detienen el despliegue de los servicios: se informa y se sigue.
domain_step() {
    set +e
    ./setup_api_domain.sh
    local CODE=$?
    set -e
    case $CODE in
        0) echo "Dominio listo." ;;
        3) echo "AVISO: valida el certificado en Cloudflare y vuelve a correr ./setup_api_domain.sh" ;;
        4) echo "AVISO: el dominio no responde todavía; no cambies las URLs hasta que pase." ;;
        *) echo "Error en setup_api_domain.sh ($CODE)."; exit "$CODE" ;;
    esac
    return $CODE
}

case "$1" in
    --redeploy)
        shift
        deploy_in_order "" "$@"
        domain_step || true
        ;;
    --urls)
        # Sólo con el dominio respondiendo: cambia los .env y vuelve a publicar
        # la configuración de los servicios que cambiaron, sin reconstruirlos.
        if domain_step; then
            ./update_service_urls.sh --yes
            deploy_in_order "--skip-code-update" "${URL_CONSUMERS[@]}"
        else
            echo "Las URLs no se cambiaron."
            exit 1
        fi
        ;;
    "")
        echo "=== 1. Tablas DynamoDB ==="
        ./create_dynamodb_tables.sh
        echo "=== 2-5. Servicios en orden ==="
        deploy_in_order ""
        echo "=== 6. Tareas programadas ==="
        ./create_schedules.sh
        echo "=== 7. Dominio api.bearsoft.com.bo ==="
        domain_step || true
        ;;
    *)
        echo "Uso: $0 [--redeploy [servicio ...] | --urls]"
        exit 1
        ;;
esac

echo ""
echo "Proceso de despliegue finalizado. ✅"
