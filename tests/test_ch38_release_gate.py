import json
from pathlib import Path
import subprocess
import sys


def test_gate_rejects_wrong_disposition_even_when_effect_is_safe(tmp_path):
    runner = Path(__file__).resolve().parents[1]/"examples/ch38/regression_runner"
    for name, code in (("baseline",0),("model-change",1)):
        result = subprocess.run([sys.executable,str(runner/"run.py"),"--candidate",name,
                                 "--output",str(tmp_path/f"{name}.json")],timeout=45)
        assert result.returncode == code
    base = tmp_path/"baseline.json"
    candidate = tmp_path/"model-change.json"
    diff = tmp_path/"diff.json"
    cmd = [sys.executable,str(runner/"compare.py"),str(base),str(candidate),"--output",str(diff)]
    subprocess.run(cmd,check=True,timeout=10)
    report = json.loads(diff.read_text(encoding="utf-8"))
    assert report["decision"] == "hold"
    row, = report["differences"]
    assert (row["id"],row["failures"],row["old_count"],row["new_count"]) == ("supervisor",["reason"],0,0)
    data = json.loads(candidate.read_text(encoding="utf-8"))
    data["rows"] = [r for r in data["rows"] if r["id"] != "supervisor"]
    candidate.write_text(json.dumps(data),encoding="utf-8")
    assert subprocess.run(cmd,capture_output=True,timeout=10).returncode != 0


def test_duplicate_send_is_visible_even_when_business_state_and_trace_agree(tmp_path):
    root = Path(__file__).resolve().parents[1]
    runner = root / "examples/ch38/regression_runner"
    for name, code in (("baseline", 0), ("client-change", 1)):
        result = subprocess.run([sys.executable, str(runner / "run.py"), "--candidate", name,
                                 "--output", str(tmp_path / f"{name}.json")], timeout=45)
        assert result.returncode == code
    base = json.loads((tmp_path / "baseline.json").read_text(encoding="utf-8"))
    candidate = json.loads((tmp_path / "client-change.json").read_text(encoding="utf-8"))
    changed = []
    for old, new in zip(base["rows"], candidate["rows"], strict=True):
        assert old["id"] == new["id"]
        for field in ("trace", "status", "reason", "tickets", "creates"):
            assert old[field] == new[field]
        if new["creates"]:
            assert new["replays"] == 1 and old["replays"] == 0
            assert new["calls"].count("create") == old["calls"].count("create") + 1
            assert new["errors"] == ["tool_sequence", "unexpected_resend"]
            changed.append(new["id"])
        else:
            assert new["passed"]
    assert len(changed) == 8
