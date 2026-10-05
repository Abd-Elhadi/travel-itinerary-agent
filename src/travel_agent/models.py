from typing import Literal

from pydantic import BaseModel

##from travel_agent.models import ActivityPlan, TripRequest, VisaResult

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


class TransportOption(BaseModel):
    mode: Literal["flight", "car_rental", "train", "local"]
    description: str
    cost_usd_total: float  # whole group, whole trip
    is_estimate: bool
 
 
class TransportPlan(BaseModel):
    options: list[TransportOption]  # best value first
    notes: str
 
 
class StayOption(BaseModel):
    name: str
    area: str
    total_cost_usd: float | None  # whole group, all nights
    why: str
    is_estimate: bool
 
 
class StayPlan(BaseModel):
    options: list[StayOption]  # best fit first
    notes: str
 
 
class BudgetReport(BaseModel):
    flights_usd: float
    stay_usd: float
    activities_usd: float
    local_transport_usd: float
    food_usd: float
    total_usd: float
    budget_usd: float
    within_budget: bool
    remaining_usd: float
 
 
class DayPlan(BaseModel):
    day: int
    date: str | None
    city: str
    items: list[str]
 
 
class Itinerary(BaseModel):
    title: str
    summary: str
    visa_note: str
    days: list[DayPlan]
    budget_note: str
 
 
class TripPlan(BaseModel):
    trip: TripRequest
    visa: VisaResult
    activities: ActivityPlan
    transport: TransportPlan
    stay: StayPlan
    budget: BudgetReport
    itinerary: Itinerary
 