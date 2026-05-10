FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y build-essential gcc libpq-dev && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /opt/airflow/data /opt/airflow/project /opt/project/data \
 && chown -R airflow:0 /opt/airflow/data /opt/airflow/project /opt/project
USER airflow

COPY airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY airflow/dags /opt/airflow/dags
COPY training/src /opt/airflow/project/training/src
