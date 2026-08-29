#!/usr/bin/env python
"""Ask for a picture for stories that were told before Veo was switched on.

New stories queue themselves at the end of the call. Everything already in the
archive never will, because nothing re-publishes on read -- so the seeded life
would stay pictureless forever while only stories told from today on had one.

    python scripts/backfill_memories.py                  # dry run
    python scripts/backfill_memories.py --commit --limit 4
    python scripts/backfill_memories.py --commit --story story_ah_khim_003

Dry run by default and `--limit` defaulting low, because each message is a
paid Veo render and a careless `--commit` here bills for the whole archive at
once. Stories that already have an asset are skipped, so re-running costs
nothing for what is already done.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--narrator", default="ah_khim")
    ap.add_argument("--story", action="append", default=[], help="just these ids")
    ap.add_argument(
        "--limit", type=int, default=4, help="most to queue in one go (default 4)"
    )
    ap.add_argument(
        "--redo", action="store_true", help="include stories that already have one"
    )
    ap.add_argument("--commit", action="store_true", help="actually publish")
    return ap.parse_args()


def main() -> int:
    if Path(".env").exists():
        for line in Path(".env").read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

    from sampan.config import Settings
    from sampan.family import build_cards
    from sampan.memories import MemoryRequest, publish
    from sampan.repository import Repository
    from sampan.store import build_store

    args = parse_args()
    settings = Settings()
    if not settings.memories_topic:
        print("SAMPAN_MEMORIES_TOPIC is not set. Run scripts/setup_memories.sh.")
        return 1

    repository = Repository(build_store(settings))
    cards = build_cards(repository.load_stories(args.narrator))
    have = {a.get("story_id") for a in repository.load_memory_assets(args.narrator)}

    wanted = [c for c in cards if not args.story or c.story_id in args.story]
    if not args.redo:
        wanted = [c for c in wanted if c.story_id not in have]

    print(f"{len(cards)} stories, {len(have)} already have a clip")
    if not wanted:
        print("Nothing to do.")
        return 0

    queue = wanted[: args.limit]
    print(f"\nwould queue {len(queue)} of {len(wanted)}:")
    for card in queue:
        # The sense detail is what the prompt is built from, so a story without
        # one is worth seeing before it is paid for -- it will be filmed from
        # its title, which is the Archivist's phrasing rather than hers.
        print(f"  {card.story_id[:34]:34}  {card.title[:38]:38}")
        if not card.sense_detail:
            print(f"  {'':34}  (no sense detail; filmed from the title)")

    if not args.commit:
        print("\nDry run. Re-run with --commit. Each one is a paid Veo render.")
        return 0

    for card in queue:
        sent = publish(
            settings,
            MemoryRequest(
                narrator_id=args.narrator,
                story_id=card.story_id,
                title=card.title,
                sense_detail=card.sense_detail,
                where_said=card.where_said,
                year=card.year_from,
            ),
        )
        print(f"{'queued ' if sent else 'FAILED '} {card.story_id}")

    print("\nQueued. Each takes tens of seconds; the cards pick them up on reload.")
    print("Watch: gcloud run services logs read sampan --region=asia-southeast1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
