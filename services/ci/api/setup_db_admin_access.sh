#!/bin/bash

# Deja la instancia NAT de la red privada lista para administrar la base
# PostgreSQL compartida desde AWS Systems Manager (Session Manager), sin claves
# SSH ni puertos abiertos a internet:
#
#   1. Un rol para la instancia con la política administrada de Systems Manager
#      (AmazonSSMManagedInstanceCore), y su perfil de instancia.
#   2. La regla que deja a la instancia NAT llegar al puerto 5432 de la base.
#
# Sin costo. Es idempotente: lo que existe se deja como está.
#
# Después, desde la consola: EC2 → la instancia bearsoft-private-nat →
# Conectar → Session Manager. Ahí se instala el cliente (`sudo dnf install -y
# postgresql17`) y se conecta como el usuario maestro para crear la base y el
# usuario de cada servicio (el SQL lo imprime create_private_network.sh). Las
# contraseñas las escribe quien administra, en esa sesión: no quedan en ningún
# archivo ni en el historial de comandos de Systems Manager.

# Detiene la ejecución si algún comando falla
set -e

REGION="us-east-1"
PROFILE="deploy_ml"
PROJECT="bearsoft-private"
ROLE="${PROJECT}-nat-role"
INSTANCE_PROFILE="${PROJECT}-nat-profile"

aws_cli() {
    aws "$@" --region "$REGION" --profile "$PROFILE"
}

NAT_INSTANCE=$(aws_cli ec2 describe-instances \
    --filters "Name=tag:Name,Values=${PROJECT}-nat" "Name=instance-state-name,Values=running,stopped" \
    --query 'Reservations[0].Instances[0].InstanceId' --output text | sed 's/^None$//')
if [ -z "$NAT_INSTANCE" ]; then
    echo "No existe la instancia ${PROJECT}-nat: corre antes create_private_network.sh."
    exit 1
fi

echo "Acceso de administración a la base por Systems Manager (${NAT_INSTANCE})"

if ! aws_cli iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
    aws_cli iam create-role --role-name "$ROLE" --assume-role-policy-document \
        '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"ec2.amazonaws.com"},"Action":"sts:AssumeRole"}]}' \
        >/dev/null
    echo "  Rol creado: $ROLE"
fi
aws_cli iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore

if ! aws_cli iam get-instance-profile --instance-profile-name "$INSTANCE_PROFILE" >/dev/null 2>&1; then
    aws_cli iam create-instance-profile --instance-profile-name "$INSTANCE_PROFILE" >/dev/null
    aws_cli iam add-role-to-instance-profile --instance-profile-name "$INSTANCE_PROFILE" --role-name "$ROLE"
    # IAM tarda unos segundos en dejar usar un perfil recién creado.
    sleep 10
    echo "  Perfil de instancia creado: $INSTANCE_PROFILE"
fi

CURRENT=$(aws_cli ec2 describe-iam-instance-profile-associations \
    --filters "Name=instance-id,Values=${NAT_INSTANCE}" "Name=state,Values=associated" \
    --query 'IamInstanceProfileAssociations[0].IamInstanceProfile.Arn' --output text | sed 's/^None$//')
if [ -z "$CURRENT" ]; then
    aws_cli ec2 associate-iam-instance-profile --instance-id "$NAT_INSTANCE" \
        --iam-instance-profile "Name=${INSTANCE_PROFILE}" >/dev/null
    echo "  Perfil asociado a la instancia NAT"
    # El agente de una instancia que arrancó sin rol deja de buscar credenciales
    # (10-nov-2026: «not connected» hasta reiniciarla). Al reiniciar toma el
    # rol; la NAT vuelve en un minuto.
    sleep 15
    aws_cli ec2 reboot-instances --instance-ids "$NAT_INSTANCE"
    echo "  Instancia NAT reiniciada para que el agente tome el rol"
fi

group_id() {
    aws_cli ec2 describe-security-groups --filters "Name=group-name,Values=$1" \
        --query 'SecurityGroups[0].GroupId' --output text
}
DB_SG=$(group_id "${PROJECT}-db-sg")
NAT_SG=$(group_id "${PROJECT}-nat-sg")
if aws_cli ec2 authorize-security-group-ingress --group-id "$DB_SG" --protocol tcp --port 5432 \
        --source-group "$NAT_SG" >/dev/null 2>&1; then
    echo "  La instancia NAT ya puede llegar al puerto 5432 de la base"
else
    echo "  Regla de la base hacia la instancia NAT: ya existía"
fi

echo ""
echo "Listo. En unos minutos la instancia aparece en Systems Manager; entra por"
echo "EC2 → ${PROJECT}-nat → Conectar → Session Manager."
