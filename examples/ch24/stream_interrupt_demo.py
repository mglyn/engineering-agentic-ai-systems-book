"""Replay forty controlled stop schedules against three local stream consumers."""
import argparse
import asyncio
from dataclasses import asdict, dataclass
from itertools import product
import json
from pathlib import Path
from time import perf_counter_ns

PHASES = ("before_start", "full_queue", "in_flight", "after_commit", "after_complete")
MODES = ("ui_only", "propagate", "fenced")
OLD = ("turn-1", 1)
NEW = ("turn-2", 2)


@dataclass(frozen=True)
class Frame:
    turn_id: str
    generation: int
    sequence: int
    value: str

    @property
    def owner(self):
        return self.turn_id, self.generation


def metrics(events):
    stop = next(i for i, event in enumerate(events) if event["kind"] == "user_stop")
    origin = events[stop]["us"]

    def offset(kind):
        event = next((e for e in events if e["kind"] == kind), None)
        return event["us"] - origin if event is not None else None

    late = [e for e in events[stop:] if e["kind"] == "present"
            and (e["turn_id"], e["generation"]) == OLD]
    return dict(ui_ack_us=offset("ui_ack"), cancel_sent_us=offset("cancel_sent"),
                cancel_received_us=offset("cancel_received"), producer_exit_us=offset("producer_exit"),
                producer_joined_us=offset("producer_joined"), last_old_us=late[-1]["us"] - origin if late else None,
                old_count=len(late), cleared=sum(e["kind"] == "cleared" for e in events),
                rejected_at_sink=sum(e["kind"] == "obsolete" for e in events))


async def trial(phase, capacity, medium, repeat, mode):
    start = perf_counter_ns()
    events = []
    queue = asyncio.Queue(maxsize=capacity)
    high_water = asyncio.Event()
    accepted = OLD
    receipt_store = {}
    visible = []
    parked = []
    stopped = False

    def log(kind, **fields):
        events.append(dict(us=(perf_counter_ns() - start) // 1000, kind=kind, **fields))

    def present(frame):
        if mode == "fenced" and frame.owner != accepted:
            log("obsolete", **asdict(frame))
            return
        visible.append(frame)
        log("present", **asdict(frame))

    def take():
        frame = queue.get_nowait()
        log("dequeued", **asdict(frame), depth=queue.qsize())
        return frame

    async def produce():
        try:
            for i in range(capacity + 2):
                frame = Frame(*OLD, i, f"{medium}-{i}")
                log("produced", **asdict(frame))
                if queue.full():
                    high_water.set()
                await queue.put(frame)
                log("enqueued", **asdict(frame), depth=queue.qsize())
        except asyncio.CancelledError:
            log("cancel_received")
            raise
        finally:
            log("producer_exit")

    async def drain_while_producing():
        while not producer.done():
            if not queue.empty():
                present(take())
            await asyncio.sleep(0)

    producer = asyncio.create_task(produce())
    if phase != "before_start":
        await high_water.wait()
    if phase == "in_flight":
        parked.append(take())
    if phase == "after_complete":
        await drain_while_producing()
        while not queue.empty():
            present(take())
    if phase == "after_commit":
        receipt_store["T-DEMO-01:1:create"] = "ticket-1"
        log("tool_committed", operation_id="T-DEMO-01:1:create")

    def stop():
        nonlocal accepted, stopped
        log("user_stop", turn_id=OLD[0], generation=OLD[1])
        if stopped:
            log("duplicate_stop")
            return
        stopped = True
        log("ui_ack")
        if mode == "fenced":
            accepted = NEW
        if mode != "ui_only":
            delivered = producer.cancel()
            log("cancel_sent", task_accepted_request=delivered)
        if mode == "fenced":
            while not queue.empty():
                log("cleared", **asdict(queue.get_nowait()))

    stop()
    if repeat:
        stop()
    if mode == "ui_only":
        await drain_while_producing()
    try:
        await producer
    except asyncio.CancelledError:
        pass
    log("producer_joined")
    while not queue.empty():
        present(take())
    for frame in parked:
        present(frame)
    if receipt_store:
        log("receipt_recorded", operation_id=next(iter(receipt_store)))
        present(Frame(*OLD, capacity + 2, "old-receipt"))
    new_frame = Frame(*NEW, 0, "new-turn")
    present(new_frame)

    expected = {
        "before_start": capacity + 2 if mode == "ui_only" else 0,
        "full_queue": capacity + 2 if mode == "ui_only" else capacity,
        "in_flight": capacity + 2 if mode == "ui_only" else capacity,
        "after_commit": capacity + 3 if mode == "ui_only" else capacity + 1,
        "after_complete": 0,
    }[phase] if mode != "fenced" else 0
    observed = metrics(events)
    checks = dict(old_count=expected == observed["old_count"], new_frame=visible.count(new_frame) == 1,
                  resources=producer.done() and queue.empty(),
                  receipt=len(receipt_store) == int(phase == "after_commit"))
    return dict(phase=phase, capacity=capacity, medium=medium, repeated_stop=repeat,
                mode=mode, events=events, high_water_reached=high_water.is_set(),
                expected_old=expected, actual_old=observed["old_count"],
                old_tail_us=observed["last_old_us"] or 0, measurements=observed, checks=checks,
                errors=[key for key, ok in checks.items() if not ok], passed=all(checks.values()))


async def main(output):
    output.parent.mkdir(parents=True, exist_ok=True)
    failed = 0
    with output.open("w", encoding="utf-8") as sink:
        for args in product(PHASES, (1, 4), ("text", "audio-block"), (False, True), MODES):
            row = await asyncio.wait_for(trial(*args), timeout=5)
            sink.write(json.dumps(row) + "\n")
            failed += not row["passed"]
    print(f"40 schedules x 3 policies; failed={failed}")
    return bool(failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch24/interrupt_timeline.jsonl"))
    raise SystemExit(asyncio.run(main(parser.parse_args().output)))
