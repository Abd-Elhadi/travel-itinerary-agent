from travel_agent.memory import ProfileStore


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
