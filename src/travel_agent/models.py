from typing import Literal

from pydantic import BaseModel


class TripRequest(BaseModel):
    trip_type: Literal["leisure", "business"] | None
    passport_country: str | None
    origin: str | None
    destination: str | None
    start_date: str | None  # YYYY-MM-DD
    end_date: str | None  # YYYY-MM-DD
    num_days: int | None
    travelers: int | None  # 1 means solo
    budget_usd: float | None
    interests: list[str]
    meeting_address: str | None  # business only
    needs_car_rental: bool | None  # business only


class IntakeResult(BaseModel):
    trip: TripRequest
    missing_fields: list[str]
    next_question: str | None
    is_complete: bool


class VisaResult(BaseModel):
    passport: str
    destination: str
    requirement: str  # visa_free, e_visa, visa_required, unknown, ...
    allowed_days: int | None
    summary: str
    source: Literal["orizn_api", "mock"]


class Activity(BaseModel):
    name: str
    category: str
    why: str
    estimated_cost_usd: float | None
    duration_hours: float | None
    from_tool: bool  # True if returned by places tool, False if from web search


class ActivityPlan(BaseModel):
    destination: str
    weather_summary: str
    activities: list[Activity]