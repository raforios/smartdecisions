#!/bin/bash

# Este script crea y despliega toda la infraestructura necesaria para la API SmartDecisions.

# Detiene la ejecución si algún comando falla
set -e

REGION="us-east-1" # Asegúrate de que esta sea tu región de AWS
PROFILE="deploy_ml"

echo "Iniciando el despliegue y construcción de la infraestructura de SmartDecisions..."

./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/auth
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/events
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/files --skip-table-creation
./build_and_deploy.sh --path /Users/rafael/Work/projects/back/SmartDecisions/app/services/ml_functions --skip-table-creation

./create_dynamodb_tables.sh

sleep 180

./configure_https_and_api_domain.sh
./map_api_base_paths.sh

echo "Proceso de despliegue finalizado con éxito. ✅"
