# Taller 1
## Modelo Penguins Clasificación de especies - FastApi - Docker

Proyecto de **machine learning** para predecir la especie de pingüinos a partir de medidas morfológicas y contexto (isla, sexo, año). Incluye pipeline de entrenamiento, dos modelos (Random Forest y Regresión Logística), una **API REST** con FastAPI y una **imagen Docker** para desplegar el servicio.

---

## Tabla de contenidos

- [Descripción general](#descripción-general)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Dataset](#dataset)
- [Requisitos e instalación](#requisitos-e-instalación)
- [Pipeline de entrenamiento](#pipeline-de-entrenamiento)
- [Modelos generados](#modelos-generados)
- [API REST](#api-rest)
- [Docker](#docker)


---

## Descripción general

El flujo del proyecto es:

1. **Dataset** (`Dataset/penguins.csv`): datos de pingüinos con medidas y atributos.
2. **Entrenamiento** (`Model/train.py`): preparación de datos en 6 pasos, construcción y entrenamiento de dos clasificadores (RF y LR), validación y guardado de los pipelines como `RF.pkl` y `LR.pkl`.
3. **API** (`API/main.py`): servicio FastAPI que carga ambos modelos y expone **POST /rf** y **POST /lr** para predecir la especie.
4. **Docker** (`Docker/`): Dockerfile para construir una imagen que ejecuta la API en el puerto **8989**.

**Especies objetivo:** Adelie, Chinstrap, Gentoo.

---

## Estructura del proyecto

```
penguins/
├── README.md              # Este archivo
├── requirements.txt       # Dependencias Python
├── Dataset/
│   └── penguins.csv       # Dataset de entrenamiento
├── Model/
│   ├── train.py           # Script de entrenamiento (genera RF.pkl y LR.pkl)
│   ├── RF.pkl             # Pipeline Random Forest (generado)
│   └── LR.pkl             # Pipeline Regresión Logística (generado)
├── API/
│   └── main.py            # Aplicación FastAPI
└── Docker/
    ├── Dockerfile         # Imagen para ejecutar la API
    ├── .dockerignore


---

## Dataset

- **Ubicación:** `Dataset/penguins.csv`
- **Origen:** Palmer Penguins (medidas de pingüinos de Palmer Station, Antarctica).

| Columna            | Tipo   | Descripción                          |
|--------------------|--------|--------------------------------------|
| `species`          | texto  | **Target.** Adelie, Chinstrap o Gentoo |
| `island`           | texto  | Isla: Torgersen, Biscoe o Dream      |
| `bill_length_mm`   | float  | Longitud del pico (mm)               |
| `bill_depth_mm`    | float  | Profundidad del pico (mm)            |
| `flipper_length_mm`| float  | Longitud de la aleta (mm)            |
| `body_mass_g`      | float  | Masa corporal (g)                    |
| `sex`              | texto  | male o female                        |
| `year`             | int    | Año (ej. 2007)                       |

El CSV puede contener valores faltantes (`NA`); el pipeline de entrenamiento los elimina antes de entrenar.

---

## Requisitos e instalación

- **Python:** 3.9 o superior (recomendado 3.11).
- **Dependencias:**

```bash
pip install -r requirements.txt
```

Contenido de `requirements.txt`:

- `pandas` — manipulación de datos
- `numpy` — operaciones numéricas
- `scikit-learn` — modelos y preprocesado
- `joblib` — serialización de modelos
- `fastapi` — API REST
- `uvicorn[standard]` — servidor ASGI

---

## Pipeline de entrenamiento

El script `Model/train.py` ejecuta un pipeline en dos bloques: **preparación de datos** (6 pasos) y **creación de modelos** (3 pasos por modelo).

### 1. Preparación de datos (6 pasos)

| Paso | Nombre                  | Descripción |
|------|-------------------------|-------------|
| 1    | **Carga**               | Lectura de `Dataset/penguins.csv`. |
| 2    | **Limpieza**            | Reemplazo de `"NA"` por nulos y eliminación de filas con valores faltantes. |
| 3    | **Transformación**      | Conversión de columnas numéricas a tipo numérico y eliminación de filas que queden con nulos. |
| 4    | **Validación**          | Comprobación de que no hay nulos en `species`, que hay al menos 2 clases y que queda un volumen de datos válido. |
| 5    | **Ingeniería de características** | Definición de **X** (todas las columnas salvo `species`) y **y** (`species`). Preprocesado: escalado (StandardScaler) para variables numéricas y OneHotEncoder para categóricas (`island`, `sex`). |
| 6    | **División**            | División 80% train / 20% test con `train_test_split`, estratificada por `species`, `random_state=42`. |

<p align="center">
  <img src="https://github.com/user-attachments/assets/f7c338c6-6438-404c-b9e5-78d11538125a" width="100%" alt="imagen" />
</p>

### 2. Creación de modelos (3 pasos por modelo)

Para **Random Forest (RF)** y **Regresión Logística (LR)**:

| Paso | Nombre            | Descripción |
|------|-------------------|-------------|
| 1    | **Construcción**  | Definición del estimador: `RandomForestClassifier(n_estimators=100)` o `LogisticRegression(max_iter=1000)`. |
| 2    | **Entrenamiento** | Pipeline: preprocesador (ColumnTransformer) + clasificador; se ajusta con `X_train`, `y_train`. |
| 3    | **Validación**    | Predicción sobre `X_test`, cálculo de accuracy, classification report y matriz de confusión. |

Al final se guardan los pipelines completos (preprocesador + modelo) con `joblib` en:

- `Model/RF.pkl`
- `Model/LR.pkl`

### Ejecutar el entrenamiento

Desde la **raíz del proyecto**:

```bash
python Model/train.py
```

Tras ejecutar, en `Model/` deben aparecer `RF.pkl` y `LR.pkl`; la API los utiliza para servir las predicciones.

---

## Modelos generados

- **RF.pkl:** pipeline de Random Forest (preprocesador + `RandomForestClassifier`). Archivo serializado con `joblib` (extensión `.pkl`).
- **LR.pkl:** pipeline de Regresión Logística (preprocesador + `LogisticRegression`), mismo formato.

Ambos reciben las mismas **features** en el mismo orden que en entrenamiento: `island`, `bill_length_mm`, `bill_depth_mm`, `flipper_length_mm`, `body_mass_g`, `sex`, `year`. La salida es la **especie** predicha: Adelie, Chinstrap o Gentoo.

<p align="center">
  <img src="https://github.com/user-attachments/assets/fa24b972-41df-45ce-abfd-e4f49b9bf5bb" width="80%" alt="imagen" />
</p>
---

## API REST

La API está implementada en **FastAPI** en `API/main.py`. Al arrancar, carga `Model/RF.pkl` y `Model/LR.pkl` y expone dos endpoints de predicción.

### Arranque en local

Desde la raíz del proyecto:

```bash
uvicorn API.main:app --host 127.0.0.1 --port 8000
```


- **Documentación interactiva (Swagger):** http://127.0.0.1:8000/docs  
- **Raíz:** http://127.0.0.1:8000/
<p align="center">
  <img src="https://github.com/user-attachments/assets/725b5fe9-316d-44f8-8f7f-fbd4f02b7405" width="50%" alt="imagen" />
</p>
### Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET    | `/`  | Mensaje de bienvenida y enlaces a la API y a los endpoints. |
| POST   | `/rf`| Predicción usando el modelo **Random Forest** (RF.pkl). |
| POST   | `/lr`| Predicción usando el modelo **Regresión Logística** (LR.pkl). |

### Cuerpo de la petición (POST /rf y POST /lr)

JSON con las mismas variables que en el dataset (todas obligatorias):

```json
{
  "island": "Biscoe",
  "bill_length_mm": 39.1,
  "bill_depth_mm": 18.7,
  "flipper_length_mm": 181,
  "body_mass_g": 3750,
  "sex": "male",
  "year": 2007
}
```

Restricciones útiles:

- `island`: uno de `"Torgersen"`, `"Biscoe"`, `"Dream"`.
- `sex`: `"male"` o `"female"`.
- `year`: entero (ej. 2007, 2008, 2009).

### Respuesta

Ejemplo para **POST /rf** o **POST /lr**:

```json
{
  "model": "RF",
  "species": "Adelie"
}
```

O con LR:

```json
{
  "model": "LR",
  "species": "Adelie"
}
```

<p align="center">
  <img src="https://github.com/user-attachments/assets/d91ccd8e-bb6e-432a-8cb8-63ded279841c" width="50%" alt="imagen" />
</p>

En caso de error (datos inválidos o modelo no cargado), la API devuelve códigos 422 o 503 con un mensaje en el cuerpo.

---

## Docker

En `Docker/` se encuentra todo lo necesario para construir una **imagen** que ejecuta la API y exponerla en el puerto **8989**.

### Construcción de la imagen

Desde la **raíz del proyecto** (el contexto de build es el directorio raíz):

```bash
docker build -f Docker/Dockerfile -t penguins-api .
```

La imagen incluye:

- Python 3.11-slim
- Dependencias de `requirements.txt`
- Código de `API/`
- Modelos `Model/RF.pkl` y `Model/LR.pkl`

### Ejecución del contenedor

```bash
docker run -p 8989:8989 penguins-api
```

- La API queda disponible en **http://localhost:8989**.
- Documentación: **http://localhost:8989/docs**.
- Endpoints de predicción: **POST http://localhost:8989/rf** y **POST http://localhost:8989/lr**.

El puerto **8989** está declarado en el Dockerfile (`EXPOSE 8989`) y es el puerto por defecto del proceso dentro del contenedor.

<p align="center">
  <img src="https://github.com/user-attachments/assets/e31c3cb4-ac39-4ab4-a4e5-9d3e4731695c" width="80%" alt="imagen" />
</p>
<p align="center">
  <img src="https://github.com/user-attachments/assets/edf2c3e8-fff0-41cd-9b8a-e367e39799ba" width="80%" alt="imagen" />
</p>
---
