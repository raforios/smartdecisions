#!/bin/bash
# Recreate the `optimization_routes` DynamoDB table in AWS so it matches
# the schema the optimization service expects:
#
#   - Partition key:  route_day_key  (S)   formatted as "{route_id}#{day}"
#   - Sort key:       client_id      (N)
#
# This lets the service hit it with a single Query call per (route_id, day)
# pair, which is O(items) instead of a full Scan of the table.
#
# Usage:
#   chmod +x scripts/recreate_aws_table.sh
#   AWS_PROFILE=deploy_ml ./scripts/recreate_aws_table.sh
#
# WARNING: this drops the existing table. Re-run any data seeding after.

set -euo pipefail

TABLE_NAME="optimization_routes"
REGION="${AWS_REGION:-us-east-1}"
PROFILE_FLAG=""
if [ -n "${AWS_PROFILE:-}" ]; then
    PROFILE_FLAG="--profile ${AWS_PROFILE}"
fi

echo "=================================================="
echo "  Recreate AWS DynamoDB table: ${TABLE_NAME}"
echo "  Region:  ${REGION}"
echo "  Profile: ${AWS_PROFILE:-default}"
echo "=================================================="

read -p "This will DELETE the existing '${TABLE_NAME}' table and re-create it. Continue? (yes/[no]): " confirm
if [ "${confirm}" != "yes" ]; then
    echo "Aborted."
    exit 0
fi

echo ""
echo "Deleting table '${TABLE_NAME}'..."
aws dynamodb delete-table \
    --table-name "${TABLE_NAME}" \
    --region "${REGION}" \
    ${PROFILE_FLAG} >/dev/null 2>&1 || true

echo "Waiting for table to disappear..."
aws dynamodb wait table-not-exists \
    --table-name "${TABLE_NAME}" \
    --region "${REGION}" \
    ${PROFILE_FLAG} || true

echo ""
echo "Creating table '${TABLE_NAME}' with composite key (route_day_key, client_id)..."
aws dynamodb create-table \
    --table-name "${TABLE_NAME}" \
    --attribute-definitions \
        AttributeName=route_day_key,AttributeType=S \
        AttributeName=client_id,AttributeType=N \
    --key-schema \
        AttributeName=route_day_key,KeyType=HASH \
        AttributeName=client_id,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --region "${REGION}" \
    ${PROFILE_FLAG}

aws dynamodb wait table-exists \
    --table-name "${TABLE_NAME}" \
    --region "${REGION}" \
    ${PROFILE_FLAG}

echo ""
echo "Table '${TABLE_NAME}' is active in AWS."
echo "Next: seed it via"
echo "  PYTHONPATH=. python scripts/seed_from_csv.py --csv scripts/sample_routes.csv"
echo "(no --endpoint-url flag → boto3 will use AWS through your default profile)"
