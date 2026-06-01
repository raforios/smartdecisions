# # 1. Usamos la imagen base para x86_64 (procesadores Intel/AMD estándar)
# FROM public.ecr.aws/lambda/python:3.14

# USER root
# RUN dnf update -y && dnf install -y \
#     gcc gcc-c++ make zip tar gzip python3-devel openblas-devel cargo rust \
#     && dnf clean all

# WORKDIR /build
# COPY requirements.txt .

# # 2. Instalamos las dependencias nativas limpias en la carpeta /package
# RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
#     pip install --no-cache-dir --target /package -r requirements.txt

# # 3. Copiamos el código fuente a /package
# COPY . /package/

# # 4. Creamos el ZIP desde /package y lo guardamos en /app para que el script lo extraiga
# WORKDIR /package
# RUN mkdir -p /app && \
#     zip -r9 /app/lambda_function.zip . -x "Dockerfile" "build_and_deploy.sh" "deploy.config" "*.venv*" "*venv*" "*__pycache__*"

# Dockerfile

# Etapa 1: Construcción de dependencias
ARG VARIANT=3.13
ARG BUILDPLATFORM=linux/amd64
FROM --platform=${BUILDPLATFORM} python:${VARIANT}-slim


# Instalar dependencias básicas del sistema
RUN apt-get update && apt-get install -y \
    curl build-essential zip && \
    rm -rf /var/lib/apt/lists/*

# Crea directorio de trabajo
WORKDIR /app

# Copia los requisitos
COPY requirements.txt .

# Instala dependencias con compatibilidad para Lambda (manylinux2014)
# RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

RUN pip install --platform manylinux2014_x86_64 \
    --implementation cp \
    --python-version 3.13 \
    --only-binary=:all: \
    --target python \
    -r requirements.txt

# Copia el resto de la app
COPY . .

# Incluye todos los archivos en la carpeta python
RUN cp -r main.py controllers models routes schemas services python/

# Crea el ZIP final
WORKDIR /app/python
RUN zip -r9 /app/lambda_function.zip .

