"""A local producer, a controlled consumer and a delayed tool receipt.
Run from repository root: python examples/ch24/stream_interrupt_demo.py
"""
import argparse
import asyncio
from itertools import product
import json
from pathlib import Path
from time import perf_counter_ns

PHASES = ("before_start", "full_queue", "in_flight", "after_commit", "after_complete")
MODES = ("ui_only", "propagate", "fenced")


async def trial(phase, capacity, medium, repeat, mode):
    start = perf_counter_ns()
    events = []
    queue = asyncio.Queue(maxsize=capacity)
    ready = asyncio.Event()
    accepted = 1
    receipt_store = {}
    visible = []
    parked = []
    paused_at_high = False
    stopped = False

    def log(kind, **fields):
        events.append(dict(us=(perf_counter_ns() - start) // 1000, kind=kind, **fields))

    def present(frame):
        generation, value = frame
        if mode == "fenced" and generation != accepted:
            log("obsolete", generation=generation, value=value)
            return
        visible.append(frame)
        log("present", generation=generation, value=value)

    async def produce():
        nonlocal paused_at_high
        try:
            for i in range(capacity + 2):
                if queue.full():
                    paused_at_high = True
                    ready.set()
                await queue.put((1, f"{medium}-{i}"))
                log("enqueued", depth=queue.qsize())
        finally:
            log("producer_exit")

    async def drain():
        while not producer.done() or not queue.empty():
            if not queue.empty():
                present(await queue.get())
            await asyncio.sleep(0)

    # No yield before before_start: cancellation can precede coroutine entry.
    producer = asyncio.create_task(produce())
    if phase != "before_start":
        await ready.wait()
    if phase == "in_flight":
        parked.append(await queue.get())
    if phase == "after_complete":
        await drain()
    if phase == "after_commit":
        receipt_store["T-DEMO-01:1:create"] = "ticket-1"
        log("tool_committed")

    def stop():
        nonlocal accepted, stopped
        log("user_stop")
        if stopped:
            log("duplicate_stop")
            return
        stopped = True
        log("ui_ack")
        if mode != "ui_only":
            producer.cancel()
            log("cancel_sent")
        if mode == "fenced":
            accepted += 1
            while not queue.empty():
                queue.get_nowait()
                log("cleared")

    stop()
    if repeat:
        stop()
    if mode == "ui_only":
        await drain()
    else:
        try:
            await producer
        except asyncio.CancelledError:
            pass
        while not queue.empty():
            present(await queue.get())
    log("producer_joined")
    for frame in parked:
        present(frame)
    if receipt_store:
        log("receipt_recorded", operation_id=next(iter(receipt_store)))
        present((1, "old-receipt"))
    present((2, "new-turn"))
    stop_idx = next(i for i, e in enumerate(events) if e["kind"] == "user_stop")
    residual = [e for e in events[stop_idx:] if e["kind"] == "present" and e["generation"] == 1]
    expected = {
        "before_start": capacity + 2 if mode == "ui_only" else 0,
        "full_queue": capacity + 2 if mode == "ui_only" else capacity,
        "in_flight": capacity + 2 if mode == "ui_only" else capacity,
        "after_commit": capacity + 3 if mode == "ui_only" else capacity + 1,
        "after_complete": 0,
    }[phase] if mode != "fenced" else 0
    return dict(phase=phase, capacity=capacity, medium=medium, repeated_stop=repeat,
                mode=mode, events=events, high_water_reached=paused_at_high,
                expected_old=expected, actual_old=len(residual),
                old_tail_us=residual[-1]["us"] - events[stop_idx]["us"] if residual else 0,
                passed=(expected == len(residual) and visible.count((2, "new-turn")) == 1
                        and producer.done() and queue.empty()
                        and len(receipt_store) == int(phase == "after_commit")))


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
