"""Reconstruct scheduler occupancy from an archived event stream, without calling adapters."""
import argparse
from collections import Counter
import json
from pathlib import Path


def replay(report, run):
    jobs = {j["name"]:j for j in report["jobs"]}
    states = dict.fromkeys(jobs, "planned")
    occupancy = Counter()
    peak = 0
    next_state = {"ready":("planned","ready"), "dispatch":("ready","running"),
                  "planned":("running","planned"), "done":("running","done"),
                  "cancelled":("running","cancelled"), "timeout":("running","timeout"),
                  "blocked":("planned","blocked"), "worker_enter":("running","running"),
                  "worker_lost":("running","running")}
    for event in run["trace"]:
        name, kind, tenant = event["task"], event["kind"], event["tenant"]
        job = jobs[name]
        source, target = next_state[kind]
        if states[name] != source or job["tenant"] != tenant:
            raise ValueError(f"illegal event {event}")
        if kind == "ready" and any(states[d] != "done" for d in job["dependencies"]):
            raise ValueError(f"premature release {name}")
        if kind == "blocked" and not any(states[d] in {"cancelled","timeout","blocked"}
                                         for d in job["dependencies"]):
            raise ValueError(f"unexpected block {name}")
        if target == "running" and source != target:
            occupancy[tenant] += 1
        if source == "running" and target != source:
            occupancy[tenant] -= 1
        if run["mode"] == "bounded" and (occupancy[tenant] > report["config"]["tenant_limit"]
                or sum(occupancy.values()) > report["config"]["workers"]):
            raise ValueError("quota exceeded")
        peak = max(peak, sum(occupancy.values()))
        states[name] = target
    if (any(occupancy.values()) or dict(Counter(states.values())) != run["states"]
            or peak != run["peak_active"]):
        raise ValueError("incomplete or inconsistent final ledger")
    return states


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    report = json.loads(parser.parse_args().report.read_text(encoding="utf-8"))
    runs = report["normal"] + report["faults"]
    for run in runs:
        replay(report, run)
    print(f"replayed {len(runs)} runs")
