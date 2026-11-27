"""Deliver a stale stop and a committed receipt after switching the active stream."""
import argparse
import asyncio
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory

from stream_interrupt_demo import Frame

REFERENCE = Path(__file__).resolve().parents[1] / "ch36"
sys.path.insert(0, str(REFERENCE / "src"))
from book_reference.contracts import Approval, digest, payload_for
from book_reference.storage import TicketService


def matches(rule, target, current):
    if rule == "session":
        return True
    if rule == "turn":
        return target[0] == current[0]
    if rule == "generation":
        return target[1] == current[1]
    return target == current


async def trial(directory, successor, rule):
    task = json.loads((REFERENCE / "fixtures/task.json").read_text(encoding="utf-8"))
    payload = payload_for(task)
    grant = Approval(task["tenant"], digest(payload), 4000)
    operation = f'{task["task_id"]}:{task["revision"]}:create'
    old = ("turn-1", 1)
    current = ("turn-2", 1) if successor == "next_turn" else ("turn-1", 2)
    committed = asyncio.Event()
    release_receipt = asyncio.Event()
    database = directory / "service.sqlite"
    trace = []

    async def send():
        with closing(TicketService(database)) as service:
            ticket = service.create(task["tenant"], operation, payload, grant, 1000)
        trace.append(dict(event="service_commit", operation=operation, ticket=ticket))
        committed.set()
        await release_receipt.wait()
        return Frame(*old, 0, f"ticket-{ticket}")

    pending = asyncio.create_task(send())
    # A service failure must surface even if the commit event was never set.
    try:
        await asyncio.wait_for(committed.wait(), timeout=5)
        trace.append(dict(event="switch_owner", current=current))
        stopped_new = matches(rule, old, current)
        trace.append(dict(event="delayed_stop", target=old, applied=stopped_new))
    finally:
        release_receipt.set()
        receipt = await pending

    # Updating the operation ledger and rendering its notification have separate predicates.
    receipt_visible = matches(rule, receipt.owner, current)
    trace.append(dict(event="receipt_arrived", owner=receipt.owner, recorded=operation, visible=receipt_visible))
    visible = []
    if receipt_visible:
        visible.append(receipt.value)
    if not stopped_new:
        visible.append("new-output")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        tickets = db.execute("SELECT tenant, operation_id, payload_json, approved_digest FROM tickets").fetchall()
        creates = db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]
    expected = json.loads((REFERENCE / "fixtures/expected.json").read_text(encoding="utf-8"))["payload"]
    business_ok = len(tickets) == 1 and creates == 1 and (
        tickets[0][0] == task["tenant"] and tickets[0][1] == operation and
        json.loads(tickets[0][2]) == expected and tickets[0][3] == digest(expected))
    return dict(successor=successor, rule=rule, trace=trace, visible=visible,
                ticket_count=len(tickets), created_count=creates, business_ok=business_ok,
                late_stop_ignored=not stopped_new, old_receipt_hidden=not receipt_visible,
                passed=business_ok and visible == ["new-output"])


async def run():
    rows = []
    with TemporaryDirectory() as temp:
        for successor in ("next_turn", "retry_same_turn"):
            for rule in ("session", "turn", "generation", "pair"):
                folder = Path(temp) / successor / rule
                folder.mkdir(parents=True)
                rows.append(await trial(folder, successor, rule))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch24/late_receipt.json"))
    args = parser.parse_args()
    rows = asyncio.run(run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    expected = {("next_turn", "turn"), ("next_turn", "pair"),
                ("retry_same_turn", "generation"), ("retry_same_turn", "pair")}
    actual = {(r["successor"], r["rule"]) for r in rows if r["passed"]}
    print(f"{len(rows)} cases; correct UI and business state in {len(actual)}")
    raise SystemExit(int(actual != expected or not all(r["business_ok"] for r in rows)))
