FROM jupyter/datascience-notebook:latest

USER jovyan

RUN pip install --no-cache-dir \
    mlflow==2.17.0 \
    psycopg2-binary \
    sqlalchemy \
    scikit-learn==1.3.2 \
    pandas \
    boto3
