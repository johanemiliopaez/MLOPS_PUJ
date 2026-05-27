FROM apache/airflow:2.9.1

# Copiamos el archivo de requerimientos al contenedor
COPY requirements.txt /requirements.txt

# Volvemos al usuario airflow para instalar paquetes de Python de forma segura
USER airflow
RUN pip install --no-cache-dir -r /requirements.txt