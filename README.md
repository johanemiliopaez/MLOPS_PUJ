# MLOPS_PUJ

Repositorio académico de MLOps que reúne los talleres prácticos de la materia MLOPS_PUJ

## Resumen del repositorio

- **Taller 1 - Penguins:** pipeline de entrenamiento en Python, generación de modelos (`RF.pkl` y `LR.pkl`), API REST con FastAPI y despliegue en Docker.
- **Taller 2 - Contenedores:** entorno con Docker Compose para ejecutar FastAPI + JupyterLab en paralelo, con volumen compartido para datos, código y artefactos.
- **Taller 3 - Airflow:** pipeline orquestado con Airflow (múltiples tareas), MySQL para capas `raw` y `procesada`, entrenamiento de modelos y servicio FastAPI conectado al volumen compartido de modelos.

## Estructura principal

```text
MLOPS_PUJ/
├── Taller 1 - Penguins/
├── Taller 2 - Contenedores/
├── Taller 3 - Airflow/
└── README.md
```

## Guía rápida

- Para flujo básico de entrenamiento + API: revisa `Taller 1 - Penguins/README.md`.
- Para entorno de desarrollo con JupyterLab + FastAPI: revisa `Taller 2 - Contenedores/README.md`.
- Para orquestación end-to-end con Airflow, MySQL y FastAPI: revisa `Taller 3 - Airflow/README.md`.


