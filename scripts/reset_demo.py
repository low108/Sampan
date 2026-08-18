"""Put the archive back to its demo-ready state.

Testing the voice loop consumes the very things the demo is built to show. A
single four-turn call re-queues nothing, marks Wei Lun's question delivered,
empties the bell and leaves a stray conversation in her history -- and the next
time you open the app it all looks broken when it is merely spent.

This restores the starting position without touching her stories:

  * Wei Lun's question goes back in the queue, undelivered.
  * Every "seen" marker is cleared, so the bells show their badges again.
  * Conversations recorded after the seed are listed, and removed only with
    --drop-test-calls, because a real recording is not something to delete on
    a script's own initiative.

    uv run python scripts/reset_demo.py            # show what would change
    uv run python scripts/reset_demo.py --apply
    uv run python scripts/reset_demo.py --apply --drop-test-calls
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from google.cloud import firestore

from sampan.config import Settings

# The four seeded conversations. Anything else in her history arrived from a
# real call into the microphone.
SEEDED_PREFIXES = (
    "conv_ah_khim_20260817",
    "conv_wei_lun_20260817",
)


def _db(settings: Settings) -> Any:
    return firestore.Client(
        project=settings.project_id, database=settings.firestore_database
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="write the changes (default: dry run)"
    )
    parser.add_argument(
        "--drop-test-calls",
        action="store_true",
        help="also delete conversations recorded after the seed",
    )
    args = parser.parse_args()

    settings = Settings()
    if not settings.configured:
        print("No GOOGLE_CLOUD_PROJECT configured.", file=sys.stderr)
        return 1

    db = _db(settings)
    dry = not args.apply
    label = "would" if dry else ""

    # 1. Re-arm every delivered question.
    rearmed = 0
    for collection in db.collections():
        if not collection.id.startswith("asks__"):
            continue
        for doc in collection.stream():
            raw = doc.to_dict() or {}
            if not raw.get("delivered"):
                continue
            print(f'  {label} re-arm  "{str(raw.get("question"))[:58]}"')
            if not dry:
                doc.reference.update({"delivered": False, "delivered_at": None})
            rearmed += 1

    # 2. Clear seen markers so the bells carry their badges again.
    cleared = 0
    for collection in db.collections():
        if "seen" not in collection.id:
            continue
        for doc in collection.stream():
            if not dry:
                doc.reference.delete()
            cleared += 1
    print(f"  {label} clear {cleared} seen marker(s)")

    # 3. Report -- and only on request, remove -- calls made since the seed.
    strays = []
    for collection in db.collections():
        if not collection.id.startswith("conversations__"):
            continue
        for doc in collection.stream():
            if doc.id.startswith(SEEDED_PREFIXES):
                continue
            raw = doc.to_dict() or {}
            strays.append((collection.id, doc.reference, doc.id, raw.get("turns")))

    for _, ref, doc_id, turns in strays:
        if args.drop_test_calls:
            print(f"  {label} delete  {doc_id} ({turns} turns)")
            if not dry:
                ref.delete()
        else:
            print(
                f"  kept     {doc_id} ({turns} turns) -- --drop-test-calls removes it"
            )

    print(
        f"\n{'DRY RUN. ' if dry else ''}"
        f"{rearmed} question(s) re-armed, {cleared} seen marker(s) cleared, "
        f"{len(strays)} call(s) since the seed."
    )
    if dry:
        print("Re-run with --apply to write these changes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
