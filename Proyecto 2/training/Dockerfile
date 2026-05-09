FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /opt/project

RUN apt-get update && apt-get install -y build-essential gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY training/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY training/src /opt/project/training/src

CMD ["python", "/opt/project/training/src/pipeline.py"]
