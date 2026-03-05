"""
API Model - Hello World con FastAPI
"""

from fastapi import FastAPI

app = FastAPI(
    title="API Model",
    version="1.0.0",
    description="Hello World con FastAPI",
)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/health")
async def health():
    return {"status": "ok"}
