from fastapi import FastAPI

from app.api import router

app = FastAPI(title="construction-ai API", version="0.1.0")
app.include_router(router, prefix="/api")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
