#!/bin/bash

# =============================================================================
# Script de Pruebas E2E - Mining Analysis Service (POSTMAN ALIGNED)
# =============================================================================
# REFACTOR: Autenticación vía External Auth Service (AWS API Gateway)
# =============================================================================

set -eo pipefail

# --- CONFIGURACIÓN (Basada en Postman Environment) ---
BASE_URL="http://localhost:3020"
AUTH_URL="https://32652ile50.execute-api.us-east-1.amazonaws.com/v1/auth"
EMAIL="raforios@gmail.com"
PASSWORD="MotoPassword"
CSV_FILE="../../../data/cotizacion_minerales_consolidado.csv"
DELIMITER=";"

# Colors
readonly GREEN='\033[0;32m'
readonly RED='\033[0;31m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

PASSED=0
FAILED=0
TOKEN=""

# --- FUNCIONES ---
log_test() { echo -e "${YELLOW}[TEST]${NC} $1..."; }
parse_json() { echo "$1" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('$2', ''))" 2>/dev/null; }

test_authentication() {
  log_test "Autenticando con Central Auth Service ($AUTH_URL)"
  
  # Login con JSON payload según la Collection de Postman
  local response=$(curl -s -X POST "$AUTH_URL/login" \
    -H "Content-Type: application/json" \
    -d "{ \"email\": \"$EMAIL\", \"password\": \"$PASSWORD\" }")
  
  TOKEN=$(parse_json "$response" "access_token")
  
  if [ -n "$TOKEN" ]; then
    echo -e "${GREEN}✅ Autenticación Exitosa.${NC}"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}❌ Error de Autenticación.${NC}"
    echo "Respuesta: $response"
    exit 1
  fi
}

test_etl_process() {
  log_test "Ejecutando ETL en Mining Service ($BASE_URL)"
  
  local response=$(curl -s -X POST "$BASE_URL/v1/mining-analysis/etl/upload?delimiter=$DELIMITER" \
    -H "Authorization: Bearer $TOKEN" \
    -F "file=@$CSV_FILE")
  
  local status=$(parse_json "$response" "status")
  if [ "$status" = "success" ]; then
    echo -e "${GREEN}✅ ETL Completado.${NC}"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}❌ Fallo en ETL.${NC}"
    echo "$response"
    FAILED=$((FAILED + 1))
  fi
}

test_get_prices() {
  log_test "Verificando persistencia de datos"
  
  local status_code=$(curl -s -o /dev/null -w "%{http_code}" \
    -X GET "$BASE_URL/v1/mining-analysis/prices" \
    -H "Authorization: Bearer $TOKEN")
  
  if [ "$status_code" = "200" ]; then
    echo -e "${GREEN}✅ Consulta de precios exitosa (HTTP 200).${NC}"
    PASSED=$((PASSED + 1))
  else
    echo -e "${RED}❌ Error al consultar precios (HTTP $status_code).${NC}"
    FAILED=$((FAILED + 1))
  fi
}

# --- EJECUCIÓN ---
echo "🚀 Iniciando Pruebas E2E - Mining Analysis"
test_authentication
test_etl_process
test_get_prices

echo -e "\n${BLUE}RESUMEN:${NC} PASSED: $PASSED | FAILED: $FAILED"
[ $FAILED -eq 0 ] && exit 0 || exit 1
