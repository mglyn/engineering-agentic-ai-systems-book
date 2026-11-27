"""Build two release probes and exercise rollback on Chapter 36's PRJ-3 database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile, ZipInfo

CHAPTER = Path(__file__).resolve().parents[1]
EXAMPLES = CHAPTER.parent
ROOT = EXAMPLES.parent
CANARY = "DEMO-SECRET-NOT-A-CREDENTIAL"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def command(*args, env=None):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT, env=env,
                            capture_output=True, encoding="utf-8", errors="replace", timeout=180)
    if result.returncode:
        raise RuntimeError(f"subprocess exited {result.returncode}: {result.stderr[-1500:]} {result.stdout[-1500:]}")
    return result.stdout


def build(path, version):
    with ZipFile(path, "w") as archive:
        archive.writestr(ZipInfo("__main__.py"), (CHAPTER / "deploy/probe.py").read_text(encoding="utf-8").encode("utf-8"))
        archive.writestr(ZipInfo("revision.py"), f"VERSION = {version!r}\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(out, fault):
    out.mkdir(parents=True, exist_ok=False)
    versions = {v: build(out / f"{v}.pyz", v) for v in ("r1", "r2")}
    config = read(CHAPTER / "deploy/profiles.json")["preprod"]
    expected_config = {"policy": config["policy"], "transport": config["transport"]}
    allowed = config["viewer"]
    task = read(EXAMPLES / "ch36/fixtures/task.json")
    expected = read(EXAMPLES / "ch36/fixtures/expected.json")
    command(EXAMPLES / "ch36/run.py", "reproduce", "--output", out / "projects")
    project = out / "projects/PRJ-3"
    tests = "absent"
    if fault != "skip-tests":
        env = dict(os.environ, PYTHONPATH=str(EXAMPLES / "ch36/src"), PYTHONUTF8="1")
        tests = command("-m", "pytest", "-q", "examples/ch37/tests/test_behaviour.py", env=env).strip()
    command(EXAMPLES / "ch38/regression_runner/run.py", "--output", out / "gate.json")
    gate = read(out / "gate.json")
    checks = dict(projects=read(out / "projects/reproduction.json")["passed"],
                  tests=tests != "absent", regression=gate["decision"] == "pass" and len(gate["rows"]) == 12)
    log = (["build complete", "candidate ready"] if fault != "log-marker"
           else ["build complete", "diagnostic " + CANARY])
    log_path = out / "build.log"
    log_path.write_text("\n".join(log), encoding="utf-8")
    checks["log_marker_absent"] = CANARY not in log_path.read_text(encoding="utf-8")
    report = dict(scope="local stdio processes; fixed model; course fixtures",
                  artifacts=versions, tests=tests, gates=checks, human_review="pending",
                  timeline=[], production_authorized=False)
    if not all(checks.values()):
        report["result"] = "hold"
        write(out / "release.json", report)
        return False

    state = out / "state"
    state.mkdir()
    write(state / "config.json", expected_config)
    write(state / "identity.json", {"viewer": allowed})
    write(state / "cache.json", {})
    scope_digest = hashlib.sha256(json.dumps(expected["payload"], ensure_ascii=False, sort_keys=True,
                                             separators=(",", ":")).encode()).hexdigest()
    key = read(project / "summary.json")["operation_id"]

    def observe(stage, artifact, required_revision):
        path = out / f"{artifact}.pyz"
        actual = json.loads(command(path, state, project / "service.sqlite"))
        tickets = [[t, k, json.loads(p), d] for t, k, p, d in actual["tickets"]]
        facts = dict(code=actual["revision"] == required_revision and
                     hashlib.sha256(path.read_bytes()).hexdigest() == versions[required_revision],
                     config=actual["config"] == expected_config,
                     data=tickets == [[task["tenant"], key, expected["payload"], scope_digest]]
                     and actual["created"] == expected["created_event_count"],
                     identity=actual["authority"] == allowed, cache=actual["effective"] == allowed)
        row = dict(stage=stage, process_healthy=actual["healthy"], facts=facts,
                   accepted=all(facts.values()), observed=actual)
        report["timeline"].append(row)
        return row["accepted"]

    stable = observe("before", "r1", "r1")
    candidate = observe("controlled-release", "r2", "r2")
    write(state / "config.json", expected_config | {"policy": "P20-A@1.0"})
    write(state / "identity.json", {"viewer": ["read", "approve"]})
    write(state / "cache.json", {})
    drift = observe("config-drift", "r2", "r2")
    write(state / "config.json", expected_config)
    write(state / "identity.json", {"viewer": allowed})
    partial = observe("partial-rollback", "r1", "r1")
    write(state / "cache.json", {})
    recovered = observe("verified-rollback", "r1", "r1")
    # Controlled dashboard input: an older sample is delivered after recovery.
    delayed = report["timeline"][2]
    report["delayed_alert"] = dict(received_after="verified-rollback", measured_at=delayed["stage"],
                                   historical_alarm=not delayed["accepted"], current_alarm=not recovered)
    cache_only = [k for k, ok in report["timeline"][-2]["facts"].items() if not ok] == ["cache"]
    passed = stable and candidate and not drift and not partial and cache_only and recovered
    report["result"] = "drill-passed" if passed else "hold"
    write(out / "release.json", report)
    return passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--fault", choices=["none", "skip-tests", "log-marker"], default="none")
    args = parser.parse_args()
    ok = run(args.output.resolve(), args.fault)
    print(read(args.output / "release.json")["result"])
    raise SystemExit(0 if ok else 1)
