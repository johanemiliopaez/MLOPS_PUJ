FROM apache/airflow:2.9.1

# La ruta ahora especifica la subcarpeta desde la raíz
COPY ./airflow_image/requirements.txt /requirements.txt

USER airflow
RUN pip install --no-cache-dir -r /requirements.txt

# Ahora sí puede ver la carpeta dags que está en la raíz
COPY --chown=airflow:root ./dags /opt/airflow/dags