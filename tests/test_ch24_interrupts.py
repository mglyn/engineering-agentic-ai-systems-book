import json
from pathlib import Path
import subprocess
import sys


def test_stop_races_from_public_entrypoint(tmp_path):
    root = Path(__file__).resolve().parents[1]
    log = tmp_path / "timeline.jsonl"
    subprocess.run([sys.executable, str(root / "examples/ch24/stream_interrupt_demo.py"),
                    "--output", str(log)], check=True, timeout=30)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len({(r["phase"], r["capacity"], r["medium"], r["repeated_stop"], r["mode"])
                for r in rows}) == len(rows) == 120
    for row in rows:
        events = row["events"]
        stop = next(i for i, e in enumerate(events) if e["kind"] == "user_stop")
        deliveries = [e for e in events[stop:] if e["kind"] == "present"]
        assert [e["value"] for e in deliveries if e["generation"] == 2] == ["new-turn"]
        if row["mode"] == "fenced":
            assert all(e["generation"] == 2 for e in deliveries)
        elif row["phase"] == "in_flight":
            assert any(e["generation"] == 1 for e in deliveries)
        if row["phase"] == "after_commit":
            assert "tool_committed" in [e["kind"] for e in events[:stop]]
            assert "receipt_recorded" in [e["kind"] for e in events[stop:]]

