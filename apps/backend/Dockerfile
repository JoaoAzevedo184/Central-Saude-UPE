FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # /app é do root; o usuário da aplicação não escreve caches ali.
    PYTEST_ADDOPTS="-p no:cacheprovider" \
    RUFF_CACHE_DIR=/tmp/ruff

# true = inclui o grupo dev (pytest, ruff), para rodar os testes dentro do container.
ARG INSTALL_DEV=true

RUN useradd --create-home --uid 10001 app

WORKDIR /app

# Dependências antes do código, para aproveitar o cache das camadas.
COPY pyproject.toml ./
RUN python -c "import os, tomllib; d = tomllib.load(open('pyproject.toml', 'rb')); deps = d['project']['dependencies'] + (d['dependency-groups']['dev'] if os.environ['INSTALL_DEV'] == 'true' else []); print('\n'.join(deps))" > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app
COPY tests ./tests

USER app

EXPOSE 8000

CMD ["uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
