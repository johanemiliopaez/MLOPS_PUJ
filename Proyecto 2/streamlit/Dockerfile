FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY streamlit/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

COPY streamlit/app.py /app/app.py

CMD ["streamlit", "run", "/app/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
