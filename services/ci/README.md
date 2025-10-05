# Gestión de Infraestructura AWS para API de Microservicios

**Nota:** Esta infraestructura se ha construido bajo los principios de Clean Code, Arquitectura Limpia, SOLID y DRY. Toda la configuración es centralizada y parametrizable.

---

## 1. Pre-requisitos

Antes de comenzar, asegúrese de que los siguientes componentes estén instalados y configurados:

1.  **AWS CLI:** Instalado y configurado correctamente.
2.  **Credenciales de AWS:** Un perfil nombrado (`[perfil_aws]`) configurado en `~/.aws/credentials` con permisos para crear/eliminar recursos de IAM, EC2, RDS y VPC.
3.  **Scripts Shell:** Los scripts principales de IaC (`manage_infrastructure.sh`, `build_and_deploy.sh`, *y cualquier otro script de soporte*) deben estar en el directorio actual y tener permisos de ejecución (`chmod +x *.sh`).
4.  **Archivo de Configuración:** El archivo **`infrastructure.config`** debe existir y contener los valores correctos y deseados para el despliegue de la infraestructura central.

---

## 2. Configuración

Revise y modifique el archivo **`infrastructure.config`**. Los parámetros clave a verificar son:

* `REGION`: Región de despliegue de AWS.
* `AWS_PROFILE`: Nombre de su perfil de AWS CLI.
* `VPC_CIDR`: Rango de red deseado.
* `EC2_AMI_ID`: **Crucial**. El ID de la AMI para el SO LINUX de su preferencia en su región.

Además, asegúrese de que cada microservicio tenga su archivo **`deploy.config`** y **`.env`** (si aplica) con los valores específicos necesarios (ej. `FUNCTION_NAME`, `DYNAMODB_TABLE_NAME`).

---

## 3. Despliegue (Creación de Infraestructura)

El script maestro `manage_infrastructure.sh` se encarga de la orquestación de la infraestructura central. Está diseñado para ser **idempotente** (puede ejecutarse múltiples veces) y automáticamente extrae los IDs de red críticos (`VPC_ID`, `PRIVATE_SUBNET_IDS`, `INTERNAL_SG_ID`) y los guarda en `infrastructure.config`.

1.  **Ejecute el comando de configuración de la infraestructura base (VPC, RDS, EC2):**
    ```bash
    ./manage_infrastructure.sh setup
    ```

2.  **Siga las indicaciones:** El script le solicitará la **contraseña maestra de RDS** de forma segura.

3.  **Despliegue de Microservicios (Lambda):** Una vez que la infraestructura central esté lista, proceda a desplegar sus funciones Lambda.

    * El script **`build_and_deploy.sh`** ha sido modificado para **excluir la gestión de API Gateway y SQS**.
    * El script **asociará automáticamente la función Lambda a la VPC** (permitiendo la conexión a la instancia RDS de MySQL) **solo si** las variables `VPC_ID`, `PRIVATE_SUBNET_IDS` e `INTERNAL_SG_ID` están definidas en su respectivo `deploy.config`. Si no están definidas (como es el caso de microservicios sin conexión a RDS), la función se desplegará en la red pública por defecto.

    * **Ejemplo:** Para el microservicio `auth` (sin conexión RDS):
        ```bash
        ./build_and_deploy.sh --path /ruta/a/ms-auth/
        ```

---

## 4. Destrucción (Eliminación de Infraestructura)

El proceso de destrucción está separado en dos partes para una **eliminación controlada**.

1.  **Destruir Recursos de IaC Centrales (VPC, RDS, EC2):**
    ```bash
    ./manage_infrastructure.sh destroy
    ```
    * Este comando le pedirá confirmación antes de eliminar todos los recursos etiquetados como `API_PROJECT` (VPC, subredes, RDS, EC2, KeyPair, etc.).
    * **Nota:** El archivo de clave privada local (`api-project-keypair.pem`) será eliminado.

2.  **Destruir Microservicios (Lambdas, DynamoDB, S3 Artifacts):** Utilice el modo de destrucción incorporado de su script `build_and_deploy.sh` para cada servicio.

    * **Ejemplo:** Para el microservicio `auth`:
        ```bash
        ./build_and_deploy.sh --path /ruta/a/ms-auth/ --destroy
        ```
    * Este comando eliminará la función Lambda, la tabla DynamoDB y los artefactos de código almacenados en S3.
