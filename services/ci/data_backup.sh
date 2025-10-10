#!/bin/bash

set -e          # Terminar inmediatamente si un comando falla.
set -o pipefail # Terminar si un comando en un pipeline falla.


# Backup
aws rds create-db-snapshot \
    --db-snapshot-identifier binaria-backup-final-$(date +%Y%m%d%H%M) \
    --db-instance-identifier api-binaria-mysql-db \
    --region us-east-1 \
    --profile deploy_binaria


# Await
aws rds wait db-snapshot-available \
    --db-snapshot-identifier binaria-backup-final-$(date +%Y%m%d%H%M) \
    --region us-east-1 \
    --profile deploy_binaria

# Restore
# 3.1. Restaurar el Snapshot a una NUEVA instancia con nombre temporal:
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier api-binaria-mysql-db-restored \
    --db-snapshot-identifier binaria-backup-final-202510090746 \
    --db-instance-class db.t3.micro \
    --publicly-accessible \
    --vpc-security-group-ids sg-0eda113f539339681 \
    --db-subnet-group-name api-binaria-rds-subnet-group \
    --region us-east-1 \
    --profile deploy_binaria

# Delete RDS
aws rds delete-db-subnet-group --db-subnet-group-name api-binaria-rds-subnet-group --region us-east-1 --profile deploy_binaria
aws rds delete-db-subnet-group --db-subnet-group-name api-binaria-rds-subnet-group --region us-east-1 --profile deploy_binaria 2>/dev/null || true

