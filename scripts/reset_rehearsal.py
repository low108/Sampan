#!/usr/bin/env python
"""Undo a rehearsal call, so the next take starts from the same place.

A rehearsal call is a real call: local and Cloud Run share one Firestore
database, so a take you would rather forget leaves a conversation, whatever
was extracted from it, and a session count that no longer matches the story
you are about to tell on camera.

Removes everything one or more calls produced, and puts back the questions
they consumed so the next call opens the same way. Backs up first, always,
and refuses to delete anything it could not back up.

    python scripts/reset_rehearsal.py --today            # dry run
    python scripts/reset_rehearsal.py --today --commit
    python scripts/reset_rehearsal.py --since 2026-08-26T13:40 --commit
    python scripts/reset_rehearsal.py --conv conv_ah_khim_2026… --commit

Deliberately not a Firestore query: the derived records are found by matching
the conversation id inside each document, because a story keys off a story_id
prefix rather than an episode_id field, and searching only the obvious field
is how a stale card was left sitting in the unplaced tray after its
conversation had been deleted.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DERIVED = (
    "conversations__{n}",
    "stories__{n}",
    "facts__{n}",
    "entities__{n}",
    "concerns__{n}",
    "memories__{n}",
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--narrator", default="ah_khim")
    ap.add_argument("--today", action="store_true", help="every call from today")
    ap.add_argument("--since", help="ISO instant, e.g. 2026-08-26T13:40")
    ap.add_argument("--conv", action="append", default=[], help="a conversation id")
    ap.add_argument(
        "--baseline-sessions",
        type=int,
        help="session_count to restore; default is current minus calls removed",
    )
    ap.add_argument("--commit", action="store_true", help="actually delete")
    return ap.parse_args()


def targets(db: Any, narrator: str, args: argparse.Namespace) -> set[str]:
    wanted = set(args.conv)
    if args.today:
        args.since = datetime.now(UTC).strftime("%Y-%m-%d")
    if args.since:
        for doc in db.collection(f"conversations__{narrator}").stream():
            when = doc.to_dict().get("occurred_at") or ""
            if when >= args.since:
                wanted.add(doc.id)
    return wanted


def main() -> int:
    from google.cloud import firestore

    args = parse_args()
    db = firestore.Client()
    narrator = args.narrator

    convs = targets(db, narrator, args)
    if not convs:
        print("Nothing matched. Archive untouched.")
        return 0

    print(f"calls to remove ({len(convs)}):")
    for c in sorted(convs):
        print("  ", c)

    found: dict[str, list[dict[str, Any]]] = {}
    for pattern in DERIVED:
        name = pattern.format(n=narrator)
        rows = []
        for doc in db.collection(name).stream():
            blob = json.dumps(doc.to_dict(), default=str)
            if any(c in blob or c in doc.id for c in convs):
                rows.append({"_id": doc.id, **doc.to_dict()})
        if rows:
            found[name] = rows

    # Any question these calls consumed goes back in the queue, matched on
    # when it was delivered rather than on which call took it -- the ask does
    # not record that, and a first attempt that tried to infer it from the
    # conversation id found nothing while a question sat delivered.
    cutoff = args.since or min(convs)
    asks = [
        {"_id": d.id, **d.to_dict()}
        for d in db.collection(f"asks__{narrator}").stream()
        if d.to_dict().get("delivered")
        and (d.to_dict().get("delivered_at") or "") >= cutoff
    ]
    profile = db.collection("profiles").document(narrator).get().to_dict() or {}

    print("\nwould remove:")
    for name, rows in found.items():
        print(f"  {name}: {len(rows)}")
        for r in rows:
            label = (
                r.get("title") or r.get("statement") or r.get("canonical_name") or ""
            )
            print(f"      {str(label)[:56] or r['_id'][:56]}")
    print(f"  asks to re-queue: {len(asks)}")
    threads = [
        t
        for t in profile.get("threads", [])
        if t.get("opened_in") in convs or t.get("last_touched") in convs
    ]
    print(f"  threads to drop : {len(threads)}")
    sessions = args.baseline_sessions
    if sessions is None:
        sessions = max(0, (profile.get("session_count") or 0) - len(convs))
    print(f"  session_count   : {profile.get('session_count')} -> {sessions}")

    if not args.commit:
        print("\nDry run. Re-run with --commit to apply.")
        return 0

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    backup = Path(f"/tmp/sampan_reset_{stamp}.json")
    backup.write_text(
        json.dumps(
            {
                "conversations": sorted(convs),
                "derived": found,
                "asks": asks,
                "profile": profile,
            },
            indent=1,
            default=str,
        )
    )
    print(f"\nbacked up to {backup}")

    for name, rows in found.items():
        for r in rows:
            db.collection(name).document(r["_id"]).delete()
            print(f"deleted {name.split('__')[0]:14} {r['_id'][:48]}")

    for a in asks:
        # `chosen` as well as `delivered`: a call consumes the question it was
        # about to ask, so restoring it without putting it back at the front
        # means the next take opens on a different one. Delivery clears the
        # flag, so there is nothing to restore -- it is set, not remembered.
        db.collection(f"asks__{narrator}").document(a["_id"]).update(
            {"delivered": False, "delivered_at": firestore.DELETE_FIELD, "chosen": True}
        )
        print(f"re-queued ask  {(a.get('question') or '')[:48]}  (goes first)")

    # Only one question can be first.
    for d in db.collection(f"asks__{narrator}").stream():
        row = d.to_dict()
        if row.get("chosen") and d.id not in {a["_id"] for a in asks}:
            db.collection(f"asks__{narrator}").document(d.id).update({"chosen": False})

    keep = [t for t in profile.get("threads", []) if t not in threads]
    db.collection("profiles").document(narrator).update(
        {"threads": keep, "session_count": sessions, "last_closure": None}
    )
    print(
        f"profile        session_count -> {sessions}, {len(threads)} thread(s) dropped"
    )
    print("\nDone. Check the tray and the map before the next take.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
