from fastapi import FastAPI

from .model_service import MODEL_PATH, predict_price
from .schemas import ApartmentRequest, PredictionResponse


app = FastAPI(
    title="Astana Apartment Price API",
    description="API for apartment price prediction. Telegram bot can call /predict.",
    version="1.0.0",
)


@app.get("/")
def root():
    return {
        "service": "Astana Apartment Price API",
        "status": "ok",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_exists": MODEL_PATH.exists(),
        "model_path": str(MODEL_PATH),
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: ApartmentRequest):
    predicted_price = predict_price(payload)
    return PredictionResponse(
        predicted_price=predicted_price,
        predicted_price_rounded=round(predicted_price),
    )
