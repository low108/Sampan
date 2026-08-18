"""Recompute the chapters of a narrator's life.

Zep extends communities cheaply as each conversation lands — a new entity joins
whichever community most of its neighbours are in — and is explicit that this
drifts: "periodic community refreshes remain necessary". This is that refresh.

Scheduled, never on the call path. It runs full label propagation over the
whole graph and re-names every chapter, which costs one model call per chapter
and takes seconds.

    uv run python scripts/refresh_communities.py            # show what would change
    uv run python scripts/refresh_communities.py --apply
"""

from __future__ import annotations

import argparse
import sys

from sampan.communities import (
    GeminiCommunityNamer,
    build_communities,
    hub_entities,
)
from sampan.config import Settings, apply_genai_env
from sampan.repository import Repository
from sampan.store import build_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("narrators", nargs="*", default=["ah_khim", "wei_lun"])
    parser.add_argument(
        "--apply", action="store_true", help="write the chapters (default: dry run)"
    )
    args = parser.parse_args()

    settings = Settings()
    if not settings.configured:
        print("No GOOGLE_CLOUD_PROJECT configured.", file=sys.stderr)
        return 1
    apply_genai_env(settings)

    repo = Repository(build_store(settings))
    namer = GeminiCommunityNamer(settings)

    for narrator_id in args.narrators:
        entities = repo.load_entities(narrator_id)
        facts = repo.load_facts(narrator_id)
        print(f"\n{narrator_id}: {len(entities)} entities, {len(facts)} current facts")

        if not facts:
            print("  no facts yet — nothing to cluster")
            continue

        # She is in every chapter of her own life, so she cannot separate
        # them. Found by connectivity, not by name.
        hubs = hub_entities(entities, facts)
        if hubs:
            names = ", ".join(e.canonical_name for e in entities if e.entity_id in hubs)
            print(f"  excluded as too connected to cluster: {names}")

        chapters = build_communities(
            entities, facts, namer if args.apply else None, exclude=hubs
        )
        by_id = {e.entity_id: e.canonical_name for e in entities}

        for chapter in chapters:
            title = chapter.name or f"(unnamed, {chapter.size} members)"
            print(f"\n  {title}")
            if chapter.summary:
                print(f"    {chapter.summary}")
            print("    " + ", ".join(by_id.get(m, m) for m in chapter.member_ids))

        if args.apply:
            repo.save_communities(narrator_id, chapters)
            print(f"\n  saved {len(chapters)} chapters")

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to name and save these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
