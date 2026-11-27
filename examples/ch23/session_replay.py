"""Read-only session replay, compared with a transcript-only reconnect policy."""
import argparse
from contextlib import closing
from dataclasses import asdict, dataclass, replace
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from time import perf_counter_ns

HERE = Path(__file__).resolve().parent
REF = HERE.parent / "ch36"
sys.path.insert(0, str(REF / "src"))
from book_reference.contracts import Approval, digest, payload_for
from book_reference.storage import TicketService

TRANSITIONS = json.loads((HERE / "session_state_machine.yaml").read_text())
SCHEMA = json.loads((HERE / "event_schema.json").read_text())
PROFILES = ("completed", "cancelled", "failed")
FAULTS = ("clean", "duplicate_first", "duplicate_middle", "duplicate_end", "missing_first",
          "missing_middle", "missing_end", "reverse", "swap_first", "swap_last", "empty_wire",
          "old_snapshot", "ahead_snapshot", "wrong_session_snapshot", "bad_snapshot_digest",
          "future_version", "legacy_version", "foreign_event", "changed_payload", "changed_id")


@dataclass(frozen=True)
class View:
    session_id: str
    sequence: int = 0
    status: str = "empty"
    operation_id: str | None = None
    ticket_id: int | None = None


def normalize(event):
    event = dict(event)
    if type(event.get("schema_version")) is not int:
        raise ValueError("invalid version")
    if event["schema_version"] == 0 and "seq" in event and "sequence" not in event:
        event["sequence"] = event.pop("seq")
        event["schema_version"] = 1
    if event["schema_version"] != 1 or set(event) != set(SCHEMA["required"]):
        raise ValueError("unsupported envelope")
    for key in ("session_id", "turn_id", "event_id"):
        if not isinstance(event[key], str) or not event[key]:
            raise ValueError(key)
    for key, lower in (("sequence", 1), ("occurred_ms", 0)):
        if type(event[key]) is not int or event[key] < lower:
            raise ValueError(key)
    if event["kind"] not in SCHEMA["properties"]["kind"]["enum"]:
        raise ValueError("kind")
    if event["operation_id"] is not None and not isinstance(event["operation_id"], str):
        raise ValueError("operation_id")
    ticket = event["ticket_id"]
    if ticket is not None and (type(ticket) is not int or ticket < 1):
        raise ValueError("ticket_id")
    return event


def reduce_event(view, raw):
    event = normalize(raw)
    if (event["session_id"], event["sequence"]) != (view.session_id, view.sequence + 1):
        raise ValueError("cursor")
    status = TRANSITIONS[view.status].get(event["kind"])
    if status is None:
        raise ValueError("illegal transition")
    return View(view.session_id, event["sequence"], status,
                event["operation_id"] or view.operation_id, event["ticket_id"] or view.ticket_id)


def configure_journal(db):
    db.execute("CREATE TABLE checkpoints(s TEXT, n INTEGER, body TEXT, checksum TEXT, PRIMARY KEY(s,n))")
    db.execute("CREATE TABLE journal(s TEXT, n INTEGER, body TEXT, PRIMARY KEY(s,n))")


def make_session(db, service, profile):
    task = json.loads((REF / "fixtures/task.json").read_text())
    task["task_id"] += "-" + profile
    payload = payload_for(task)
    op = f'{task["task_id"]}:{task["revision"]}:create'
    grant = Approval(task["tenant"], digest(payload), 4000)
    ticket = None
    kinds = ["opened", "started", "paused", "resumed", profile]
    events = []
    projection = View(profile)
    for index, kind in enumerate(kinds, 1):
        if kind == "completed":
            ticket = service.create(task["tenant"], op, payload, grant, 1000)
        event = dict(session_id=profile, turn_id="turn-1", sequence=index, event_id=f"{profile}-{index}",
                     occurred_ms=1000 + index, schema_version=1, kind=kind,
                     operation_id=op if index >= 4 else None, ticket_id=ticket)
        projection = reduce_event(projection, event)
        with db:
            if index <= 2:
                body = asdict(projection)
                db.execute("INSERT INTO checkpoints VALUES(?,?,?,?)",
                           (profile, index, json.dumps(body), digest(body)))
            db.execute("INSERT INTO journal VALUES(?,?,?)", (profile, index, json.dumps(event)))
        events.append(event)
    return events, task, payload, grant, op


def repair(db, session, snapshot, claimed_hash, wire):
    # The checkpoint is server-issued. The trusted digest is separate from the client copy.
    count = db.execute("SELECT COUNT(*) FROM journal WHERE s=?", (session,)).fetchone()[0]
    notes = []
    if (digest(asdict(snapshot)) != claimed_hash or snapshot.session_id != session
            or not 0 <= snapshot.sequence <= count):
        snapshot = View(session)
        notes.append("reset_snapshot")
    view = snapshot
    for raw in wire:
        try:
            event = normalize(raw)
        except ValueError:
            notes.append("reject_version_or_fields")
            continue
        if event["session_id"] != session:
            notes.append("reject_foreign")
            continue
        stored = db.execute("SELECT body FROM journal WHERE s=? AND n=?",
                            (session, event["sequence"])).fetchone()
        if stored is None or json.loads(stored[0]) != event:
            notes.append("reject_conflict")
            continue
        if event["sequence"] <= view.sequence:
            notes.append("duplicate")
        elif event["sequence"] == view.sequence + 1:
            view = reduce_event(view, event)
        else:
            notes.append("gap")
    for (body,) in db.execute("SELECT body FROM journal WHERE s=? AND n>? ORDER BY n",
                              (session, view.sequence)):
        view = reduce_event(view, json.loads(body))
        notes.append("backfill")
    return view, notes


def run_case(db, session, events, fault):
    cursor = 1 if fault == "old_snapshot" else 2
    body, trusted = db.execute("SELECT body,checksum FROM checkpoints WHERE s=? AND n=?",
                               (session, cursor)).fetchone()
    snap = View(**json.loads(body))
    wire = list(events[2:])
    if fault in {"duplicate_first", "duplicate_middle", "duplicate_end"}:
        i = ("duplicate_first", "duplicate_middle", "duplicate_end").index(fault)
        wire.insert(i, wire[i])
    elif fault.startswith("missing_"):
        del wire[("missing_first", "missing_middle", "missing_end").index(fault)]
    elif fault == "reverse":
        wire.reverse()
    elif fault == "swap_first":
        wire[0], wire[1] = wire[1], wire[0]
    elif fault == "swap_last":
        wire[1], wire[2] = wire[2], wire[1]
    elif fault == "empty_wire":
        wire = []
    elif fault == "ahead_snapshot":
        snap = replace(snap, sequence=99)
    elif fault == "wrong_session_snapshot":
        snap = replace(snap, session_id="other")
    elif fault == "bad_snapshot_digest":
        snap = replace(snap, status="completed")
    elif fault == "future_version":
        wire[0] = wire[0] | {"schema_version": 2}
    elif fault == "legacy_version":
        v0 = dict(wire[0], schema_version=0)
        v0["seq"] = v0.pop("sequence")
        wire[0] = v0
    elif fault == "foreign_event":
        wire[0] = wire[0] | {"session_id": "other"}
    elif fault == "changed_payload":
        wire[0] = wire[0] | {"ticket_id": 999}
    elif fault == "changed_id":
        wire[0] = wire[0] | {"event_id": "reused"}
    start = perf_counter_ns()
    view, notes = repair(db, session, snap, trusted, wire)
    return dict(variant=fault, received=wire, snapshot=asdict(snap), result=asdict(view),
                elapsed_us=(perf_counter_ns() - start) / 1000, actions=notes)


def counts(db):
    return tuple(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                 for table in ("tickets", "service_events"))


def experiment(folder):
    records, sessions = [], {}
    for profile in PROFILES:
        source = folder / (profile + ".sqlite")
        target = folder / (profile + "-tickets.sqlite")
        with closing(sqlite3.connect(source)) as db, closing(TicketService(target)) as service:
            configure_journal(db)
            events, task, payload, grant, op = make_session(db, service, profile)
        sessions[profile] = events
        # Reopen after disconnect. Replay has no writable handle to either database.
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db, closing(
            sqlite3.connect(target.as_uri() + "?mode=ro", uri=True)
        ) as observer:
            before = counts(observer)
            expected = View(profile)
            for event in events:
                expected = reduce_event(expected, event)
            for fault in FAULTS:
                row = run_case(db, profile, events, fault)
                row.update(profile=profile, before=before, after=counts(observer))
                row["passed"] = (row["result"] == asdict(expected) and expected.status == profile
                                 and expected.ticket_id == (1 if profile == "completed" else None)
                                 and before == row["after"] == (int(profile == "completed"),) * 2)
                records.append(row)
        if profile == "completed":
            # Counterfactual: same visible transcript, fresh write key after reconnect.
            with closing(TicketService(target)) as service:
                ticket = service.create(task["tenant"], op, payload, grant, 1001)
                same_key = dict(ticket_id=ticket, counts=counts(service.db))
                prior = counts(service.db)
                service.create(task["tenant"], op + "-retry", payload, grant, 1002)
                transcript_only = dict(chat="请求已收到", before=prior, after=counts(service.db))
    return dict(sessions=sessions, cases=records, same_key_retry=same_key, transcript_only=transcript_only)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch23/replay.json"))
    args = parser.parse_args()
    with TemporaryDirectory() as temp:
        report = experiment(Path(temp).resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    passed = sum(case["passed"] for case in report["cases"])
    print(f"replay {passed}/60; transcript-only tickets {report['transcript_only']['after'][0]}")
    raise SystemExit(int(passed != 60 or report["transcript_only"]["after"] != (2, 3)
                         or report["same_key_retry"]["counts"] != (1, 2)))
