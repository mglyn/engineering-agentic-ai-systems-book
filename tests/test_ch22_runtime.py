import json
from pathlib import Path
import subprocess
import sys


def test_real_worker_exit_and_tenant_isolation(tmp_path):
    root = Path(__file__).resolve().parents[1]
    source = root / "examples/ch22"
    cfg = json.loads((source / "runtime_config.yaml").read_text(encoding="utf-8"))
    config = tmp_path / "config.yaml"
    config.write_text(json.dumps(cfg | {"repetitions": 1}), encoding="utf-8")
    log = tmp_path / "out.json"
    subprocess.run([sys.executable, str(source/"async_runtime.py"), "--config", str(config),
                    "--output", str(log)], check=True, timeout=30)
    subprocess.run([sys.executable, str(source/"replay_load.py"), str(log)], check=True, timeout=10)
    runs = json.loads(log.read_text(encoding="utf-8"))
    recovered, cancelled, timeout = runs["faults"]
    attempts = [e["attempt"] for e in recovered["trace"] if e["kind"]=="dispatch" and e["task"]=="batch-0"]
    assert attempts == [1, 2]
    for fault in (cancelled, timeout):
        assert sum(e["kind"]=="done" and e["tenant"]=="interactive" for e in fault["trace"]) == 25
        assert {e["task"] for e in fault["trace"] if e["kind"]=="blocked"} == {
            f"batch-{i}" for i in range(15, 25)}
    for run in runs["normal"]:
        assert run["peak_endpoint"] <= cfg["endpoint_slots"]
        if run["mode"] == "bounded":
            assert run["peak_ready"] <= 2 * cfg["ready_per_tenant"]
