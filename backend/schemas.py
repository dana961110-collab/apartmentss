from typing import Optional

from pydantic import BaseModel, Field, model_validator


class ApartmentRequest(BaseModel):
    rooms: float = Field(..., gt=0, description="Number of rooms")
    area: float = Field(..., gt=0, description="Total apartment area in square meters")
    floor: float = Field(..., ge=0, description="Apartment floor")
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
        return self


class PredictionResponse(BaseModel):
    predicted_price: float
    predicted_price_rounded: int
    currency: str = "KZT"
