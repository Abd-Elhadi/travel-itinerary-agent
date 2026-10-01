# Smart Travel Itinerary Assistant

Multi-agent travel planner built with the OpenAI Agents SDK.

## Abstract

Plan leisure or business trips from one conversation. The assistant collects trip details, checks visa rules, finds flights and stays, builds a day-by-day itinerary within budget, and emails a detailed report. Specialist agents handle each task and a manager agent coordinates them.

## Goals

- Collect trip request: type (leisure or business), origin passport, destination, dates, days, budget, group size, interests
- Check visa and entry requirements
- Search flights, hotels, car rental
- Build itinerary with activities, free time, weather
- Stay within budget; flag overruns
- Send report by email
- Remember traveler preferences across sessions

## Agents

| Agent             | Job                                             | Tools                               |
| ----------------- | ----------------------------------------------- | ----------------------------------- |
| Intake            | Ask questions, output structured TripRequest    | none, structured output             |
| Visa              | Entry requirements for passport and destination | visa API                            |
| Transport         | Flights, car rental                             | flight API                          |
| Stay              | Hotels near plans or meetings                   | stays API                           |
| Activities        | Attractions, weather, free-time slots           | places API, weather API, web search |
| Budget            | Total costs, compare with budget                | calculator tool                     |
| Planner (manager) | Calls specialists as tools, merges output       | specialists as tools                |
| Report            | Final report and email                          | email tool                          |

## Tech stack

- Python 3.12 or newer
- uv for packages
- OpenAI Agents SDK
- Cursor and Jupyter notebooks
- Gradio for UI
- SQLite for memory

## Setup

```bash
git clone <repo-url>
cd travel-itinerary-agent
uv sync
cp .env.example .env   # add your keys
uv run jupyter lab
```
