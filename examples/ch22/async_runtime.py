"""Finite two-tenant DAG scheduler and local load experiment (Python 3.12)."""
import argparse
import asyncio
from collections import Counter, deque
from dataclasses import asdict, dataclass
import json
from math import ceil
from pathlib import Path
import platform
from time import perf_counter_ns


@dataclass(frozen=True)
class Job:
    name: str
    tenant: str
    dependencies: tuple
    duration_ms: int
    adapter: str


def workload(cfg):
    jobs = []
    for tenant in cfg["tenants"]:
        for i in range(cfg["tasks_per_tenant"]):
            deps = (f"{tenant}-0",) if i >= 15 else ()
            slow = tenant == "batch" and i % cfg["slow_every"] == 0
            jobs.append(Job(f"{tenant}-{i}", tenant, deps, cfg["slow_ms"] if slow else cfg["fast_ms"],
                            "lookup" if i < 15 else "format"))
    return jobs


class WorkerLost(RuntimeError):
    pass


class Endpoint:
    """Both mock adapters share the same downstream capacity in all three arms."""
    def __init__(self, slots):
        self.slots = asyncio.Semaphore(slots)
        self.inside = self.waiting = self.peak_inside = self.peak_waiting = 0

    async def call(self, job):
        self.waiting += 1
        if self.slots.locked():
            self.peak_waiting = max(self.peak_waiting, self.waiting)
        try:
            await self.slots.acquire()
        finally:
            self.waiting -= 1
        self.inside += 1
        self.peak_inside = max(self.peak_inside, self.inside)
        try:
            deadline_ns = perf_counter_ns() + job.duration_ms * 1_000_000
            while (left_ns := deadline_ns - perf_counter_ns()) > 0:
                await asyncio.sleep(left_ns / 1e9)
        finally:
            self.inside -= 1
            self.slots.release()


async def run(cfg, jobs, mode, fault=None):
    started = perf_counter_ns()
    endpoint = Endpoint(cfg["endpoint_slots"])
    adapters = {"lookup": endpoint.call, "format": endpoint.call}
    states = {job.name: "planned" for job in jobs}
    tenants = cfg["tenants"]
    queues = {t: deque() for t in tenants}
    active = {}
    occupancy, attempts = Counter(), Counter()
    trace, latency = [], {}
    peak_queue = peak_active = cursor = 0
    limit = {"serial": 1, "unbounded": len(jobs), "bounded": cfg["workers"]}[mode]
    queue_limit = cfg["ready_per_tenant"] if mode == "bounded" else len(jobs)
    per_tenant = cfg["tenant_limit"] if mode == "bounded" else limit

    def record(kind, job):
        now = (perf_counter_ns() - started) / 1e6
        trace.append(dict(kind=kind, task=job.name, tenant=job.tenant, ms=round(now, 4),
                          attempt=attempts[job.name]))
        return now

    async def execute(job):
        record("worker_enter", job)
        if job.name == "batch-0" and attempts[job.name] == 1:
            if fault == "worker_exit":
                await asyncio.sleep(0)
                raise WorkerLost()
            if fault == "cancel":
                asyncio.get_running_loop().call_soon(asyncio.current_task().cancel)
        budget = 0.001 if fault == "timeout" and job.name == "batch-0" else cfg["timeout_ms"]/1000
        async with asyncio.timeout(budget):
            await adapters[job.adapter](job)

    try:
        while any(s in {"planned", "ready", "running"} for s in states.values()):
            for job in jobs:
                if states[job.name] != "planned":
                    continue
                dep = [states[d] for d in job.dependencies]
                if any(s in {"cancelled", "timeout", "blocked"} for s in dep):
                    states[job.name] = "blocked"
                    record("blocked", job)
                elif all(s == "done" for s in dep) and len(queues[job.tenant]) < queue_limit:
                    states[job.name] = "ready"
                    queues[job.tenant].append(job)
                    record("ready", job)
            peak_queue = max(peak_queue, sum(map(len, queues.values())))
            while len(active) < limit:
                order = tenants[cursor:] + tenants[:cursor] if mode == "bounded" else tenants
                tenant = next((t for t in order if queues[t] and occupancy[t] < per_tenant), None)
                if tenant is None:
                    break
                job = queues[tenant].popleft()
                cursor = (tenants.index(tenant) + 1) % len(tenants)
                states[job.name] = "running"
                occupancy[tenant] += 1
                attempts[job.name] += 1
                record("dispatch", job)
                active[asyncio.create_task(execute(job))] = job
            peak_active = max(peak_active, len(active))
            if not active:
                if any(s in {"planned", "ready"} for s in states.values()):
                    raise ValueError("no runnable task: check DAG and quotas")
                break
            finished, _ = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
            for task in sorted(finished, key=lambda t: active[t].name):
                job = active.pop(task)
                occupancy[job.tenant] -= 1
                try:
                    task.result()
                    state = "done"
                except WorkerLost:
                    state = "planned"  # Injected once, before the read-only endpoint call.
                    record("worker_lost", job)
                except asyncio.CancelledError:
                    state = "cancelled"
                except TimeoutError:
                    state = "timeout"
                states[job.name] = state
                at = record(state, job)
                if state == "done":
                    latency[job.name] = at
    finally:
        for task in active:
            task.cancel()
        await asyncio.gather(*active, return_exceptions=True)

    elapsed = (perf_counter_ns() - started) / 1e6
    def p95(values):
        values = sorted(values)
        return round(values[ceil(0.95 * len(values))-1], 3) if values else None
    return dict(mode=mode, fault=fault, elapsed_ms=elapsed, states=dict(Counter(states.values())),
                throughput=len(latency)*1000/elapsed, p95_ms=p95(latency.values()),
                tenant_p95_ms={t:p95(latency[j.name] for j in jobs if j.tenant==t and j.name in latency)
                               for t in tenants},
                peak_ready=peak_queue, peak_active=peak_active, peak_endpoint=endpoint.peak_inside,
                peak_endpoint_wait=endpoint.peak_waiting, remaining_slots_used=endpoint.inside,
                remaining_waiters=endpoint.waiting, trace=trace)


async def main(args):
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    for key in ("tasks_per_tenant", "fast_ms", "slow_ms", "slow_every", "endpoint_slots", "workers",
                "tenant_limit", "ready_per_tenant", "timeout_ms", "repetitions"):
        if type(cfg[key]) is not int or cfg[key] < 1:
            raise ValueError(key)
    if cfg["tenants"] != ["batch", "interactive"]:
        raise ValueError("this fixture needs batch and interactive tenants")
    jobs = workload(cfg)
    rows = []
    modes = ["serial", "unbounded", "bounded"]
    for i in range(cfg["repetitions"]):
        for mode in modes[i%3:] + modes[:i%3]:
            rows.append(await run(cfg, jobs, mode))
    faults = [await run(cfg, jobs, "bounded", fault) for fault in ("worker_exit", "cancel", "timeout")]
    result = dict(python=platform.python_version(), os=platform.system(), machine=platform.machine(),
                  config=cfg, jobs=[asdict(j) for j in jobs], normal=rows, faults=faults)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    print("normal:", [r["states"] for r in rows[:3]], "faults:", [r["states"] for r in faults])
    blocked = sum("batch-0" in j.dependencies for j in jobs)
    return not (all(r["states"] == {"done":len(jobs)} for r in rows + faults[:1])
                and all(r["states"].get("blocked", 0) == blocked and r["states"].get(key) == 1
                        for r, key in zip(faults[1:], ("cancelled","timeout")))
                and all(r["remaining_slots_used"] == r["remaining_waiters"] == 0 for r in rows + faults))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("runtime_config.yaml"))
    parser.add_argument("--output", type=Path, default=Path("outputs/ch22/load.json"))
    raise SystemExit(asyncio.run(main(parser.parse_args())))
