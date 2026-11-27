import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHAPTER = ROOT / "examples/ch24"


def run(script, output):
    subprocess.run([sys.executable, str(CHAPTER / script), "--output", str(output)],
                   check=True, timeout=30)


def test_stop_races_from_public_entrypoint(tmp_path):
    log = tmp_path / "timeline.jsonl"
    run("stream_interrupt_demo.py", log)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert len({(r["phase"], r["capacity"], r["medium"], r["repeated_stop"], r["mode"])
                for r in rows}) == len(rows) == 120
    for row in rows:
        events = row["events"]
        stop = next(i for i, e in enumerate(events) if e["kind"] == "user_stop")
        deliveries = [e for e in events[stop:] if e["kind"] == "present"]
        assert [e["value"] for e in deliveries if e["generation"] == 2] == ["new-turn"]
        if row["mode"] == "fenced":
            assert all((e["turn_id"], e["generation"]) == ("turn-2", 2) for e in deliveries)
            if row["phase"] == "in_flight":
                parked = next(e for e in events[:stop] if e["kind"] == "dequeued")
                rejected = next(e for e in events[stop:] if e["kind"] == "obsolete")
                for field in ("turn_id", "generation", "sequence", "value"):
                    assert parked[field] == rejected[field]
                assert row["measurements"]["cleared"] == row["capacity"] - 1
        if row["mode"] == "propagate" and row["phase"] == "in_flight":
            kinds = [e["kind"] for e in events[stop:]]
            assert kinds.index("cancel_received") < kinds.index("producer_exit") < kinds.index("producer_joined")
            assert kinds.index("producer_joined") < kinds.index("present")
        if row["phase"] == "before_start" and row["mode"] != "ui_only":
            assert row["measurements"]["cancel_received_us"] is None
            assert row["measurements"]["producer_exit_us"] is None
            assert row["measurements"]["producer_joined_us"] is not None
        if row["phase"] == "after_commit":
            assert "tool_committed" in [e["kind"] for e in events[:stop]]
            assert "receipt_recorded" in [e["kind"] for e in events[stop:]]


def test_late_commands_and_receipts_keep_distinct_identities(tmp_path):
    out = tmp_path / "receipt.json"
    run("late_receipt.py", out)
    rows = json.loads(out.read_text())
    assert len(rows) == 8
    for r in rows:
        assert [e["event"] for e in r["trace"]] == ["service_commit", "switch_owner", "delayed_stop", "receipt_arrived"]
        assert (r["ticket_count"], r["created_count"], r["business_ok"]) == (1, 1, True)
        correct = (r["rule"] == "pair" or (r["rule"], r["successor"]) in
                   {("turn", "next_turn"), ("generation", "retry_same_turn")})
        assert r["visible"] == (["new-output"] if correct else ["ticket-1"])


def test_low_watermark_controls_actual_wakeups(tmp_path):
    out = tmp_path / "watermarks.json"
    run("watermarks.py", out)
    rows = json.loads(out.read_text())
    assert [(r["low"], r["pauses"]) for r in rows] == [(3, 20), (1, 7)]
    for r in rows:
        assert max(e["depth"] for e in r["events"]) == 4
        assert all(e["depth"] <= r["low"] for e in r["events"] if e["kind"] == "resume")
        assert [e["sequence"] for e in r["events"] if e["kind"] == "present"] == list(range(24))


def test_exported_sample_matches_canonical_chapter():
    # Render at its published location so relative asset links are verified too.
    import runpy
    export = runpy.run_path(str(CHAPTER / "export_sample.py"))
    destination = CHAPTER / "sample_ch24_zh.md"
    assert destination.read_text(encoding="utf-8") == export["render"](destination)
