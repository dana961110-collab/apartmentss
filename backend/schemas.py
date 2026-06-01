from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ApartmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rooms: float = Field(..., gt=0, description="Number of rooms")
    area: float = Field(..., gt=0, description="Total apartment area in square meters")
    floor: float = Field(..., ge=1, description="Apartment floor")
    total_floors: float = Field(..., gt=0, description="Total floors in the building")

    living_area: Optional[float] = Field(None, ge=0)
    kitchen_area: Optional[float] = Field(None, ge=0)
    house_type: Optional[str] = None
    year_built: Optional[float] = Field(None, ge=1800)
    ceiling_height: Optional[float] = Field(None, gt=0)
    condition: Optional[str] = None
    bathroom: Optional[str] = None
    floor_type: Optional[str] = None
    district: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    has_balcony: Optional[bool] = None
    has_parking: Optional[bool] = None
    has_furniture: Optional[bool] = None
    has_security: Optional[bool] = None

    @model_validator(mode="after")
    def validate_floor(self):
        if self.floor > self.total_floors:
            raise ValueError("floor cannot be greater than total_floors")
        if self.living_area is not None and self.living_area > self.area:
            raise ValueError("living_area cannot be greater than area")
        if self.kitchen_area is not None and self.kitchen_area > self.area:
            raise ValueError("kitchen_area cannot be greater than area")
        if self.year_built is not None and self.year_built > self.current_year:
            raise ValueError("year_built cannot be in the future")
        return self

    @computed_field
    @property
    def current_year(self) -> int:
        return date.today().year


class PredictionResponse(BaseModel):
    predicted_price: float
    predicted_price_rounded: int
    currency: str = "KZT"
