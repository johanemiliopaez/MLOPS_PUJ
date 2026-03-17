# MLOPS_PUJ

Repositorio académico de MLOps que reúne los talleres prácticos de la materia MLOPS_PUJ


- **Taller 1 - Penguins:** pipeline de entrenamiento en Python, generación de modelos (`RF.pkl` y `LR.pkl`), API REST con FastAPI y despliegue en Docker.
- **Taller 2 - Contenedores:** entorno con Docker Compose para ejecutar FastAPI + JupyterLab en paralelo, con volumen compartido para datos, código y artefactos.
- **Taller 3 - Airflow:** pipeline orquestado con Airflow (múltiples tareas), MySQL para capas `raw` y `procesada`, entrenamiento de modelos y servicio FastAPI conectado al volumen compartido de modelos.
- **Proyecto 1 - MLOPS:** El proyecto consiste en implementar una arquitectura MLOps en una máquina virtual usando Docker Compose, integrando Airflow, MinIO y PostgreSQL.
Se deben consumir datos desde una API externa en intervalos de 5 minutos para alimentar el pipeline.
Con esos datos se entrenan modelos de IA, se almacenan y luego se exponen mediante una API en FastAPI para inferencia.
La evaluación se basa en el repositorio, el despliegue funcional, la orquestación con Airflow y el flujo completo de datos a inferencia.