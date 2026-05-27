FROM python:3.10-slim

WORKDIR /app

#LALALALALAL
# Copiar dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la API
COPY main.py .

# Exponer el puerto
EXPOSE 8000

# Comando para ejecutar Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
