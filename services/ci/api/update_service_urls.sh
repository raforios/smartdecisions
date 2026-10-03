#!/bin/bash

# Apunta las llamadas entre servicios al dominio único (api.bearsoft.com.bo).
#
# Los servicios se llaman entre sí con *_SERVICE_URL + "/v1/<servicio>/...". Con
# el dominio, la base es la misma para todos: una URL que no cambia si un API
# se recrea y su ID de execute-api cambia.
#
# Se corre SÓLO después de que setup_api_domain.sh dé 401 en su prueba de humo:
# antes de eso, cambiar las URLs deja a los servicios hablando a un dominio que
# todavía no responde. Después hay que redesplegar los servicios que cambiaron,
# porque el .env viaja a las variables del Lambda en el despliegue.
#
# Uso:
#   ./update_service_urls.sh          # informa qué cambiaría
#   ./update_service_urls.sh --yes    # escribe los .env

set -e

BASE_URL="https://api.bearsoft.com.bo"
SERVICES_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# Servicios propios cuyos .env llaman a otros servicios. Los de clientes
# (TRADE, FORMS, LOCALIZATION, CMS, MINING_SUMMIT) no se tocan.
SERVICES=(ai analytics billing ingest mining_analysis optimization quotes)
VARIABLES=(EVENTS_SERVICE_URL FILES_SERVICE_URL INGEST_SERVICE_URL QUOTES_SERVICE_URL)

WRITE=false
[ "$1" == "--yes" ] && WRITE=true

for SERVICE in "${SERVICES[@]}"; do
    ENV_FILE="$SERVICES_DIR/$SERVICE/.env"
    [ -f "$ENV_FILE" ] || { echo "$SERVICE: sin .env, se omite."; continue; }
    for VARIABLE in "${VARIABLES[@]}"; do
        CURRENT=$(grep -E "^${VARIABLE}=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d "'\"")
        [ -n "$CURRENT" ] || continue
        if [ "$CURRENT" == "$BASE_URL" ]; then
            echo "$SERVICE: $VARIABLE ya apunta a $BASE_URL"
            continue
        fi
        echo "$SERVICE: $VARIABLE $CURRENT -> $BASE_URL"
        if $WRITE; then
            sed -i.bak -E "s|^${VARIABLE}=.*|${VARIABLE}='${BASE_URL}'|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
        fi
    done
done

if $WRITE; then
    echo "Escrito. Redespliega los servicios que cambiaron (start.sh --redeploy)."
else
    echo "Simulación: no se escribió nada. Repite con --yes."
fi
