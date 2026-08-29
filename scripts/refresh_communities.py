"""Recompute the chapters of a narrator's life, by hand.

Zep extends communities cheaply as each conversation lands — a new entity joins
whichever community most of its neighbours are in — and is explicit that this
drifts: "periodic community refreshes remain necessary". This is that refresh.

Never on the call path. It runs full label propagation over the whole graph and
re-names every chapter, which costs one model call per chapter and takes
seconds.

    uv run python scripts/refresh_communities.py            # show what would change
    uv run python scripts/refresh_communities.py --apply

In production this runs on a schedule instead, against `/internal/communities`
— see `scripts/setup_scheduler.sh`. Both paths call `refresh_narrator()`, so
there is one clustering implementation rather than two that drift, with the
unattended one being the copy nobody notices has drifted.
"""

from __future__ import annotations

import argparse
import sys

from sampan.communities import GeminiCommunityNamer, refresh_narrator
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
        outcome = refresh_narrator(
            repo, narrator_id, namer if args.apply else None, save=args.apply
        )
        print(
            f"\n{narrator_id}: {outcome.entities} entities, "
            f"{outcome.facts} current facts"
        )
        if outcome.skipped:
            print(f"  {outcome.skipped}")
            continue
        if outcome.excluded:
            print(
                "  excluded as too connected to cluster: "
                + ", ".join(outcome.excluded)
            )
        for name in outcome.names:
            print(f"    {name}")
        if outcome.saved:
            print(f"\n  saved {outcome.chapters} chapters")

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to name and save these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
