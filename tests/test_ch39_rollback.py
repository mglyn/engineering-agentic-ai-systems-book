"""Validate the published drill evidence, including the two intentionally blocked releases."""
import json
from pathlib import Path

REPORTS = Path(__file__).resolve().parents[1] / "examples/ch39/reports"


def report(name):
    return json.loads((REPORTS / f"{name}.json").read_text(encoding="utf-8"))


def test_partial_rollback_preserves_ticket_but_keeps_stale_grant():
    run = report("normal")
    phases = run["timeline"]
    assert [row["accepted"] for row in phases] == [True, True, False, False, True]
    assert all(row["process_healthy"] for row in phases)
    assert all(row["observed"]["tickets"] == phases[0]["observed"]["tickets"] for row in phases)
    assert [k for k, ok in phases[3]["facts"].items() if not ok] == ["cache"]
    assert phases[3]["observed"]["effective"] == ["read", "approve"]
    assert phases[4]["observed"]["effective"] == ["read"]
    assert run["delayed_alert"]["historical_alarm"] and not run["delayed_alert"]["current_alarm"]
    assert run["production_authorized"] is False


def test_missing_tests_and_log_marker_block_before_deployment():
    for name, gate in [("skip-tests", "tests"), ("log-marker", "log_marker_absent")]:
        run = report(name)
        assert run["result"] == "hold"
        assert run["timeline"] == []
        assert [key for key, ok in run["gates"].items() if not ok] == [gate]
