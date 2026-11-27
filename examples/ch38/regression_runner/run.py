"""Run a local release gate against the chapter 36 engine. Candidates are controlled doubles."""
import argparse
from contextlib import closing
import hashlib
import json
from pathlib import Path
import platform
import sqlite3
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parents[1]
REF = HERE.parent / "ch36"
sys.path.insert(0, str(REF/"src"))
from book_reference.adapters import ControlledClock, FixedModel
from book_reference.contracts import Approval, SimulatedCrash
from book_reference.engine import Engine
from book_reference.storage import SessionStore, TicketService


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


BASE = {"model": "fixed-v1", "prompt": "include both policy clauses", "deadline_ms": 5000, "client": "single-send"}
RECIPES = {"baseline": BASE, "model-change": BASE | {"model":"fixed-v2"},
           "prompt-change": BASE | {"prompt":"include first policy clause"},
           "config-change": BASE | {"deadline_ms":900},
           "client-change": BASE | {"client":"repeat-after-success"}}


class ToolAdapter:
    def __init__(self, service, fault, client):
        self.client = client
        self.service, self.fault = service, fault
        self.calls = []

    def lookup(self, *args):
        self.calls.append("lookup")
        if self.fault == "lookup_timeout":
            self.fault = None
            raise TimeoutError("lookup timeout")
        return self.service.lookup(*args)

    def create(self, *args):
        self.calls.append("create")
        if self.fault == "rate_limited":
            self.fault = None
            raise TimeoutError("local quota exhausted; retry on next invocation")
        result = self.service.create(*args)
        if self.client == "repeat-after-success":
            self.calls.append("create")
            return self.service.create(*args)
        return result

    def verify(self, *args):
        self.calls.append("verify")
        actual = self.service.verify(*args)
        if self.fault == "wrong_result":
            self.fault = None
            return False
        return actual


def observe(folder):
    with closing(sqlite3.connect((folder/"service.sqlite").as_uri()+"?mode=ro", uri=True)) as db:
        tickets = [dict(tenant=t, key=k, payload=json.loads(p), approved_digest=a)
                   for t,k,p,a in db.execute("SELECT tenant,operation_id,payload_json,approved_digest FROM tickets")]
        service_counts = dict(db.execute("SELECT kind,COUNT(*) FROM service_events GROUP BY kind"))
    with closing(sqlite3.connect((folder/"session.sqlite").as_uri()+"?mode=ro", uri=True)) as db:
        trace = [dict(sequence=n,tenant=t,task_id=i,kind=k,details=json.loads(d))
                 for n,t,i,k,d in db.execute("SELECT * FROM events ORDER BY sequence")]
    return tickets, service_counts, trace


def trace_errors(trace, expected, task, rules, injected):
    errors = []
    if not trace or any(set(rules["attributes"]) - set(e) or e["tenant"] != task["tenant"]
                        or e["task_id"] != task["task_id"] for e in trace):
        errors.append("trace_attributes")
    if [e["sequence"] for e in trace] != list(range(1, len(trace)+1)):
        errors.append("trace_sequence")
    kinds = [e["kind"] for e in trace]
    suffix = iter(kinds)
    if not all(kind in suffix for kind in rules[expected["status"]]):
        errors.append("trace_order")
    if injected and injected["required"] not in kinds:
        errors.append("fault_evidence")
    return errors


def execute(folder, gold, recipe, rules, matrix):
    case = gold["id"]
    task = read(REF/"fixtures/task.json")
    policy = read(REF/"fixtures/policy.json")
    if case == "supervisor":
        task["amount"] = 350
    if case == "wrong_policy":
        task["policy_version"] = "different"
    payload = {k:task[k] for k in ("task_id","revision","amount","domestic","receipt_valid","policy_version")}
    scope = digest(payload)
    grant = None if case == "no_grant" else Approval(task["tenant"], scope, 900 if case=="expired_grant" else 4000)
    reply = read(REF/"fixtures/model_response.json")
    if case == "supervisor":
        reply["decision"] = "needs_approval"
    # One controlled model replacement differs on the supervisor slice only.
    if recipe["model"] == "fixed-v2" and case == "supervisor":
        reply["decision"] = "eligible"
    # A scripted prompt interpreter, not a claim about learned model sensitivity.
    if recipe["prompt"] == "include first policy clause":
        reply["evidence"] = reply["evidence"][:1]
    model = FixedModel(reply)
    checkpoints, calls = [], []
    pending_fault = case
    for attempt in range(2):
        with closing(SessionStore(folder/"session.sqlite")) as store, closing(TicketService(folder/"service.sqlite")) as service:
            adapter = ToolAdapter(service, pending_fault, recipe["client"])
            engine = Engine(store, adapter, model, ControlledClock(1000), policy, deadline_ms=recipe["deadline_ms"])
            hook = case if attempt == 0 and case in {"response_lost","after_commit","cancel_after_commit"} else None
            try:
                state = engine.run(task, grant, project="PRJ-3", fault=hook)
                checkpoints.append(state["status"])
            except SimulatedCrash:
                checkpoints.append("interrupted")
            calls.extend(adapter.calls)
        pending_fault = None
        if checkpoints[-1] not in {"pending","interrupted"}:
            break
    tickets, service_counts, trace = observe(folder)
    creates = service_counts.get("created", 0)
    replays = service_counts.get("replayed", 0)
    errors = []
    if calls != gold["calls"]:
        errors.append("tool_sequence")
    if replays > rules["allowed_service_replays"]:
        errors.append("unexpected_resend")
    if state["status"] != gold["status"]:
        errors.append("status")
    if gold["reason"] and state["reason"] != gold["reason"]:
        errors.append("reason")
    if len(tickets) != gold["count"] or creates != gold["count"]:
        errors.append("effect_count")
    if any(t["approved_digest"] != scope or t["payload"] != payload or t["tenant"] != task["tenant"]
           or t["key"] != f'{task["task_id"]}:{task["revision"]}:create' for t in tickets):
        errors.append("effect_scope")
    initial = trace[:-1] if case == "trace_export_loss" else trace
    initial_errors = trace_errors(initial, gold, task, rules, matrix.get(case))
    if case == "trace_export_loss" and not initial_errors:
        errors.append("lost_event_undetected")
    errors.extend(trace_errors(trace, gold, task, rules, matrix.get(case)))
    return dict(id=case, status=state["status"], reason=state["reason"], checkpoints=checkpoints,
                reply=reply, calls=calls, tickets=tickets, creates=creates, replays=replays, trace=trace,
                initial_trace_errors=initial_errors, errors=errors, passed=not errors)


def run(recipe_name):
    slices = read(HERE/"golden_slices.yaml")
    rules = read(HERE/"trace_assertions.yaml")
    matrix = read(HERE/"fault_injection_matrix.yaml")
    recipe = RECIPES[recipe_name]
    rows = []
    with TemporaryDirectory() as temp:
        for gold in slices:
            folder = Path(temp).resolve()/gold["id"]
            folder.mkdir()
            rows.append(execute(folder,gold,recipe,rules,matrix))
    inputs = [HERE/"golden_slices.yaml", HERE/"trace_assertions.yaml", HERE/"fault_injection_matrix.yaml",
              Path(__file__).resolve(), *sorted((REF/"src/book_reference").glob("*.py")),
              *(REF/"fixtures"/f for f in ("task.json","policy.json","model_response.json"))]
    manifest = {str(p.relative_to(HERE.parent.parent).as_posix()):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in inputs}
    return dict(schema="book-gate-1", recipe=recipe_name, config=recipe, config_digest=digest(recipe),
                inputs=manifest, python=platform.python_version(), sqlite=sqlite3.sqlite_version,
                exceptions=[], rows=rows, decision="pass" if all(r["passed"] for r in rows) else "hold")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=RECIPES, default="baseline")
    parser.add_argument("--output", type=Path, default=Path("outputs/ch38/gate.json"))
    args = parser.parse_args()
    result = run(args.candidate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(result["decision"], [r["id"] for r in result["rows"] if not r["passed"]])
    raise SystemExit(int(result["decision"] != "pass"))
