"""Read-only release acceptance client. Both revisions use the same wire format."""
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from revision import VERSION


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def observe(state, database):
    config = read(state / "config.json")
    grants = read(state / "identity.json")
    cache = read(state / "cache.json")
    # Deliberate defect under study: the external cache survives process restarts.
    if "viewer" not in cache:
        cache["viewer"] = grants["viewer"]
        (state / "cache.json").write_text(json.dumps(cache), encoding="utf-8")
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        tickets = db.execute(
            "SELECT tenant, operation_id, payload_json, approved_digest FROM tickets ORDER BY ticket_id"
        ).fetchall()
        created = db.execute("SELECT count(*) FROM service_events WHERE kind='created'").fetchone()[0]
    return dict(revision=VERSION, healthy=True, config=config, authority=grants["viewer"],
                effective=cache["viewer"], tickets=tickets, created=created)


if __name__ == "__main__":
    print(json.dumps(observe(Path(sys.argv[1]), Path(sys.argv[2]))))
