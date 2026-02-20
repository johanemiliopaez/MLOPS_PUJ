# Dockerfile para JupyterLab - Desarrollo y entrenamiento de modelos
FROM python:3.12-slim-bookworm

# Instalar UV
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace/commons

# Instalar dependencias requeridas por Setup/API/main.py y Setup/Model/train.py usando UV
COPY Setup/pyproject.toml /tmp/pyproject.toml
RUN uv pip install --system -r /tmp/pyproject.toml

# Instalar herramientas de notebook en JupyterLab
RUN uv pip install --system \
    jupyterlab \
    ipywidgets \
    matplotlib

# Puerto JupyterLab
EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--ServerApp.token=", "--ServerApp.password="]
