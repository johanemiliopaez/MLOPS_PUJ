# MLOPS_PUJ

Repositorio académico de MLOps que reúne dos talleres prácticos enfocados en el ciclo completo de un modelo de machine learning: entrenamiento, empaquetado y despliegue de una API de inferencia para clasificación de especies de pingüinos.

## Resumen del repositorio

- **Taller 1 - Penguins:** pipeline de entrenamiento en Python, generación de modelos (`RF.pkl` y `LR.pkl`), API REST con FastAPI y despliegue en Docker.
- **Taller 2 - Contenedores:** entorno con Docker Compose para ejecutar FastAPI + JupyterLab en paralelo, con volumen compartido para datos, código y artefactos.
- **Caso de uso común:** predicción de especie (`Adelie`, `Chinstrap`, `Gentoo`) a partir de variables morfológicas y de contexto del dataset Palmer Penguins.

## Estructura principal

```text
MLOPS_PUJ/
├── Taller 1 - Penguins/
│   ├── API/
│   ├── Dataset/
│   ├── Docker/
│   ├── Model/
│   └── README.md
├── Taller 2 - Contenedores/
│   ├── Docker/
│   ├── Setup/
│   ├── docker-compose.yml
│   └── README.md
└── README.md
```
