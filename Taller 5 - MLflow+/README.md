# Taller 5 - Pipeline MLOps: MLflow, FastAPI y Load Testing (Locust)

Pipeline MLOps completo para el dataset de Penguins. Incluye infraestructura orquestada para: PostgreSQL (bases de datos independientes para metadata y negocio), MinIO (artifacts), JupyterLab (entrenamiento) y una API de inferencia (FastAPI) que consume el modelo directamente desde MLflow Model Registry. Además, incluye pruebas de estrés con Locust.

## Arquitectura

```text
PostgreSQL 
 ├─ mlflow_db ←──────────────────→ MLflow (tracking + registry)
 └─ data_db   ←─ JupyterLab ─→          ↓
                     ↓             MinIO (artifacts)
                     ↓                  ↓
              API Inferencia ←──────────┘
      (obtiene modelo desde MLflow)
```

## 1. Despliegue de la Infraestructura Base (Producción)

Para levantar la infraestructura principal (Bases de datos, Jupyter, MinIO, MLflow y la API de producción), ejecuta el archivo unificado:

```bash
docker compose -f docker-compose-prod.yaml up -d --build
```

### Servicios Disponibles

| Servicio | URL | Credenciales / Info |
|----------|-----|---------------------|
| JupyterLab | http://localhost:8888 | token: `jupyter` |
| MLflow UI | http://localhost:5002 | — |
| MinIO Console | http://localhost:9001 | `admin` / `admin1234` |
| API Inferencia | http://localhost:8001 | Swagger en `/docs` |

## 2. Entrenamiento y Registro de Modelos

Para el propósito de las pruebas de este taller, nos enfocaremos en el modelo base **PenguinsRF** (Random Forest):

1. Ingresa a **JupyterLab** (http://localhost:8888).
2. Ejecuta todas las celdas del notebook `entrenamiento_mlflow.ipynb`.
3. Esto procesará los datos en la base de datos, entrenará el modelo RandomForest con múltiples variaciones de hiperparámetros y promoverá el mejor modelo al estado **Production** en MLflow bajo el nombre `PenguinsRF`.

## 3. Uso de la API de Inferencia

La API consume por defecto el modelo `PenguinsRF`. Puedes probarla enviando un payload al endpoint principal:

**POST /predict**
```bash
curl -X POST http://localhost:8001/predict \
  -H "Content-Type: application/json" \
  -d '{"features": [39.1, 18.7, 181, 3750, 0, 0, 2007]}'
```
*(Respuesta esperada: `{"species_prediccion": "Adelie"}`)*

---

## 4. Pruebas de Carga y Estrés (Locust)

Se configuró un entorno aislado mediante `docker-compose-loadtest.yaml` para someter la API a **10.000 usuarios recurrentes** (Spawn rate: 500) usando el endpoint por defecto (`/predict` con PenguinsRF).

Para monitorear el consumo de recursos de los contenedores en tiempo real durante las pruebas, se utilizó el siguiente comando en una terminal separada:
```bash
docker stats
```
Para verificar contenedores caídos y sus códigos de salida:
```bash
docker ps -a
```

### Bitácora de Desarrollo: Problemas Hallados y Resueltos

Durante la fase de experimentación y escalamiento, nos encontramos con los siguientes retos técnicos, los cuales fueron diagnosticados y solucionados:

**Problema 1: Colapso por Memoria (OOMKilled)**
* **Incidente:** Al iniciar las pruebas con recursos estrictamente limitados (0.5 CPU y 256MB de RAM), el contenedor de la API colapsaba abruptamente y la terminal arrojaba el estado `Exited (137)`.
* **Diagnóstico:** El código 137 indica que el sistema operativo "asesinó" el contenedor por falta de memoria RAM (OOMKilled) al intentar cargar `scikit-learn`, `pandas` y el modelo simultáneamente bajo alta concurrencia.
* **Solución:** Se editó el archivo `docker-compose-loadtest.yaml` para incrementar el límite de memoria a `512M`. Con este ajuste, la API logró estabilizarse utilizando aproximadamente ~425 MiB (83% de la memoria asignada).

**Problema 2: Cuello de botella de CPU (GIL de Python)**
* **Incidente:** Tras solucionar la memoria y subir la CPU a `1.0`, la API no se colgaba, pero su rendimiento no superaba las **~50 peticiones por segundo (RPS)**, a pesar de que la máquina anfitriona tenía recursos de sobra.
* **Diagnóstico:** El comando `docker stats` mostró el contenedor al 101.90% de CPU. Python sufre del *Global Interpreter Lock (GIL)*, lo que impide que un solo *worker* de FastAPI aproveche eficientemente múltiples núcleos para procesamiento matemático paralelo.
* **Solución:** Implementar escalamiento horizontal (múltiples réplicas) en lugar de escalamiento vertical.

**Problema 3: Conflicto de nombres al escalar**
* **Incidente:** Al intentar ejecutar `docker compose up --scale api-testing=3`, Docker arrojó un error indicando que los contenedores requerían nombres únicos.
* **Solución:** Se eliminó la etiqueta estática `container_name: api_penguins_test` dentro del archivo `docker-compose-loadtest.yaml`, permitiendo que Docker asigne dinámicamente nombres secuenciales (ej. `api-testing-1`, `api-testing-2`).

---

## 5. Conclusiones Finales (Análisis de Escalamiento)

*Archivos de referencia en la carpeta `Resultados/`: `Locust.pdf` y `Locust 3procesos.pdf`.*

* **Escenario Base (1 Instancia):** Como se observa en `Locust.pdf`, una sola instancia de la API alcanzó su límite físico en **~50 RPS**.
* **Escenario Escalado (3 Instancias):** Al ejecutar 3 réplicas detrás del balanceador nativo de Docker, el rendimiento registrado en `Locust 3procesos.pdf` se triplicó, superando las **150 RPS estables**.
* **Uso de Recursos:** El comando `docker stats` demostró que Docker distribuyó la carga equitativamente, llevando las 3 réplicas al ~100% de uso de su respectiva CPU y ~245MB de RAM cada una.
* **Respuesta del Sistema:** El sistema soportó con éxito los **10.000 usuarios concurrentes** solicitados. Gracias al balanceo de carga, la tasa de rechazo de peticiones (Failures) se mantuvo en **0%**, demostrando que el escalamiento horizontal es la arquitectura idónea para evadir las limitaciones del GIL en despliegues de Machine Learning con Python.