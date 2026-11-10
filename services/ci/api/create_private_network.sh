#!/bin/bash

# Crea la red privada y la instancia RDS PostgreSQL que comparten los servicios
# transaccionales (Rafael, 10-nov-2026): el WMS, BILLING, COMMERCIAL y FINANCE.
# Una VPC con una subred pública (sólo para la instancia NAT) y dos privadas
# (los Lambdas y la base), una instancia NAT chica en EC2 para que los Lambdas
# de la red privada lleguen a AUTH, EVENTS y FILES, una salida directa a
# DynamoDB (los servicios siguen usando sus tablas) y el RDS, que no se expone
# a internet.
#
# Una instancia, una base de datos por servicio, cada una con su propio usuario
# y contraseña: PostgreSQL no permite consultar entre bases distintas, así que
# ningún servicio puede leer las tablas de otro (CLAUDE.md §4).
#
# Por qué así (Rafael, 9-nov-2026): sólo el costo que no se puede evitar. El
# NAT Gateway cuesta ~US$ 33 al mes; la instancia NAT t4g.nano, ~US$ 7,40 con
# su IP pública. Juntos con el RDS db.t4g.micro, ~US$ 22 al mes.
#
# Es idempotente: cada recurso se busca por su etiqueta Name y sólo se crea si
# falta. No borra ni modifica lo que existe.
#
# Va ANTES del primer despliegue de un servicio con base de datos: al terminar
# imprime VPC_ID, PRIVATE_SUBNET_IDS e INTERNAL_SG_ID para el deploy.config de
# cada uno (build_and_deploy.sh pone el Lambda en la red privada cuando los
# tres están), DB_HOST para su .env, y el SQL que crea la base y el usuario de
# cada servicio.
#
# Pide la contraseña del usuario maestro al crear la instancia; no se guarda en
# ningún archivo ni en Secrets Manager (Rafael, 10-nov-2026: sin costos
# evitables). El maestro sólo crea bases y usuarios: ningún servicio lo usa.

# Detiene la ejecución si algún comando falla
set -e

REGION="us-east-1"
PROFILE="deploy_ml"
PROJECT="bearsoft-private"

# --- Red ---
VPC_CIDR="10.40.0.0/16"
PUBLIC_CIDR="10.40.0.0/24"
# RDS exige subredes en dos zonas aunque la base viva en una sola.
PRIVATE_CIDRS=("10.40.10.0/24" "10.40.11.0/24")

# --- Instancia NAT ---
# fck-nat: imagen de código abierto (Amazon Linux 2023) ya configurada como
# NAT; su dueño publica las AMI con esta cuenta. Se busca la más reciente
# para ARM, que es la arquitectura de la t4g.
NAT_INSTANCE_TYPE="t4g.nano"
NAT_AMI_OWNER="568608671756"
NAT_AMI_NAME="fck-nat-al2023-*-arm64-ebs"

# --- Base de datos ---
DB_INSTANCE_ID="bearsoft-postgres"
DB_INSTANCE_CLASS="db.t4g.micro"
DB_STORAGE_GB=20
DB_USERNAME="bearsoft_admin"
# Una base y un usuario por servicio transaccional; agregar uno es sumarlo acá.
SERVICE_DATABASES=(wms billing commercial finance)
DB_BACKUP_DAYS=7

aws_cli() {
    aws "$@" --region "$REGION" --profile "$PROFILE"
}

# El id del recurso con esa etiqueta Name, o vacío.
find_tagged() {
    local kind="$1" name="$2" query="$3"
    aws_cli ec2 "describe-${kind}" --filters "Name=tag:Name,Values=${name}" \
        --query "$query" --output text | sed 's/^None$//'
}

tag() {
    aws_cli ec2 create-tags --resources "$1" \
        --tags "Key=Name,Value=$2" "Key=Project,Value=${PROJECT}"
}

AZS=($(aws_cli ec2 describe-availability-zones --query 'AvailabilityZones[0:2].ZoneName' --output text))

echo "Red privada y base PostgreSQL compartida (${REGION}, perfil ${PROFILE})"

# ---------------------------------------------------------------- VPC ---
VPC_ID=$(find_tagged vpcs "${PROJECT}-vpc" 'Vpcs[0].VpcId')
if [ -z "$VPC_ID" ]; then
    VPC_ID=$(aws_cli ec2 create-vpc --cidr-block "$VPC_CIDR" --query Vpc.VpcId --output text)
    aws_cli ec2 wait vpc-available --vpc-ids "$VPC_ID"
    # El endpoint del RDS se resuelve por DNS dentro de la VPC.
    aws_cli ec2 modify-vpc-attribute --vpc-id "$VPC_ID" --enable-dns-hostnames
    tag "$VPC_ID" "${PROJECT}-vpc"
    echo "  VPC creada: $VPC_ID"
else
    echo "  VPC existente: $VPC_ID"
fi

IGW_ID=$(find_tagged internet-gateways "${PROJECT}-igw" 'InternetGateways[0].InternetGatewayId')
if [ -z "$IGW_ID" ]; then
    IGW_ID=$(aws_cli ec2 create-internet-gateway --query InternetGateway.InternetGatewayId --output text)
    aws_cli ec2 attach-internet-gateway --internet-gateway-id "$IGW_ID" --vpc-id "$VPC_ID"
    tag "$IGW_ID" "${PROJECT}-igw"
    echo "  Puerta a internet creada: $IGW_ID"
fi

# ------------------------------------------------------------ Subredes ---
ensure_subnet() {
    local name="$1" cidr="$2" zone="$3" id
    id=$(find_tagged subnets "$name" 'Subnets[0].SubnetId')
    if [ -z "$id" ]; then
        id=$(aws_cli ec2 create-subnet --vpc-id "$VPC_ID" --cidr-block "$cidr" \
            --availability-zone "$zone" --query Subnet.SubnetId --output text)
        tag "$id" "$name"
        echo "  Subred creada: $name ($cidr, $zone)" >&2
    fi
    echo "$id"
}

PUBLIC_SUBNET=$(ensure_subnet "${PROJECT}-public-a" "$PUBLIC_CIDR" "${AZS[0]}")
PRIVATE_SUBNETS=()
for i in 0 1; do
    PRIVATE_SUBNETS+=("$(ensure_subnet "${PROJECT}-private-${i}" "${PRIVATE_CIDRS[$i]}" "${AZS[$i]}")")
done

PUBLIC_RTB=$(find_tagged route-tables "${PROJECT}-public-rtb" 'RouteTables[0].RouteTableId')
if [ -z "$PUBLIC_RTB" ]; then
    PUBLIC_RTB=$(aws_cli ec2 create-route-table --vpc-id "$VPC_ID" --query RouteTable.RouteTableId --output text)
    tag "$PUBLIC_RTB" "${PROJECT}-public-rtb"
    aws_cli ec2 create-route --route-table-id "$PUBLIC_RTB" \
        --destination-cidr-block 0.0.0.0/0 --gateway-id "$IGW_ID" >/dev/null
    aws_cli ec2 associate-route-table --route-table-id "$PUBLIC_RTB" --subnet-id "$PUBLIC_SUBNET" >/dev/null
    echo "  Rutas de la subred pública: a internet por $IGW_ID"
fi

# -------------------------------------------------- Grupos de seguridad ---
ensure_sg() {
    local name="$1" description="$2" id
    id=$(aws_cli ec2 describe-security-groups \
        --filters "Name=vpc-id,Values=${VPC_ID}" "Name=group-name,Values=${name}" \
        --query 'SecurityGroups[0].GroupId' --output text | sed 's/^None$//')
    if [ -z "$id" ]; then
        id=$(aws_cli ec2 create-security-group --group-name "$name" \
            --description "$description" --vpc-id "$VPC_ID" --query GroupId --output text)
        tag "$id" "$name"
        echo "  Grupo de seguridad creado: $name" >&2
        echo "new:$id"
        return
    fi
    echo "$id"
}

# Los Lambdas: salen a donde necesiten, nadie entra.
LAMBDA_SG=$(ensure_sg "${PROJECT}-lambda-sg" "BearSoft private Lambdas")
LAMBDA_SG="${LAMBDA_SG#new:}"

# La base: sólo los Lambdas de la red privada, sólo PostgreSQL.
DB_SG=$(ensure_sg "${PROJECT}-db-sg" "BearSoft PostgreSQL")
if [[ "$DB_SG" == new:* ]]; then
    DB_SG="${DB_SG#new:}"
    aws_cli ec2 authorize-security-group-ingress --group-id "$DB_SG" \
        --protocol tcp --port 5432 --source-group "$LAMBDA_SG" >/dev/null
fi

# La instancia NAT: recibe todo lo que sale de la VPC y no acepta nada de afuera.
NAT_SG=$(ensure_sg "${PROJECT}-nat-sg" "BearSoft NAT instance")
if [[ "$NAT_SG" == new:* ]]; then
    NAT_SG="${NAT_SG#new:}"
    aws_cli ec2 authorize-security-group-ingress --group-id "$NAT_SG" \
        --protocol -1 --cidr "$VPC_CIDR" >/dev/null
fi

# ------------------------------------------------------ Instancia NAT ---
NAT_INSTANCE=$(aws_cli ec2 describe-instances \
    --filters "Name=tag:Name,Values=${PROJECT}-nat" "Name=instance-state-name,Values=pending,running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text | sed 's/^None$//')
if [ -z "$NAT_INSTANCE" ]; then
    NAT_AMI=$(aws_cli ec2 describe-images --owners "$NAT_AMI_OWNER" \
        --filters "Name=name,Values=${NAT_AMI_NAME}" "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' --output text)
    NAT_INSTANCE=$(aws_cli ec2 run-instances --image-id "$NAT_AMI" \
        --instance-type "$NAT_INSTANCE_TYPE" --subnet-id "$PUBLIC_SUBNET" \
        --security-group-ids "$NAT_SG" --associate-public-ip-address \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=${PROJECT}-nat},{Key=Project,Value=${PROJECT}}]" \
        --query 'Instances[0].InstanceId' --output text)
    aws_cli ec2 wait instance-running --instance-ids "$NAT_INSTANCE"
    # Un NAT reenvía paquetes que no son suyos: sin esto la instancia los descarta.
    aws_cli ec2 modify-instance-attribute --instance-id "$NAT_INSTANCE" --no-source-dest-check
    echo "  Instancia NAT creada: $NAT_INSTANCE ($NAT_INSTANCE_TYPE, $NAT_AMI)"

    # Se repone sola: si falla el hardware de AWS, la recupera en otro; si se
    # cuelga el sistema, la reinicia. Cada alarma cuesta ~US$ 0,10 al mes.
    aws_cli cloudwatch put-metric-alarm --alarm-name "${PROJECT}-nat-recover" \
        --namespace AWS/EC2 --metric-name StatusCheckFailed_System \
        --dimensions "Name=InstanceId,Value=${NAT_INSTANCE}" \
        --statistic Maximum --period 60 --evaluation-periods 2 --threshold 1 \
        --comparison-operator GreaterThanOrEqualToThreshold \
        --alarm-actions "arn:aws:automate:${REGION}:ec2:recover"
    aws_cli cloudwatch put-metric-alarm --alarm-name "${PROJECT}-nat-reboot" \
        --namespace AWS/EC2 --metric-name StatusCheckFailed_Instance \
        --dimensions "Name=InstanceId,Value=${NAT_INSTANCE}" \
        --statistic Maximum --period 60 --evaluation-periods 3 --threshold 1 \
        --comparison-operator GreaterThanOrEqualToThreshold \
        --alarm-actions "arn:aws:automate:${REGION}:ec2:reboot"
    echo "  Alarmas de recuperación y reinicio de la instancia NAT"
else
    echo "  Instancia NAT existente: $NAT_INSTANCE"
fi

PRIVATE_RTB=$(find_tagged route-tables "${PROJECT}-private-rtb" 'RouteTables[0].RouteTableId')
if [ -z "$PRIVATE_RTB" ]; then
    PRIVATE_RTB=$(aws_cli ec2 create-route-table --vpc-id "$VPC_ID" --query RouteTable.RouteTableId --output text)
    tag "$PRIVATE_RTB" "${PROJECT}-private-rtb"
    aws_cli ec2 create-route --route-table-id "$PRIVATE_RTB" \
        --destination-cidr-block 0.0.0.0/0 --instance-id "$NAT_INSTANCE" >/dev/null
    for subnet in "${PRIVATE_SUBNETS[@]}"; do
        aws_cli ec2 associate-route-table --route-table-id "$PRIVATE_RTB" --subnet-id "$subnet" >/dev/null
    done
    echo "  Rutas de las subredes privadas: a internet por la instancia NAT"
fi

# Las tablas DynamoDB se alcanzan sin pasar por la instancia NAT: el endpoint de
# tipo gateway es gratuito y no tiene límite de tráfico.
DYNAMO_ENDPOINT=$(aws_cli ec2 describe-vpc-endpoints \
    --filters "Name=vpc-id,Values=${VPC_ID}" "Name=service-name,Values=com.amazonaws.${REGION}.dynamodb" \
    --query 'VpcEndpoints[0].VpcEndpointId' --output text | sed 's/^None$//')
if [ -z "$DYNAMO_ENDPOINT" ]; then
    aws_cli ec2 create-vpc-endpoint --vpc-id "$VPC_ID" --vpc-endpoint-type Gateway \
        --service-name "com.amazonaws.${REGION}.dynamodb" --route-table-ids "$PRIVATE_RTB" >/dev/null
    echo "  Salida directa a DynamoDB desde las subredes privadas"
fi

# ------------------------------------------------------ Base de datos ---
DB_SUBNET_GROUP="${PROJECT}-db-subnets"
if ! aws_cli rds describe-db-subnet-groups --db-subnet-group-name "$DB_SUBNET_GROUP" >/dev/null 2>&1; then
    aws_cli rds create-db-subnet-group --db-subnet-group-name "$DB_SUBNET_GROUP" \
        --db-subnet-group-description "BearSoft private subnets" \
        --subnet-ids "${PRIVATE_SUBNETS[@]}" >/dev/null
    echo "  Grupo de subredes de la base creado: $DB_SUBNET_GROUP"
fi

if ! aws_cli rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" >/dev/null 2>&1; then
    echo -n "  Contraseña del usuario ${DB_USERNAME} (mínimo 8 caracteres; no se guarda): "
    read -rs DB_PASSWORD
    echo ""
    # Sin versión: la que AWS tiene por defecto para PostgreSQL, que desde la
    # 15 exige SSL (rds.force_ssl = 1) en su grupo de parámetros por defecto.
    aws_cli rds create-db-instance --db-instance-identifier "$DB_INSTANCE_ID" \
        --engine postgres --db-instance-class "$DB_INSTANCE_CLASS" \
        --allocated-storage "$DB_STORAGE_GB" --storage-type gp3 --storage-encrypted \
        --master-username "$DB_USERNAME" \
        --master-user-password "$DB_PASSWORD" \
        --db-subnet-group-name "$DB_SUBNET_GROUP" --vpc-security-group-ids "$DB_SG" \
        --no-publicly-accessible --no-multi-az \
        --backup-retention-period "$DB_BACKUP_DAYS" --copy-tags-to-snapshot \
        --deletion-protection \
        --tags "Key=Name,Value=${DB_INSTANCE_ID}" "Key=Project,Value=${PROJECT}" >/dev/null
    unset DB_PASSWORD
    echo "  Base creándose: $DB_INSTANCE_ID (tarda 5 a 10 minutos)"
    aws_cli rds wait db-instance-available --db-instance-identifier "$DB_INSTANCE_ID"
else
    echo "  Base existente: $DB_INSTANCE_ID"
fi

DB_HOST=$(aws_cli rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].Endpoint.Address' --output text)
DB_VERSION=$(aws_cli rds describe-db-instances --db-instance-identifier "$DB_INSTANCE_ID" \
    --query 'DBInstances[0].EngineVersion' --output text)
if [ "${DB_VERSION%%.*}" -lt 15 ]; then
    echo "  AVISO: PostgreSQL ${DB_VERSION} no exige SSL por defecto; revisa rds.force_ssl."
fi

PRIVATE_SUBNET_IDS=$(IFS=,; echo "${PRIVATE_SUBNETS[*]}")

echo ""
echo "Listo. Para el deploy.config de cada servicio con base de datos:"
echo "  VPC_ID=${VPC_ID}"
echo "  PRIVATE_SUBNET_IDS=${PRIVATE_SUBNET_IDS}"
echo "  INTERNAL_SG_ID=${LAMBDA_SG}"
echo "Para su .env: DB_HOST=${DB_HOST}, DB_PORT=5432, DB_DIALECT=postgresql+psycopg2, y su DATABASE, DB_USER y DB_PASSWORD."
echo "PostgreSQL ${DB_VERSION}."
echo ""
echo "Una sola vez por servicio, conectado como ${DB_USERNAME} desde la red privada"
echo "(la contraseña de cada usuario la eliges tú y va sólo a su .env):"
for service in "${SERVICE_DATABASES[@]}"; do
    echo "  CREATE ROLE ${service} LOGIN PASSWORD '<contraseña de ${service}>';"
    echo "  CREATE DATABASE ${service} OWNER ${service};"
    echo "  REVOKE ALL ON DATABASE ${service} FROM PUBLIC;"
done
