#!/bin/bash

# Local DynamoDB management script for the CMS service.
# Provisions the four content tables (news, documents, slides, entities).
# Reuses the same container as mining_summit (single DynamoDB Local
# instance on :3100), so this script only adds tables.

CONTAINER_NAME='dynamodb-local-container'
IMAGE_NAME='amazon/dynamodb-local'
PORT_MAPPING='3100:8000'
ENDPOINT_URL='http://localhost:3100'
REGION='us-east-1'

# Each CMS table keys items by a single uuid `id`. Per-entity tables keep
# the model simple; switch to a GSI on (lang, sort_order) when scan volume
# becomes a bottleneck.
TABLES=(
    '{ "name": "t_cms_news", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
    '{ "name": "t_cms_documents", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
    '{ "name": "t_cms_slides", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
    '{ "name": "t_cms_entities", "attributes": "AttributeName=id,AttributeType=S", "keys": "AttributeName=id,KeyType=HASH" }'
)

echo '==================================================='
echo '  CMS - DynamoDB Local Bootstrap'
echo '==================================================='
echo ''

# --- Step 1: Docker container management ---
echo "Checking Docker container '${CONTAINER_NAME}'..."

if docker ps --filter "name=${CONTAINER_NAME}" --filter 'status=running' --quiet | grep -q .; then
    echo "Container '${CONTAINER_NAME}' is already running."
elif docker ps -a --filter "name=${CONTAINER_NAME}" --quiet | grep -q .; then
    echo "Container '${CONTAINER_NAME}' exists but is stopped. Starting it..."
    docker start "${CONTAINER_NAME}"
    if [ $? -ne 0 ]; then
        echo "ERROR starting '${CONTAINER_NAME}'."
        exit 1
    fi
else
    echo "Creating container '${CONTAINER_NAME}'..."
    docker run -d --name "${CONTAINER_NAME}" -p "${PORT_MAPPING}" "${IMAGE_NAME}"
    if [ $? -ne 0 ]; then
        echo "ERROR creating '${CONTAINER_NAME}'."
        exit 1
    fi
fi
echo ''

# --- Step 2: Wait for DynamoDB Local to be ready ---
check_dynamodb_ready() {
    local retries=15
    local count=0
    local sleep_time=2
    while ! aws dynamodb list-tables --endpoint-url "${ENDPOINT_URL}" --region "${REGION}" &>/dev/null; do
        if [ $count -ge $retries ]; then
            echo "ERROR: DynamoDB Local not ready after ${retries} retries."
            return 1
        fi
        echo "  Waiting for DynamoDB Local... (attempt $((count + 1))/${retries})"
        sleep "${sleep_time}"
        count=$((count + 1))
    done
    echo 'DynamoDB Local is ready.'
    return 0
}

check_dynamodb_ready
if [ $? -ne 0 ]; then
    exit 1
fi
echo ''

# --- Step 3: Table creation helper ---
create_table_if_missing() {
    local table_name="$1"
    local attribute_defs="$2"
    local key_schema="$3"

    echo "Checking table '${table_name}'..."
    if aws dynamodb list-tables --endpoint-url "${ENDPOINT_URL}" --region "${REGION}" | grep -q "\"${table_name}\""; then
        echo "Table '${table_name}' already exists. Skipping creation."
        return
    fi

    echo "Creating table '${table_name}'..."
    aws dynamodb create-table \
        --table-name "${table_name}" \
        --attribute-definitions ${attribute_defs} \
        --key-schema ${key_schema} \
        --provisioned-throughput ReadCapacityUnits=1,WriteCapacityUnits=1 \
        --region "${REGION}" \
        --endpoint-url "${ENDPOINT_URL}"

    if [ $? -ne 0 ]; then
        echo "ERROR creating table '${table_name}'."
        exit 1
    fi

    aws dynamodb wait table-exists --table-name "${table_name}" --endpoint-url "${ENDPOINT_URL}" --region "${REGION}"
    if [ $? -ne 0 ]; then
        echo "ERROR: table '${table_name}' did not become active."
        exit 1
    fi
    echo "Table '${table_name}' is active."
    echo ''
}

# --- Step 4: Iterate and provision all tables ---
for table_json in "${TABLES[@]}"; do
    table_name=$(echo "${table_json}" | jq -r '.name')
    attribute_defs=$(echo "${table_json}" | jq -r '.attributes')
    key_schema=$(echo "${table_json}" | jq -r '.keys')
    create_table_if_missing "${table_name}" "${attribute_defs}" "${key_schema}"
done

echo '==================================================='
echo '  CMS DynamoDB bootstrap complete.'
echo '==================================================='
