# Proyecto 2: Arquitectura Integral de MLOps en Kubernetes
**Institución:** Pontificia Universidad Javeriana
**Fecha:** Mayo de 2026

## 1. Descripción del Proyecto
Este proyecto tiene como objetivo diseñar, implementar y desplegar una arquitectura integral de MLOps sobre Kubernetes. El sistema cubre el ciclo completo de vida de un modelo de Machine Learning: ingesta de datos por lotes, almacenamiento de información cruda, procesamiento y limpieza, entrenamiento periódico, registro de experimentos, versionamiento de modelos, selección automática del mejor modelo, despliegue de inferencia mediante una API, consumo desde una interfaz gráfica, pruebas de carga y observabilidad del servicio. El caso de uso se basa en un conjunto de datos clínicos de pacientes con diabetes para la predicción de readmisión hospitalaria.

## 2. Arquitectura del Sistema
La arquitectura está desplegada completamente en un clúster local de Kubernetes bajo el namespace `mlops-diabetes`:

### Fase de Entrenamiento
* **Airflow:** Orquestador encargado del flujo de ingesta, procesamiento, entrenamiento y registro del modelo. Gestiona la carga incremental en lotes de hasta 15,000 registros.
* **PostgreSQL:** Almacenamiento relacional para datos crudos (RAW), procesados (CLEAN) y logs de inferencia.
* **MinIO:** Sistema de almacenamiento de objetos (S3 compatible) para los artefactos de MLflow.
* **MLflow:** Servidor para el seguimiento de experimentos y registro de modelos, configurado con backend de PostgreSQL y artifact store de MinIO.

### Fase de Inferencia y Observabilidad
* **FastAPI:** API de inferencia que carga dinámicamente el modelo productivo desde MLflow. Registra cada solicitud en la base de datos.
* **Streamlit:** Interfaz gráfica simple para enviar datos a la API y visualizar predicciones.
* **Locust:** Herramienta para ejecutar pruebas de carga sobre la API de inferencia.
* **Prometheus & Grafana:** Stack de observabilidad para monitorear métricas de hardware y de la aplicación en tiempo real.

## 3. Credenciales de Acceso
A continuación, se detallan los usuarios y contraseñas configurados para los distintos servicios del clúster:

| Servicio | Usuario | Contraseña |
| :--- | :--- | :--- |
| **Airflow (Web UI)** | `admin` | `admin` |
| **Grafana (Web UI)** | `admin` | `admin` |
| **PostgreSQL / MLflow DB** | `mlops_user` | `mlops_password` |
| **MinIO (Consola/S3)** | `minio_admin` | `minio_password` |

## 4. Instrucciones de Despliegue
Para desplegar la infraestructura de forma automatizada, ejecute los siguientes comandos en orden:

1.  **Preparar el Namespace:**
    ```bash
    kubectl create namespace mlops-diabetes
    ```
2.  **Configurar Secretos y ConfigMaps:**
    ```bash
    kubectl apply -f 01-setup.yaml
    ```
3.  **Desplegar Almacenamiento:**
    ```bash
    kubectl apply -f 02-storage.yaml
    ```
4.  **Desplegar Aplicaciones y Observabilidad:**
    ```bash
    kubectl apply -f 03-mlflow.yaml -f 04-apps.yaml -f 05-observability.yaml -f 06-airflow.yaml
    ```

## 5. Guía de Validación (End-to-End)
Dado que el ecosistema nace 100% interconectado, proceda directamente con la validación del flujo de datos:

1.  **Entrenamiento:** Acceda a Airflow (`http://localhost:8080`) y active el DAG para ejecutar el pipeline. Verifique el registro en MLflow (`http://localhost:5000`).
2.  **Inferencia:** Realice una predicción clínica de prueba en la interfaz de Streamlit (`http://localhost:8501`).
3.  **Carga:** Inicie una prueba de estrés en Locust (`http://localhost:8089`) simulando 50 usuarios recurrentes hacia `http://fastapi:8000`.
4.  **Monitoreo:** Acceda a Grafana (`http://localhost:3000`), importe su archivo JSON del Dashboard de MLOps y verifique en tiempo real cómo las gráficas responden al tráfico de Locust.

## 6. Limpieza y Apagado (Opcional)
Si desea eliminar los recursos o apagar el entorno de pruebas, puede utilizar los siguientes comandos:

* **Eliminar el proyecto completo:**
    ```bash
    kubectl delete namespace mlops-diabetes
    ```
    *Este comando aniquilará todos los pods, servicios, secretos y volúmenes de almacenamiento persistente asociados al proyecto.*

* **Apagar el clúster (si utiliza Minikube):**
    ```bash
    minikube stop
    ```

## 7. Dificultades y Soluciones Encontradas
* **Gestión de Credenciales en Airflow:** Se detectó que el arranque estándar generaba contraseñas aleatorias que impedían el acceso estable. **Solución:** Se implementó un comando de inicio blindado en el deployment que fuerza el reseteo de la contraseña a `admin` en cada arranque del Pod.
* **Esquema de Datos de Inferencia:** La API fallaba al insertar logs debido a la falta de columnas dinámicas requeridas por el modelo. **Solución:** Se automatizó la creación del esquema exacto mediante un script `init.sql` montado en la inicialización de PostgreSQL.
* **Bug de Aprovisionamiento en Grafana:** El motor de configuración ignoraba la base de datos por defecto si se inyectaba en la raíz del YAML. **Solución:** Se identificó que el atributo `database` debía ser inyectado estrictamente dentro del bloque `jsonData` del `ConfigMap`, garantizando una conexión 100% automatizada sin intervención manual.

## 8. Cumplimiento de la Rúbrica
* **Kubernetes (20%):** Despliegue completo con Deployments, Services, PVC y límites de recursos definidos.
* **Orquestación Airflow (20%):** DAG de ejecución con carga por lotes y entrenamiento reproducible.
* **MLflow (20%):** Arquitectura de tracking externa utilizando PostgreSQL como Backend y MinIO como Artifact Store.
* **API e Interfaz (15%):** Despliegue de FastAPI consumiendo modelos dinámicamente y registro transaccional de inferencias en DB.
* **Observabilidad y Carga (15%):** Integración nativa de Locust, recolección de métricas con Prometheus y Dashboard de Grafana provisionado como código.