"""Author the local paired-scene corpus and its transport mutations."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent
SCENARIOS = ("aligned", "previous_turn", "late_frame", "missing_frame", "revised_transcript",
             "old_transcript", "overlap", "expired_frame", "after_deadline", "file_fallback")
ITEMS = ("车票", "住宿单", "停车票", "轮渡票", "餐费单", "行李票", "地铁票", "公交票", "快递单", "会务单")


def make(number):
    scenario = SCENARIOS[(number - 1) % 10]
    side = "右" if number <= 10 else "左"
    other = "左" if side == "右" else "右"
    name = f"receipt-{number:02d}"
    item = ITEMS[(number - 1) % 10]
    spoken = f"帮我核对{side}边这张{item}。"
    if scenario == "revised_transcript":
        spoken = f"刚才说错了，请核对{side}边这张{item}。"
    labels = {k:f"{name}-{v}" for k, v in (("左", "L"), ("右", "R"))}
    events = []

    def event(kind, turn, captured, received, **payload):
        events.append(dict(event_id=f"{name}-e{len(events)+1}", session_id=name, turn_id=turn,
                           kind=kind, captured_ms=captured, received_ms=received, payload=payload))

    event("image", 1, 300, 1200 if scenario == "previous_turn" else 400,
          ref="page@1", objects={k:v+"-old" for k,v in labels.items()})
    if scenario not in {"missing_frame", "file_fallback"}:
        received = {"late_frame":1360, "after_deadline":1700}.get(scenario,1100)
        captured = 600 if scenario == "expired_frame" else 1000
        event("image", 2, captured, received, ref="page@2", objects=labels)
    if scenario == "file_fallback":
        event("file", 2, 1010, 1330, ref="page@2", objects=labels)
    event("speech", 2, 1170, 1210, ref="page@2", side=other if scenario == "revised_transcript"
          else side, revision=1, final=False, speaker="user")
    if scenario == "overlap":
        event("speech", 2, 1180, 1220, ref="page@2", side=other, revision=1, final=True, speaker="unknown")
    event("speech", 2, 1190, 1250, ref="page@2", side=side, revision=2, final=True, speaker="user")
    if scenario == "old_transcript":
        event("speech", 1, 550, 1230, ref="page@1", side=other, revision=3, final=True, speaker="user")
    gold = None if scenario in {"missing_frame","overlap","expired_frame","after_deadline"} else labels[side]
    return dict(case_id=name, scenario=scenario, utterance=spoken, image=f"media/{name}.svg",
                audio=f"media/{name}.wav", active_turn=2, expected=gold, events=events), labels, item


def main():
    (ROOT/"media").mkdir(exist_ok=True)
    rows = []
    for n in range(1,21):
        row, labels, item = make(n)
        rows.append(row)
        cards = []
        for x, side in ((20,"左"),(320,"右")):
            cards.append(f'<rect x="{x}" y="20" width="270" height="120" rx="8" fill="#e5f1ef"/>'
                         f'<text x="{x+15}" y="64">{item} · {side}</text>'
                         f'<text x="{x+15}" y="106">{labels[side]}</text>')
        svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 610 160" '
               'font-family="sans-serif" font-size="22">' + "".join(cards) + '</svg>')
        (ROOT/row["image"]).write_text(svg, encoding="utf-8")
    (ROOT/"media_sync_cases.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False)+"\n"
                                                       for row in rows), encoding="utf-8")


if __name__ == "__main__":
    main()
