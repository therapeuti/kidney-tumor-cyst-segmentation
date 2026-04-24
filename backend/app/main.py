from fastapi import FastAPI

from backend.app.api.routes import router as api_router


app = FastAPI(title="Kidney Tumor Cyst Segmentation API")
app.include_router(api_router, prefix="/api")


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
