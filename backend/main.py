import logging

from fastapi import FastAPI
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from .model_service import MODEL_PATH, ModelLoadError, ModelPredictionError, load_model, predict_price
from .schemas import ApartmentRequest, PredictionResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
    model_loaded = False
    model_error = None
    try:
        load_model()
        model_loaded = True
    except ModelLoadError as exc:
        model_error = str(exc)

    return {
        "status": "ok",
        "model_exists": MODEL_PATH.exists(),
        "model_loaded": model_loaded,
        "model_path": str(MODEL_PATH),
        "model_error": model_error,
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(payload: ApartmentRequest):
    logger.info("Incoming /predict payload: %s", payload.model_dump())
    try:
        predicted_price = predict_price(payload)
    except ModelLoadError as exc:
        logger.exception("Prediction model is unavailable")
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_unavailable",
                "message": "Не удалось загрузить модель прогнозирования.",
            },
        ) from exc
    except ModelPredictionError as exc:
        logger.exception("Prediction failed")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "prediction_failed",
                "message": "Не удалось получить прогноз. Попробуйте позже.",
            },
        ) from exc

    logger.info("Outgoing /predict response predicted_price=%s", predicted_price)
    return PredictionResponse(
        predicted_price=predicted_price,
        predicted_price_rounded=round(predicted_price),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Invalid request to %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(exc.errors()),
            "message": "Проверьте введённые данные и попробуйте снова.",
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled FastAPI error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Не удалось получить прогноз. Попробуйте позже."},
    )
