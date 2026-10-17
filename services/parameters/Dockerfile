# 1. Usamos la imagen base para x86_64 (procesadores Intel/AMD estándar)
FROM public.ecr.aws/lambda/python:3.14

USER root
RUN dnf update -y && dnf install -y \
    gcc gcc-c++ make zip tar gzip python3-devel openblas-devel cargo rust \
    && dnf clean all

WORKDIR /build
COPY requirements.txt .

# 2. Instalamos las dependencias nativas limpias en la carpeta /package
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --target /package -r requirements.txt

# 3. Copiamos el código fuente a /package
COPY . /package/

# 4. Creamos el ZIP desde /package y lo guardamos en /app para que el script lo extraiga
WORKDIR /package
RUN mkdir -p /app && \
    zip -r9 /app/lambda_function.zip . -x "Dockerfile" "build_and_deploy.sh" "deploy.config" "*.venv*" "*venv*" "*__pycache__*"
