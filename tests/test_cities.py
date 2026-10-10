from travel_agent.cities import allocate_parts, expand_city_plan, parse_cities


def test_parse_cities_comma_and_and():
    assert parse_cities("Kathmandu, Pokhara") == ["Kathmandu", "Pokhara"]
    assert parse_cities("Kathmandu and Pokhara") == ["Kathmandu", "Pokhara"]
    assert parse_cities("Miami") == ["Miami"]
    assert parse_cities("") == []
    assert parse_cities(None) == []


def test_allocate_parts_gives_remainder_to_gateway():
    assert allocate_parts(7, 2) == [4, 3]
    assert allocate_parts(6, 2) == [3, 3]
    assert allocate_parts(5, 2) == [3, 2]


def test_expand_city_plan():
    assert expand_city_plan(["Kathmandu", "Pokhara"], 7) == (
        ["Kathmandu"] * 4 + ["Pokhara"] * 3
    )
