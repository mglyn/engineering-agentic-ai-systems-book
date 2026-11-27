"""Measure producer wakeups at two low watermarks on the same bounded queue."""
import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter_ns


async def measure(high, low, count, work_ms):
    queue = asyncio.Queue(maxsize=high)
    refill = asyncio.Event()
    events = []
    origin = perf_counter_ns()
    output = []

    def log(kind, **fields):
        events.append(dict(kind=kind, us=(perf_counter_ns() - origin) // 1000,
                           depth=queue.qsize(), **fields))

    async def produce():
        for sequence in range(count):
            if queue.qsize() >= high:
                refill.clear()
                log("pause")
                await refill.wait()
                log("resume")
            queue.put_nowait(sequence)
            log("put", sequence=sequence)

    async def consume():
        for _ in range(count):
            sequence = await queue.get()
            if queue.qsize() <= low:
                refill.set()
            log("take", sequence=sequence)
            await asyncio.sleep(work_ms / 1000)
            output.append(sequence)
            log("present", sequence=sequence)

    async with asyncio.TaskGroup() as group:
        group.create_task(produce())
        group.create_task(consume())
    return dict(high=high, low=low, count=count, requested_service_ms=work_ms, events=events,
                peak=max(e["depth"] for e in events), pauses=sum(e["kind"] == "pause" for e in events),
                elapsed_us=events[-1]["us"], complete=output == list(range(count)))


async def run():
    return [await measure(4, low, 24, 2) for low in (3, 1)]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("outputs/ch24/watermarks.json"))
    args = parser.parse_args()
    rows = asyncio.run(run())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print([(r["low"], r["pauses"], r["complete"]) for r in rows])
    raise SystemExit(int(not all(r["peak"] <= r["high"] and r["complete"] for r in rows)))
