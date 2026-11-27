"""Validate the published drill evidence, including the two intentionally blocked releases."""
import hashlib
import json
import subprocess
import sys

import pytest
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


@pytest.mark.skipif(sys.version_info[:2] != (3, 12), reason="Chapter 36 pins its teaching runtime to Python 3.12")
def test_release_consumes_actual_failing_gate(tmp_path):
    out = tmp_path / "release"
    command = [sys.executable, str(REPORTS.parent / "ci/drill.py"), "--fault", "client-regression",
               "--output", str(out)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    assert result.returncode == 1 and result.stdout.strip() == "hold", result.stderr
    release = json.loads((out / "release.json").read_text(encoding="utf-8"))
    evidence = release["regression_evidence"]
    gate_bytes = (out / evidence["file"]).read_bytes()
    gate = json.loads(gate_bytes)
    assert hashlib.sha256(gate_bytes).hexdigest() == evidence["sha256"]
    assert evidence["failed"] == [r["id"] for r in gate["rows"] if not r["passed"]]
    assert len(evidence["failed"]) == 8 and evidence["complete"]
    assert evidence["config_digest"] == gate["config_digest"]
    assert evidence["exit_code"] == 1 and evidence["decision"] == "hold"
    assert [g for g, ok in release["gates"].items() if not ok] == ["regression"]
    assert release["timeline"] == []
