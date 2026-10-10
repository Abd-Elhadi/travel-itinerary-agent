import re
from pathlib import Path

from travel_agent import knowledge
from travel_agent.memory import ProfileStore

GUIDES = Path(__file__).resolve().parents[1] / "data" / "guides"
FEES = {"free", "low", "moderate", "high", "varies"}


# ---- long-term memory ----

def test_new_traveler_has_no_profile(tmp_path):
    store = ProfileStore(tmp_path / "m.db")
    assert store.load("omar") is None
    assert store.as_text("omar") is None


def test_profile_saved_and_interests_accumulate(tmp_path, trip):
    store = ProfileStore(tmp_path / "m.db")
    store.save_from_trip("omar", trip)  # interests: food, temples
    trip.destination = "Italy"
    trip.interests = ["Food", "museums"]
    store.save_from_trip("omar", trip)
    profile = store.load("omar")
    assert profile["passport_country"] == "France"
    assert profile["origin"] == "Miami"
    assert profile["interests"] == ["food", "temples", "museums"]


def test_profile_survives_new_store_instance(tmp_path, trip):
    ProfileStore(tmp_path / "m.db").save_from_trip("omar", trip)
    assert ProfileStore(tmp_path / "m.db").load("omar")["origin"] == "Miami"


def test_trip_history_and_text_summary(tmp_path, trip):
    store = ProfileStore(tmp_path / "m.db")
    store.save_from_trip("omar", trip)
    store.save_trip("omar", trip, 4365.0)
    text = store.as_text("omar")
    assert "passport France" in text
    assert "Miami" in text
    assert "Japan (7 days)" in text
    assert store.recent_trips("omar")[0]["total_usd"] == 4365.0


def test_users_are_separate(tmp_path, trip):
    store = ProfileStore(tmp_path / "m.db")
    store.save_from_trip("omar", trip)
    assert store.load("someone-else") is None


# ---- knowledge base ----

def test_file_search_tool_needs_vector_store_id(monkeypatch):
    monkeypatch.delenv("VECTOR_STORE_ID", raising=False)
    assert knowledge.file_search_tool() is None
    monkeypatch.setenv("VECTOR_STORE_ID", "vs_123")
    tool = knowledge.file_search_tool()
    assert tool is not None
    assert tool.vector_store_ids == ["vs_123"]


def test_guides_have_enough_valid_entries():
    files = sorted(GUIDES.glob("*.md"))
    assert {f.stem for f in files} >= {"kyoto", "rome", "london"}
    for path in files:
        text = path.read_text(encoding="utf-8")
        sections = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
        assert len(sections) >= 12, f"{path.name} has too few entries"
        for section in sections:
            title = section.splitlines()[0]
            for field in ("City", "Type", "Area", "Entry", "Typical visit", "Why"):
                assert f"- {field}:" in section, f"{path.name}: '{title}' is missing {field}"
            entry = re.search(r"- Entry: (\w+)", section).group(1)
            assert entry in FEES, f"{path.name}: '{title}' has fee category '{entry}'"