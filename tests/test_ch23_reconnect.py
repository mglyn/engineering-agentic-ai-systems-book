import json
from pathlib import Path
import subprocess
import sys


def test_reconnect_evidence_and_published_example(tmp_path):
    root = Path(__file__).resolve().parents[1]
    report = tmp_path / "replay.json"
    subprocess.run([sys.executable, str(root / "examples/ch23/session_replay.py"),
                    "--output", str(report)], check=True, timeout=30)
    data = json.loads(report.read_text(encoding="utf-8"))
    appendix = (root / "docs/zh/appendix_c_schemas.md").read_text(encoding="utf-8")
    example = json.loads(appendix.split("```json\n", 1)[1].split("```", 1)[0])
    assert example == data["sessions"]["completed"][-1]
    assert len({(r["profile"], r["variant"]) for r in data["cases"]}) == 60
    for case in data["cases"]:
        assert case["result"]["status"] == case["profile"]
        assert case["before"] == case["after"]
        if case["variant"] == "changed_payload":
            assert "reject_conflict" in case["actions"]
        if case["variant"] == "missing_end":
            assert case["actions"] == ["backfill"]
        if case["variant"] == "legacy_version":
            assert case["actions"] == []
    assert data["same_key_retry"]["counts"] == [1, 2]
    assert data["transcript_only"]["after"] == [2, 3]
