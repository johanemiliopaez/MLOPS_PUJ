# Usamos una versión estable oficial de Airflow
FROM apache/airflow:2.9.1

# Copiamos el archivo de requerimientos al contenedor
COPY requirements.txt /requirements.txt
COPY ./dags/ /opt/airflow/dags/
COPY ./data/ /opt/airflow/data/
# Cambiamos al usuario root temporalmente si requerimos dependencias del sistema (opcional)
# USER root
# RUN apt-get update && apt-get install -y libgomp1

# Volvemos al usuario airflow para instalar paquetes de Python de forma segura
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt
