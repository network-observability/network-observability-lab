ARG PYTHON_VER=3.10

FROM tiangolo/uvicorn-gunicorn-fastapi:python${PYTHON_VER}-slim as machine-learning

RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y git && \
    apt-get autoremove -y && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* && \
    pip --no-cache-dir install --upgrade pip wheel && \
    pip install poetry

WORKDIR /app

# set env variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY ./machine-learning/pyproject.toml ./machine-learning/poetry.lock /app/

RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi

# Do not break dependency caching before installing project
COPY ./machine-learning/app/ /app/

WORKDIR /
