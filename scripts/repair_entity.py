#!/usr/bin/env python
"""Undo what a rehearsal did to an entity that already existed.

`reset_rehearsal.py` deletes the records a call produced. That is the whole
story for stories, facts and conversations, which are created by the call and
belong to it. It is not the story for entities: a call that mentions someone
already in the graph *mutates* that entity in place -- appends to `detail`,
appends to `aliases`, increments `mention_count` -- and deleting the call
leaves every one of those edits behind. Nothing in the reset path reverts them,
because there is nothing to delete.

The damage compounds. A new person whose role matches an existing one is
resolved onto that entity and their name is kept as an alias; from then on the
same name matches by alias immediately, so the first wrong merge makes itself
permanent and every later take confirms it. `corrections.py` says a wrong merge
is unrecoverable and a wrong split is one click. This is the unrecoverable one,
arrived at automatically.

    python scripts/repair_entity.py ent_abc123                      # show it
    python scripts/repair_entity.py ent_abc123 --drop-alias "Mrs. Rajan" \
        --truncate-detail "Came to the door at the end of the conversation." \
        --mentions 4 --commit

Backs up the whole document before writing, always.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import UTC, datetime

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("entity_id")
    ap.add_argument("--narrator", default="ah_khim")
    ap.add_argument(
        "--drop-alias", action="append", default=[], help="alias to remove (repeatable)"
    )
    ap.add_argument(
        "--truncate-detail",
        help="keep detail up to and including this text; drop the rest",
    )
    ap.add_argument("--mentions", type=int, help="restore mention_count to this")
    ap.add_argument("--commit", action="store_true")
    return ap.parse_args()


def main() -> int:
    for line in pathlib.Path(".env").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

    from google.cloud import firestore

    args = parse_args()
    db = firestore.Client()
    ref = db.collection(f"entities__{args.narrator}").document(args.entity_id)
    before = ref.get().to_dict()
    if before is None:
        print(f"No such entity: {args.entity_id}")
        return 1

    after = dict(before)

    if args.drop_alias:
        # Case-insensitive: the same name comes back capitalised differently
        # between takes, and a repair that missed "mrs. rajan" because it was
        # asked to drop "Mrs. Rajan" would look like it had worked.
        drop = {a.strip().lower() for a in args.drop_alias}
        after["aliases"] = [
            a for a in (before.get("aliases") or []) if a.strip().lower() not in drop
        ]

    if args.truncate_detail:
        detail = before.get("detail") or ""
        cut = detail.find(args.truncate_detail)
        if cut == -1:
            print("--truncate-detail text not found in detail; leaving it alone")
        else:
            after["detail"] = detail[: cut + len(args.truncate_detail)].strip()

    if args.mentions is not None:
        after["mention_count"] = args.mentions

    print("BEFORE")
    for field in ("detail", "aliases", "mention_count"):
        print(f"  {field:14}", json.dumps(before.get(field), default=str)[:300])
    print("AFTER")
    for field in ("detail", "aliases", "mention_count"):
        changed = "*" if after.get(field) != before.get(field) else " "
        print(f" {changed}{field:14}", json.dumps(after.get(field), default=str)[:300])

    if after == before:
        print("\nNothing would change.")
        return 0
    if not args.commit:
        print("\nDry run. Re-run with --commit.")
        return 0

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    backup = pathlib.Path(f"/tmp/sampan_entity_{args.entity_id}_{stamp}.json")
    backup.write_text(json.dumps(before, indent=1, default=str))
    print(f"\nbacked up to {backup}")

    ref.set(after)
    print(f"repaired {args.entity_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
