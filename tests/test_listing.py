from handoff.listing import clamp_limit


def test_limit_stays_inside_contract() -> None:
    assert clamp_limit(0) == 1
    assert clamp_limit(500) == 100
