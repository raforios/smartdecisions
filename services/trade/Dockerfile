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

