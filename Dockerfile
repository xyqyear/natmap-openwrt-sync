ARG PYTHON_VERSION=3.11

FROM python:${PYTHON_VERSION}-alpine as poetry-base

ARG POETRY_VERSION=1.6.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apk add --no-cache \
        gcc \
        musl-dev \
        libffi-dev && \
    pip install --no-cache-dir poetry==${POETRY_VERSION} && \
    apk del \
        gcc \
        musl-dev \
        libffi-dev

FROM poetry-base as app-env

ENV POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_NO_INTERACTION=1

WORKDIR /app

COPY poetry.lock pyproject.toml /app/

RUN apk add --no-cache \
        gcc \
        musl-dev \
        libffi-dev && \
    poetry install --no-interaction --no-cache --no-root --without dev && \
    apk del \
        gcc \
        musl-dev \
        libffi-dev

FROM python:${PYTHON_VERSION}-alpine as app

ENV PATH="/app/.venv/bin:$PATH" \
    NATMAP_SYNCER_CONFIG_PATH="/data/config.yaml"

WORKDIR /app

COPY --from=app-env /app/.venv /app/.venv

COPY . /app

RUN mkdir -p /data

EXPOSE 80

CMD ["python3", "-m", "natmap_openwrt_sync"]