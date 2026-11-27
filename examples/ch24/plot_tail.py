"""Render Fig-24-03 from JSONL. Optional plotting dependency: matplotlib."""
import argparse
import json
from pathlib import Path
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument("log", type=Path)
parser.add_argument("figure", type=Path)
args = parser.parse_args()
rows = [json.loads(line) for line in args.log.read_text(encoding="utf-8").splitlines()]
fig, ax = plt.subplots(figsize=(7, 3.6), layout="constrained")
for mode, marker in [("ui_only", "o"), ("propagate", "+"), ("fenced", "x")]:
    values = sorted(row["old_tail_us"] for row in rows if row["mode"] == mode)
    ax.plot(values, [(i + 1) / len(values) for i in range(len(values))],
            drawstyle="steps-post", marker=marker, markersize=3, label=mode)
ax.set(xlabel="Last old delivery after stop (microseconds)", ylabel="Fraction of schedules",
       ylim=(0, 1.04), xlim=(0, None))
ax.legend(loc="lower right")
ax.grid(alpha=0.2)
args.figure.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(args.figure, dpi=180)

