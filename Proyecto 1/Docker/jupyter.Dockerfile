FROM jupyter/scipy-notebook:latest

USER root
RUN curl -o /usr/local/bin/mc https://dl.min.io/client/mc/release/linux-amd64/mc \
    && chmod +x /usr/local/bin/mc

USER jovyan
RUN pip install --no-cache-dir minio>=7.0.0 pymysql "scikit-learn>=1.3.0,<1.4.0"
