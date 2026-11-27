"""Compare two reports with identical inputs and show the first divergent business event."""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]


def index(report, required):
    rows = report["rows"]
    if report["schema"] != "book-gate-1" or sorted(row["id"] for row in rows) != required:
        raise ValueError("report omits or duplicates a slice")
    return {r["id"]:r for r in rows}


def compare(base, candidate):
    required = sorted(item["id"] for item in json.loads((HERE/"golden_slices.yaml").read_text()))
    old, new = index(base,required), index(candidate,required)
    if base["decision"] != "pass" or not all(r["passed"] for r in old.values()):
        raise ValueError("baseline did not pass")
    if base["inputs"] != candidate["inputs"]:
        raise ValueError("input identities differ; review and re-establish the baseline")
    delta = {k:[v,candidate["config"][k]] for k,v in base["config"].items() if v!=candidate["config"][k]}
    rows = []
    for name in required:
        a, b = old[name], new[name]
        left, right = [e["kind"] for e in a["trace"]], [e["kind"] for e in b["trace"]]
        pos = next((i for i in range(max(len(left),len(right))) if left[i:i+1]!=right[i:i+1]),None)
        if not b["passed"] or pos is not None or a["reason"]!=b["reason"]:
            rows.append(dict(id=name, old_reason=a["reason"], new_reason=b["reason"], failures=b["errors"],
                             old_event=left[pos:pos+1] if pos is not None else [],
                             new_event=right[pos:pos+1] if pos is not None else [],
                             old_count=a["creates"], new_count=b["creates"]))
    return dict(candidate=candidate["recipe"], changed=delta, differences=rows, decision=candidate["decision"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("candidate",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    args = parser.parse_args()
    result = compare(*(json.loads(p.read_text(encoding="utf-8")) for p in (args.baseline,args.candidate)))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(result["candidate"],result["decision"],len(result["differences"]),"different slices")
