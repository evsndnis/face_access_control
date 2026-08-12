from poc.demo import run_happy_path, run_risky_path


def test_happy_path_allows():
    response = run_happy_path()
    assert response.decision == "allow"
    assert response.turnstile_command == "open"


def test_risky_path_does_not_open():
    response = run_risky_path()
    assert response.decision != "allow"
    assert response.turnstile_command == "hold"
