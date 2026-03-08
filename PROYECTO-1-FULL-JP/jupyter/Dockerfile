FROM jupyter/datascience-notebook:latest
USER root
RUN apt-get update && apt-get install -y default-libmysqlclient-dev pkg-config gcc
USER jovyan
COPY Prueba.py Prueba.ipynb /home/jovyan/
RUN pip install --no-cache-dir \
    minio \
    pandas==2.2.0 \
    scikit-learn==1.3.1 \
    sqlalchemy \
    pymysql