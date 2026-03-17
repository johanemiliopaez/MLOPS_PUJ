# Proyecto 1 End-to-End MLOps Pipeline

Este proyecto implementa una arquitectura completa de Machine Learning Operations (MLOps) utilizando contenedores Docker. Se configura  un entorno   donde la ingesta de datos está aislada en su propia red y un orquestador ETL extrae, procesa y sirve los datos a un entorno de experimentación.

## Arquitectura del Sistema

El proyecto está compuesto por 6 bloques principales distribuidos en dos redes Docker aisladas (`data_network` y `ml_network`):

1. **API de Datos (Fuente Externa):** Simula un proveedor de datos externo. Entrega lotes (batches) de información cada 5 minutos. Vive aislada en la `data_network`.
2. **Apache Airflow (ETL Pipeline):** Actúa como el puente autorizado entre ambas redes. Extrae los datos crudos, los limpia, imputa nulos, codifica variables categóricas (manteniendo el contexto histórico) y divide el dataset en Train/Test.
3. **MySQL (Almacén Relacional):** Guarda las tablas intermedias (`tabla_raw`, `tabla_clean`) y las tablas finales listas para entrenamiento (`tabla_train`, `tabla_test`).
4. **MinIO (Object Storage):** Repositorio para los modelos serializados (`.pkl`) entrenados.
5. **JupyterLab (Entorno de Experimentación):** Opera conectado directamente a MySQL y MinIO. Es utilizado para entrenar modelos sin requerir tareas de limpieza de datos en esta etapa.
6. **FastAPI (API de Inferencia en Producción):** Descarga el modelo   desde MinIO. Traduce los datos crudos del usuario a formato matemático y expone un endpoint REST resiliente para predicciones en tiempo real.

## Estructura del Proyecto

proyecto_mlops/
├── docker-compose.yml
├── data_api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py
│   └── data/
│       └── covertype.csv
├── airflow/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── dags/
│       └── pipeline_datos.py
├── jupyter/
│   └── Dockerfile
└── inference_api/
    ├── Dockerfile
    ├── requirements.txt
    └── main.py

# Detalle del Bloque de Inferencia (FastAPI)

El bloque de inferencia está diseñado para operar en condiciones del mundo real, donde el sistema cliente envía datos en su formato original (textos y números mezclados) y, en ocasiones, envía categorías que el modelo nunca procesó durante su entrenamiento (Out-of-Vocabulary).
Funcionamiento Interno

    Doble Carga en Frío: Al iniciar (lifespan), la API se conecta a MinIO y descarga dos artefactos: el modelo predictivo (modelo_rf.pkl) y el diccionario de memoria de Airflow (mapeo_variables.pkl).

    Traducción al Vuelo: Cuando llega una petición, la API revisa las 12 características. Si detecta texto (ej. "Rawah"), consulta el diccionario de MinIO y lo traduce a su código numérico correspondiente (ej. 0), ensamblando un pd.DataFrame estructurado idéntico al utilizado en el entrenamiento.

    Resiliencia ante Datos Desconocidos: Si el usuario envía un dato categórico nuevo (ej. "C7744") que no existe en la memoria de MinIO, la API no interrumpe el proceso ni rechaza la petición. Asigna un valor numérico genérico (-1) para que el modelo matemático pueda procesarlo, y añade una advertencia al payload de respuesta.

# Qué espera recibir el sistema (Input)

Un objeto JSON con la clave features, que contiene una lista de exactamente 12 elementos (puede ser una mezcla de enteros, flotantes y strings).
JSON

{
  "features": [
    "2596", "51", "3", "258", "0", "510", "221", "232", "148", "6279", 
    "Rawah", "C7744"
  ]
}

# Qué entrega el sistema (Output)

La API responde con un HTTP 200 y un JSON que contiene la predicción final (cover_type_prediccion como número entero). Si el sistema detecta valores fuera de vocabulario, incluye un arreglo opcional llamado advertencias.
JSON

{
  "cover_type_prediccion": 1,
  "advertencias": [
    "Valor 'C7744' no reconocido en la columna 'Soil_Type'. Se asignó el valor genérico (-1)."
  ]
}


# Guía de Ejecución y Pruebas (Paso a Paso)
## 1. Despliegue de la Infraestructura

El usuario debe ubicarse en la raíz del proyecto y ejecutar:
Bash

docker compose up -d --build
<p align="center">
<img width="1491" height="628" alt="image" src="https://github.com/user-attachments/assets/d1bbe24c-3bd7-43a8-a787-67acf8548d18" />
 </p>

## 2. Probar la Extracción (API de Datos)

    El usuario ingresa a: http://localhost:8080/docs

    Ejecuta el endpoint GET /data (parámetro group_number=1).
    <p align="center">
    <img width="631" height="569" alt="image" src="https://github.com/user-attachments/assets/b39ec1d1-ed01-4bc5-bb53-b64f3b960a7f" />
    </p>

## 3. Ejecutar el Pipeline ETL (Airflow)

    El usuario ingresa a: http://localhost:8081 (Credenciales: admin / admin).

    Enciende el DAG etl_ml_pipeline y presiona Trigger DAG (botón de "Play").

    Verificación: En MinIO (http://localhost:9001) el usuario visualiza el bucket artefactos con el archivo mapeo_variables.pkl.
<p align="center">
<img width="1691" height="709" alt="image" src="https://github.com/user-attachments/assets/0acd0af8-4307-48d5-bada-8213117b6551" />
</p>
## 4. Entrenar el Modelo (JupyterLab)

    Ingresa a: http://localhost:8888 (Token: `jupyter` o el valor de `JUPYTER_TOKEN`).

    Abre `Prueba.ipynb` y ejecuta todas las celdas. Se conecta a MySQL y MinIO usando las variables de entorno configuradas.
<p align="center">
<img width="1684" height="698" alt="image" src="https://github.com/user-attachments/assets/c3da2ffc-2b7b-489f-88ab-dd0747ef9d5a" />
</p>
    

## 5. Consumir el Modelo en Producción (API de Inferencia)

    El usuario ingresa a: http://localhost:8000/docs

    Ejecuta POST /reload para descargar el modelo y el mapeo.

    Ejecuta POST /predict enviando un payload de prueba.
<p align="center">
<img width="1167" height="393" alt="image" src="https://github.com/user-attachments/assets/da7f1cef-a894-495e-b135-5e93a9d519a0" />

<img width="648" height="446" alt="image" src="https://github.com/user-attachments/assets/e268c956-d445-447b-acbc-d8464be368b8" />
</p>


    

# Retos Encontrados y Soluciones Implementadas
1. Concurrencia en Base de Datos de Airflow

    Problema: El contenedor de Airflow entraba en estado exited (cannot use SQLite with the LocalExecutor).

    Solución: El proyecto modificó la variable a AIRFLOW__CORE__EXECUTOR=SequentialExecutor para permitir una ejecución lineal y estable de las tareas del DAG sin bloquear la base de datos interna.

2. Dependency Hell (Incompatibilidad de Versiones)

    Problema: La API de inferencia arrojaba AttributeError: 'DecisionTreeClassifier' object has no attribute 'monotonic_cst'.

    Solución: El sistema implementó "Dependency Pinning". Fijó estrictamente scikit-learn==1.3.1 y pandas==2.2.0 tanto en el Dockerfile de Jupyter como en el requirements.txt de la API de inferencia para garantizar que el modelo serializado fuera compatible al 100%.

3. Pérdida de Formato de Datos al Servir el Modelo

    Problema: Scikit-Learn rechazaba las peticiones en inferencia por falta de nombres de columnas.

    Solución: El desarrollador actualizó el endpoint /predict para que reconstruyera un pd.DataFrame al vuelo con las cabeceras originales (COLUMNAS_MODELO) antes de pasarlo al predictor.

4. Categorías "Out of Vocabulary" (Textos no vistos)

    Problema: Si el usuario enviaba un dato categórico (ej. ciudad o suelo) que no llegó en los lotes de extracción durante el entrenamiento, la API se interrumpía con un Error HTTP 500.

    Solución: El sistema integró la lógica de asignación a -1 documentada en la sección de "Funcionamiento Interno", garantizando una predicción "best-effort" ininterrumpida y visibilidad completa a través de advertencias en el JSON de respuesta
