import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from travel_agent.models import TripRequest

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "data" / "memory.db"  # keep in .gitignore


class ProfileStore:
    """Long-term memory in SQLite: a traveler profile plus a short trip history."""

    def __init__(self, db_path: Path | str = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS traveler_profile (
                    user_id TEXT PRIMARY KEY,
                    passport_country TEXT,
                    origin TEXT,
                    interests TEXT NOT NULL DEFAULT '[]',
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS trips (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    destination TEXT,
                    num_days INTEGER,
                    travelers INTEGER,
                    budget_usd REAL,
                    total_usd REAL,
                    created_at TEXT NOT NULL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def load(self, user_id: str) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM traveler_profile WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return {
            "passport_country": row["passport_country"],
            "origin": row["origin"],
            "interests": json.loads(row["interests"]),
        }

    def save_from_trip(self, user_id: str, trip: TripRequest) -> None:
        """Remember passport, home city, and interests. Interests accumulate across trips."""
        previous = self.load(user_id) or {"passport_country": None, "origin": None, "interests": []}
        interests = list(previous["interests"])
        for interest in trip.interests:
            if interest.lower() not in {i.lower() for i in interests}:
                interests.append(interest)
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """INSERT INTO traveler_profile (user_id, passport_country, origin, interests, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(user_id) DO UPDATE SET
                     passport_country = excluded.passport_country,
                     origin = excluded.origin,
                     interests = excluded.interests,
                     updated_at = excluded.updated_at""",
                (
                    user_id,
                    trip.passport_country or previous["passport_country"],
                    trip.origin or previous["origin"],
                    json.dumps(interests),
                    self._now(),
                ),
            )

    def save_trip(self, user_id: str, trip: TripRequest, total_usd: float) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """INSERT INTO trips (user_id, destination, num_days, travelers, budget_usd, total_usd, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (user_id, trip.destination, trip.num_days, trip.travelers, trip.budget_usd, total_usd, self._now()),
            )

    def recent_trips(self, user_id: str, limit: int = 3) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT destination, num_days, travelers, total_usd FROM trips "
                "WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def as_text(self, user_id: str) -> str | None:
        """One line summary for the Intake agent, or None for a new traveler."""
        profile = self.load(user_id)
        if profile is None:
            return None
        parts = []
        if profile["passport_country"]:
            parts.append(f"passport {profile['passport_country']}")
        if profile["origin"]:
            parts.append(f"usual departure city {profile['origin']}")
        if profile["interests"]:
            parts.append("interests " + ", ".join(profile["interests"]))
        trips = self.recent_trips(user_id)
        if trips:
            parts.append("past trips " + "; ".join(f"{t['destination']} ({t['num_days']} days)" for t in trips))
        return "; ".join(parts) or None