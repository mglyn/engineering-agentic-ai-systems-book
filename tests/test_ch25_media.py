import json
from pathlib import Path
import subprocess
import sys


def test_media_and_playout_from_cli(tmp_path):
    base = Path(__file__).resolve().parents[1] / "examples/ch25"
    output = tmp_path / "run.json"
    def read(script):
        subprocess.run([sys.executable, str(base/script), "--output", str(output)], check=True, timeout=15)
        return json.loads(output.read_text(encoding="utf-8"))
    rows = read("media_sync.py")
    assert len({(r["case"],r["policy"]) for r in rows}) == len(rows) == 40
    for row in rows:
        if row["policy"] != "bound":
            continue
        if row["scenario"] in {"overlap","expired_frame","after_deadline","missing_frame"}:
            assert row["object_id"] is None and row["action"].startswith("clarify")
        else:
            assert row["object_id"] == row["case"] + ("-R" if int(row["case"][-2:]) <= 10 else "-L")
            assert row["selected_ref"] == "page@2" and row["source_turn"] == 2
        if row["scenario"] == "late_frame":
            assert row["wait_ms"] == 110
    cues = read("playout.py")
    assert len(cues) == 240
    for row in cues:
        assert row["text_on"] >= row["text_rx"] and row["audio_on"] >= row["audio_rx"]
    assert max(abs(r["skew_ms"]) for r in cues if r["buffer_ms"] == 80) == 40
