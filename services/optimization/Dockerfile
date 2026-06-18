# 1. Base image for x86_64 Lambda runtime.
FROM public.ecr.aws/lambda/python:3.14

USER root
RUN dnf update -y && dnf install -y \
    gcc gcc-c++ make zip tar gzip python3-devel openblas-devel \
    geos-devel proj-devel cargo rust \
    && dnf clean all

WORKDIR /build
COPY requirements.txt .

# 2. Install dependencies into a clean target directory.
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir --target /package -r requirements.txt

# 3. Copy source code on top of the dependencies.
COPY . /package/

# 4. Build the Lambda deployment ZIP excluding local-only artifacts.
WORKDIR /package
RUN zip -r9 /app/lambda_function.zip . \
        -x "Dockerfile" "build_and_deploy.sh" "deploy.config" \
           "*.venv*" "*venv*" "*__pycache__*" "tests/*"
