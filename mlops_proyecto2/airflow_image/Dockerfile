FROM apache/airflow:2.7.1
USER root
RUN apt-get update && apt-get install -y libpq-dev gcc
USER airflow
RUN pip install mlflow psycopg2-binary boto3 pandas scikit-learn
