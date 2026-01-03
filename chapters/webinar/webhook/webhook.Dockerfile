ARG PYTHON_VER=3.10

FROM tiangolo/uvicorn-gunicorn-fastapi:python${PYTHON_VER}-slim as webhook

RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y git && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel

WORKDIR /app

# set env variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./webhook/pyproject.toml /app/

RUN pip --no-cache-dir install .

# Do not break dependency caching before installing project
COPY ./webhook/app/ /app/

WORKDIR /
