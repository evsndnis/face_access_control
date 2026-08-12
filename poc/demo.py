from src.schemas import AccessVerifyResponse

from poc.pipeline import load_demo_events, run_event

# canonical risky-случай для критериев готовности: offline + устаревший кэш
# должен дать manual_review независимо от match_score (см. docs/architecture.md,
# событие #5). Остальные risky-события (#2 quality, #3 spoofing, #4 margin)
# прогоняются в __main__ для полноты демонстрации.
RISKY_EVENT_ID = "e-1005"


def run_happy_path() -> AccessVerifyResponse:
    events = load_demo_events()
    return run_event(events["e-1001"])


def run_risky_path() -> AccessVerifyResponse:
    events = load_demo_events()
    return run_event(events[RISKY_EVENT_ID])


def _print_result(label: str, response: AccessVerifyResponse) -> None:
    print(f"\n=== {label} ({response.event_id}) ===")
    print(f"decision           = {response.decision}")
    print(f"turnstile_command  = {response.turnstile_command}")
    print(f"reasons            = {response.reasons}")
    print(f"match_score        = {response.match_score}")
    print(f"margin_to_second   = {response.margin_to_second_best}")
    print(f"degraded_mode      = {response.degraded_mode}")
    print(f"latency_ms         = {response.latency_ms}")


if __name__ == "__main__":
    _print_result("HAPPY PATH", run_happy_path())
    _print_result("RISKY PATH (offline, stale cache)", run_risky_path())

    events = load_demo_events()
    for event_id, label in [
        ("e-1002", "RISKY: low quality (mask/backlight)"),
        ("e-1003", "RISKY: spoofing suspicion (low liveness)"),
        ("e-1004", "RISKY: ambiguous match (small margin)"),
    ]:
        _print_result(label, run_event(events[event_id]))

    from poc.pipeline import AUDIT_LOG_PATH

    print(f"\nAudit log: {AUDIT_LOG_PATH}")
