"""Virtual playout of six aligned caption/audio cues for each archived short utterance."""
from pathlib import Path
import argparse
import json
import wave

ROOT = Path(__file__).parent


def playout(clip_ms, case_number, buffer_ms):
    rows = []
    for i in range(6):
        pts = i * clip_ms // 6
        # A later subtitle can still arrive in order. Both tracks share the same PTS.
        audio_rx = pts + (10, 30, 50)[(i+case_number) % 3]
        text_rx = pts + (5, 40, 70, 120)[(i+case_number) % 4]
        audio_on = max(pts+buffer_ms, audio_rx)
        text_on = max(pts+buffer_ms, text_rx)
        rows.append(dict(cue=i, pts=pts, audio_rx=audio_rx, text_rx=text_rx,
                         audio_on=audio_on, text_on=text_on, skew_ms=text_on-audio_on))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch25/playout.json"))
    args = parser.parse_args()
    rows = []
    for n, line in enumerate((ROOT/"media_sync_cases.jsonl").read_text(encoding="utf-8").splitlines()):
        case = json.loads(line)
        with wave.open(str(ROOT/case["audio"]), "rb") as src:
            length = round(1000*src.getnframes()/src.getframerate())
        for delay in (0,80):
            for cue in playout(length,n,delay):
                rows.append(dict(case=case["case_id"], buffer_ms=delay, **cue))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows,indent=2), encoding="utf-8")
    for delay in (0,80):
        subset = [r for r in rows if r["buffer_ms"] == delay]
        print(delay, "max_abs_skew_ms", max(abs(r["skew_ms"]) for r in subset),
              "first_audio_ms", min(r["audio_on"] for r in subset))
