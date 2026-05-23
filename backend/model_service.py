from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from .schemas import ApartmentRequest


BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_PATH = BASE_DIR / "randomforest_log_target.pkl"
FEATURE_COLUMNS = [
    "rooms",
    "area",
    "living_area",
    "kitchen_area",
    "floor",
    "total_floors",
    "house_type",
    "year_built",
    "ceiling_height",
    "condition",
    "bathroom",
    "floor_type",
    "district",
    "latitude",
    "longitude",
    "building_age",
    "floor_ratio",
    "is_first_floor",
    "is_last_floor",
    "has_balcony",
    "has_parking",
    "has_furniture",
    "has_security",
    "rooms_per_area",
    "kitchen_area_ratio",
    "living_area_ratio",
]


@lru_cache(maxsize=1)
def load_model() -> Any:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def _bool_to_int(value: bool | None) -> int | None:
    if value is None:
        return None
    return int(value)


def build_features(payload: ApartmentRequest) -> pd.DataFrame:
    data = payload.model_dump()

    area = data["area"]
    floor = data["floor"]
    total_floors = data["total_floors"]
    rooms = data["rooms"]
    year_built = data.get("year_built")
    kitchen_area = data.get("kitchen_area")
    living_area = data.get("living_area")

    data["building_age"] = 2026 - year_built if year_built else None
    data["floor_ratio"] = floor / total_floors if total_floors else None
    data["is_first_floor"] = int(floor == 1)
    data["is_last_floor"] = int(floor == total_floors)
    data["has_balcony"] = _bool_to_int(data.get("has_balcony"))
    data["has_parking"] = _bool_to_int(data.get("has_parking"))
    data["has_furniture"] = _bool_to_int(data.get("has_furniture"))
    data["has_security"] = _bool_to_int(data.get("has_security"))
    data["rooms_per_area"] = rooms / area if area else None
    data["kitchen_area_ratio"] = kitchen_area / area if kitchen_area and area else None
    data["living_area_ratio"] = living_area / area if living_area and area else None

    return pd.DataFrame([{column: data.get(column) for column in FEATURE_COLUMNS}])


def predict_price(payload: ApartmentRequest) -> float:
    model = load_model()
    features = build_features(payload)
    prediction = model.predict(features)[0]
    return float(prediction)
