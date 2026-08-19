"""Extract facts from conversations already in the archive.

Facts arrived after the seed sessions were recorded, so the stored transcripts
have stories and entities but no edges. This walks the conversations in order
and runs the same extraction the live pipeline runs, including contradiction
reconciliation — so a later session retiring an earlier assertion happens here
exactly as it would have at the time.

Order matters. Entity resolution has already run, so facts can point at entities
by id; running these in a different order would change which entities existed
when, and produce a different graph.

    uv run python scripts/backfill_facts.py             # show what would be written
    uv run python scripts/backfill_facts.py --apply
"""

from __future__ import annotations

import argparse
import sys

from sampan.config import Settings, apply_genai_env
from sampan.contradiction import GeminiContradictionJudge, reconcile
from sampan.fact_extraction import GeminiFactExtractor, build_facts
from sampan.repository import Repository
from sampan.store import build_store


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("narrators", nargs="*", default=["ah_khim", "wei_lun"])
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    settings = Settings()
    if not settings.configured:
        print("No GOOGLE_CLOUD_PROJECT configured.", file=sys.stderr)
        return 1
    apply_genai_env(settings)

    store = build_store(settings)
    repo = Repository(store)
    extractor = GeminiFactExtractor(settings)
    judge = GeminiContradictionJudge(settings)

    for narrator_id in args.narrators:
        entities = repo.load_entities(narrator_id)
        conversations = sorted(
            store.list(f"conversations__{narrator_id}"),
            key=lambda c: str(c.get("occurred_at") or c["conversation_id"]),
        )
        print(f"\n{narrator_id}: {len(conversations)} conversations")

        held = repo.load_facts(narrator_id)
        for raw in conversations:
            transcript = raw.get("transcript", "")
            if not transcript.strip():
                continue

            proposed = extractor.extract(transcript, entities)
            facts = build_facts(
                proposed,
                transcript=transcript,
                known_entities=entities,
                episode_id=raw["conversation_id"],
            )
            facts, disputes = reconcile(facts, held, judge)

            kept = [f for f in facts if f.is_current]
            print(
                f"  ...{raw['conversation_id'][-10:]}  {len(proposed)} proposed"
                f" -> {len(kept)} current"
            )
            for fact in kept:
                print(f"      {fact.render()[:86]}")
            for dispute in disputes:
                print(f"      DISPUTED: {dispute[:80]}")

            if args.apply:
                repo.save_facts(narrator_id, facts)
                for dispute in disputes:
                    repo.raise_concern(
                        narrator_id, "contradiction", dispute, raw["conversation_id"]
                    )
            held = [*held, *facts]

    if not args.apply:
        print("\nDRY RUN. Re-run with --apply to write these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
