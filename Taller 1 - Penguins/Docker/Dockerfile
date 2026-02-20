# Imagen base Python
FROM python:3.11-slim

# Directorio de trabajo en el contenedor
WORKDIR /app

# Copiar dependencias
COPY requirements.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar API y modelos (contexto de build = raíz del proyecto)
COPY API/ ./API/
COPY Model/RF.pkl Model/LR.pkl ./Model/

# Puerto donde se expone la API
EXPOSE 8989

# Arrancar la API con uvicorn en 0.0.0.0 para aceptar conexiones externas
CMD ["uvicorn", "API.main:app", "--host", "0.0.0.0", "--port", "8989"]