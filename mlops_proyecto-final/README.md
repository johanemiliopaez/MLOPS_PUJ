# 🚀 MLOps Real Estate Pricing Pipeline en Kubernetes

[![Kubernetes](https://img.shields.io/badge/kubernetes-%23326ce5.svg?style=for-the-badge&logo=kubernetes&logoColor=white)](#)
[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-017CEE?style=for-the-badge&logo=Apache%20Airflow&logoColor=white)](#)
[![MLflow](https://img.shields.io/badge/mlflow-%23d9ead3.svg?style=for-the-badge&logo=numpy&logoColor=blue)](#)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](#)

Este repositorio contiene la infraestructura como código (IaC) y la configuración declarativa para un ecosistema **MLOps completo (End-to-End)** desplegado sobre un clúster local de Kubernetes. 

El proyecto automatiza la extracción de datos, limpieza, entrenamiento, evaluación, registro, despliegue y monitoreo de un modelo de Machine Learning (`RealEstate_Pricing_Model`), asegurando un entorno inmutable y determinista.

---

## 🏗️ Arquitectura del Sistema

El ecosistema está compuesto por 8 microservicios interconectados mediante el DNS interno de Kubernetes:

* **Orquestación:** Apache Airflow (Scheduler & Webserver) ejecutando el DAG `real_estate_mlops_pipeline`.
* **Almacenamiento de Metadatos y Aplicación:** PostgreSQL (Bases de datos `airflow_db` y `mlops_db`).
* **Almacenamiento de Artefactos (S3):** MinIO.
* **Model Registry & Tracking:** MLflow.
* **Inferencia (Serving):** FastAPI.
* **Ingesta de Datos:** Data API académica.
* **Interfaz Gráfica (Frontend):** Streamlit.
* **Observabilidad y Pruebas:** Prometheus, Grafana y Locust.

---

## 🛠️ Requisitos Previos

* **Entorno:** Ubuntu / Linux (o WSL2 en Windows).
* **Motor de Contenedores:** Docker Desktop o el demonio nativo de Docker limpio (sin contenedores "zombies" ocupando puertos).
* **Kubernetes:** Minikube o el clúster integrado de Docker Desktop activo.
* **Herramientas CLI:** `kubectl` instalado y configurado.

---

## 🚀 Guía de Despliegue (Zero-Touch Deployment)

La infraestructura está diseñada para levantarse desde cero (`from scratch`) y auto-configurarse, incluyendo la creación dinámica de tablas SQL (`raw_data`, `clean_data`, `pipeline_history`) mediante scripts de inicialización.

### 1. Limpieza del Entorno (Opcional pero recomendado)
Si tienes despliegues anteriores, asegúrate de limpiar los puertos y liberar los volúmenes persistentes para un inicio inmaculado:
```bash
sudo killall kubectl
docker stop $(docker ps -q)
kubectl delete -f k8s/
kubectl delete pvc --all
```

### 2. Despliegue Secuencial
Ejecuta los manifiestos con **Kustomize** (aplica los mapeos de imágenes hacia `innovacion/*`). Es **crítico** respetar la pausa de 15 segundos para que PostgreSQL ejecute el `init.sql` antes de que Airflow intente conectarse.

```bash
# 1. Configuración, Infraestructura, Orquestación y Observabilidad
kubectl apply -k k8s/

# 2. Dar tiempo al provisionamiento del esquema SQL
sleep 15
```

Verifica que todos los Pods estén en estado `1/1 Running`:
```bash
kubectl get pods -w
```

---

## 🔄 CI/CD y GitOps

Este repositorio incluye un workflow de GitHub Actions para construir y publicar imágenes en DockerHub
(`.github/workflows/docker-images.yml`). Configura los siguientes secrets en GitHub:

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

Para GitOps, se incluye un manifiesto de Argo CD en `argocd/application.yaml` con soporte explícito de
Kustomize. Aplícalo en el namespace `argocd` y Argo CD sincronizará la carpeta `k8s/` automáticamente
con el clúster.

---

## 🌐 Acceso a los Servicios (Port-Forwarding)

Una vez que todos los Pods estén operativos, ejecuta este bloque en tu terminal para abrir los túneles de comunicación hacia tu máquina local:

```bash
kubectl port-forward svc/airflow-webserver 8080:8080 --address 0.0.0.0 &
kubectl port-forward svc/mlflow 5000:5000 --address 0.0.0.0 &
kubectl port-forward svc/streamlit 8501:8501 --address 0.0.0.0 &
kubectl port-forward svc/fastapi 8000:8000 --address 0.0.0.0 &
kubectl port-forward svc/data-api 8001:80 --address 0.0.0.0 &
kubectl port-forward svc/grafana 3000:3000 --address 0.0.0.0 &
kubectl port-forward svc/locust 8089:8089 --address 0.0.0.0 &
kubectl port-forward svc/minio 9001:9001 --address 0.0.0.0 &
```

### URLs y Credenciales
*Usa `127.0.0.1` en lugar de `localhost` para evitar problemas de resolución IPv6 en navegadores modernos.*

| Servicio | URL Local | Usuario | Contraseña |
| :--- | :--- | :--- | :--- |
| **Apache Airflow** | http://127.0.0.1:8080 | `admin` | `admin` |
| **MLflow** | http://127.0.0.1:5000 | - | - |
| **MinIO Console** | http://127.0.0.1:9001 | `minio_admin` | `minio_password` |
| **FastAPI Swagger**| http://127.0.0.1:8000/docs | - | - |
| **Data API Docs** | http://127.0.0.1:8001/docs | - | - |
| **Streamlit UI** | http://127.0.0.1:8501 | - | - |
| **Grafana** | http://127.0.0.1:3000 | `admin` | `admin` |
| **Locust** | http://127.0.0.1:8089 | - | - |

---

## 📊 Monitoreo y Pruebas de Carga

Para validar la resiliencia de la API de inferencia:
1. Accede a **Locust** e inicia un enjambre (ej. 50 usuarios).
2. Ingresa a **Grafana** y configura `http://prometheus:9090` como tu Data Source de Prometheus.
3. Importa o crea paneles con las siguientes consultas (PromQL):
   * **Tráfico (RPS):** `sum(rate(http_requests_total[1m]))`
   * **Latencia Promedio:** `sum(rate(http_request_duration_seconds_sum[1m])) / sum(rate(http_request_duration_seconds_count[1m]))`

---
*Desarrollado por Jesus Alberto Puenayan Quiceno como parte de investigación y arquitectura de soluciones TI.*