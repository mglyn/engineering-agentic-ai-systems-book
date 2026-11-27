"""Replay media envelopes on a virtual clock. No ASR, vision model or rendering benchmark."""
import argparse
import json
from pathlib import Path
import wave
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parent


def decide(events, turn, policy, wait_ms=200, max_age_ms=300):
    frames = []
    words = None
    start = deadline = None
    overlap = False
    trace = []
    for event in sorted(events, key=lambda e:e["received_ms"]):
        now, body = event["received_ms"], event["payload"]
        if deadline is not None and now > deadline:
            break
        if policy == "bound" and event["turn_id"] != turn:
            trace.append([now, "other_turn"])
            continue
        if event["kind"] in {"image","file"}:
            frames.append(event)
        elif body["speaker"] == "unknown" and policy == "bound":
            overlap = True
            trace.append([now, "speaker_ambiguous"])
        elif body["final"]:
            if words is None or body["revision"] > words["payload"]["revision"]:
                words = event
                if start is None:
                    start, deadline = now, now + wait_ms
        else:
            trace.append([now, "partial"])
        if words is None:
            continue
        if overlap:
            return result(None, words, now, start, "clarify_speaker", trace)
        candidates = frames
        if policy == "bound":
            candidates = [f for f in frames if f["payload"]["ref"] == words["payload"]["ref"]
                          and 0 <= words["captured_ms"] - f["captured_ms"] <= max_age_ms]
        if candidates:
            frame = candidates[-1]
            return result(frame, words, now, start, frame["kind"], trace)
    if words is None:
        raise ValueError("fixture lacks final transcript")
    return result(None, words, deadline, start, "clarify_object", trace)


def result(frame, words, now, start, action, trace):
    return dict(object_id=frame["payload"]["objects"][words["payload"]["side"]] if frame else None,
                turn_used=words["turn_id"], source_turn=frame["turn_id"] if frame else None,
                selected_ref=frame["payload"]["ref"] if frame else None,
                decision_ms=now, wait_ms=now-start, action=action, notes=trace,
                capture_offset_ms=words["captured_ms"]-frame["captured_ms"] if frame else None)


def verify_media(row):
    with wave.open(str(ROOT/row["audio"]), "rb") as f:
        duration = round(f.getnframes()*1000/f.getframerate())
    svg_text = set(ElementTree.parse(ROOT/row["image"]).getroot().itertext())
    if duration <= 0 or row["expected"] is not None and row["expected"] not in svg_text:
        raise ValueError(f"unusable paired media: {row['case_id']}")
    return duration


def run(cases):
    records = []
    for row in cases:
        duration = verify_media(row)
        for policy in ("arrival","bound"):
            choice = decide(row["events"], row["active_turn"], policy)
            records.append(dict(case=row["case_id"], scenario=row["scenario"], policy=policy,
                                audio_duration_ms=duration, expected=row["expected"],
                                correct=choice["object_id"] == row["expected"], **choice))
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch25/media.json"))
    args = parser.parse_args()
    cases = [json.loads(line) for line in (ROOT/"media_sync_cases.jsonl").read_text(encoding="utf-8").splitlines()]
    records = run(cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    for policy in ("arrival","bound"):
        subset = [r for r in records if r["policy"] == policy]
        print(policy, sum(r["correct"] for r in subset), "/", len(subset))
    raise SystemExit(int(not all(r["correct"] for r in records if r["policy"] == "bound")))
