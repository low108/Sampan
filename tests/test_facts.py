"""Facts — the edges of the memory graph.

The refusal cases carry most of the weight here. A fact the archive cannot
attribute to a sentence she said is a fact it must not assert, and every earlier
version of this check was added after a model had already got past a weaker one.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from sampan.fact_extraction import ExtractedFact, build_facts
from sampan.facts import Fact, Predicate, is_quoted
from sampan.models import Entity, EntityType, Precision, When

TRANSCRIPT = """\
A: Your father — what did he do?
K: He tapped rubber first, until his hands were all spoiled. Later he saved a
   bit of money, nineteen fifty-eight he opened a coffee shop in Ipoh, at Jalan
   Bandar. Sixty-nine the shop closed.
A: And where were you living then?
K: Upstairs. Above the shop.
"""


def entity(entity_id: str, name: str, role: str | None = None) -> Entity:
    return Entity(
        entity_id=entity_id,
        type=EntityType.PERSON,
        canonical_name=name,
        role=role,
        provisional=False,
    )


KNOWN = [
    entity("ent_father", "Lim Ah Hock", "father"),
    entity("ent_narrator", "Lim Siew Khim"),
    Entity(
        entity_id="ent_jalan_bandar",
        type=EntityType.PLACE,
        canonical_name="Jalan Bandar",
        provisional=False,
    ),
]

REAL_QUOTE = (
    "Later he saved a bit of money, nineteen fifty-eight he opened a coffee "
    "shop in Ipoh, at Jalan Bandar."
)


def extracted(**overrides) -> ExtractedFact:
    base = {
        "subject_id": "ent_father",
        "predicate": Predicate.OWNED,
        "object_id": "ent_jalan_bandar",
        "statement": "her father ran a coffee shop at Jalan Bandar",
        "valid_from": When(
            raw_phrase="nineteen fifty-eight",
            start_year=1958,
            precision=Precision.YEAR,
            confidence=0.9,
        ),
        "valid_to": When(
            raw_phrase="sixty-nine",
            start_year=1969,
            precision=Precision.YEAR,
            confidence=0.9,
        ),
        "quote": REAL_QUOTE,
        "confidence": 0.9,
    }
    return ExtractedFact(**{**base, **overrides})


def build(*items: ExtractedFact) -> list[Fact]:
    return build_facts(
        list(items),
        transcript=TRANSCRIPT,
        known_entities=KNOWN,
        episode_id="conv_001",
    )


class TestWhatTheArchiveWillAssert:
    def test_a_supported_fact_is_kept(self) -> None:
        facts = build(extracted())

        assert len(facts) == 1
        assert facts[0].statement == "her father ran a coffee shop at Jalan Bandar"
        assert facts[0].episode_id == "conv_001"

    def test_her_words_are_kept_beside_the_years(self) -> None:
        """The whole reason valid time is a `When` and not a datetime."""
        fact = build(extracted())[0]

        assert fact.valid_from is not None
        assert fact.valid_from.raw_phrase == "nineteen fifty-eight"
        assert fact.valid_from.start_year == 1958
        assert fact.year_span == (1958, 1969)

    def test_every_fact_gets_its_own_id(self) -> None:
        facts = build(extracted(), extracted())

        assert facts[0].fact_id != facts[1].fact_id


class TestWhatTheArchiveRefuses:
    def test_a_quote_she_never_said_is_dropped(self) -> None:
        """The failure mode that has now cost four bugs: a required field filled
        with the model's own reasoning rather than her speech."""
        facts = build(
            extracted(quote="The father is identified as a coffee shop proprietor.")
        )

        assert facts == []

    def test_a_fragment_too_short_to_mean_anything_is_dropped(self) -> None:
        facts = build(extracted(quote="the shop"))

        assert facts == []

    def test_a_fact_about_an_unknown_subject_is_dropped(self) -> None:
        facts = build(extracted(subject_id="ent_invented"))

        assert facts == []

    def test_a_fact_asserting_nothing_is_dropped(self) -> None:
        facts = build(extracted(object_id=None, object_literal="   "))

        assert facts == []

    def test_an_unknown_object_survives_as_a_literal(self) -> None:
        """She said it; we simply have no node for it yet. Keeping her words
        beats dropping the relationship."""
        facts = build(extracted(object_id="ent_not_in_archive"))

        assert len(facts) == 1
        assert facts[0].object_id is None
        assert facts[0].object_literal == "ent_not_in_archive"


class TestQuoteVerification:
    def test_her_sentence_is_accepted(self) -> None:
        assert is_quoted(REAL_QUOTE, TRANSCRIPT)

    def test_reasoning_dressed_as_a_quote_is_rejected(self) -> None:
        assert not is_quoted(
            "Identified as being in the vicinity of Sungai Siput", TRANSCRIPT
        )

    def test_punctuation_and_case_do_not_matter(self) -> None:
        assert is_quoted("SIXTY-NINE THE SHOP CLOSED", TRANSCRIPT)


class TestCurrency:
    """What the archive currently believes, versus what it once believed."""

    def _fact(self, **overrides) -> Fact:
        base = {
            "fact_id": "f1",
            "subject_id": "ent_father",
            "predicate": Predicate.OWNED,
            "object_literal": "a coffee shop",
            "statement": "her father ran a coffee shop",
            "episode_id": "conv_001",
            "quote": REAL_QUOTE,
        }
        return Fact(**{**base, **overrides})

    def test_a_new_fact_is_current(self) -> None:
        assert self._fact().is_current

    def test_a_superseded_fact_is_not(self) -> None:
        fact = self._fact(t_expired=datetime.now(UTC), superseded_by="f2")

        assert not fact.is_current

    def test_a_superseded_fact_is_still_readable(self) -> None:
        """Nothing is deleted. She said it once, and that stays true about her."""
        fact = self._fact(t_expired=datetime.now(UTC), superseded_by="f2")

        assert fact.statement == "her father ran a coffee shop"
        assert fact.quote == REAL_QUOTE


class TestRendering:
    def _with(self, valid_from: When | None, valid_to: When | None) -> Fact:
        return Fact(
            fact_id="f1",
            subject_id="ent_father",
            predicate=Predicate.OWNED,
            object_literal="a coffee shop",
            statement="her father ran a coffee shop",
            valid_from=valid_from,
            valid_to=valid_to,
            episode_id="conv_001",
            quote=REAL_QUOTE,
        )

    def test_a_span_reads_as_a_span(self) -> None:
        fact = self._with(
            When(
                raw_phrase="1958",
                start_year=1958,
                precision=Precision.YEAR,
                confidence=1,
            ),
            When(
                raw_phrase="1969",
                start_year=1969,
                precision=Precision.YEAR,
                confidence=1,
            ),
        )

        assert fact.render().startswith("1958–1969 · ")

    def test_her_phrase_stands_in_when_no_year_resolved(self) -> None:
        fact = self._with(
            When(
                raw_phrase="before I married",
                precision=Precision.RELATIVE,
                confidence=0.6,
            ),
            None,
        )

        assert "before I married" in fact.render()

    def test_an_undated_fact_says_so_rather_than_guessing(self) -> None:
        assert "year not yet told" in self._with(None, None).render()


class TestPredicateVocabulary:
    def test_the_model_cannot_invent_a_relation(self) -> None:
        """Predicates are join keys. The same relation named two ways is two
        relations, and no later string matching reconciles them."""
        with pytest.raises(ValueError):
            ExtractedFact(
                subject_id="ent_father",
                predicate="ran_a_business",  # type: ignore[arg-type]
                object_literal="a coffee shop",
                statement="her father ran a coffee shop",
                quote=REAL_QUOTE,
            )

    def test_the_extraction_schema_does_not_expose_archive_fields(self) -> None:
        """`t_created`, `t_expired`, `superseded_by` and `fact_id` belong to the
        archive. A field offered to a model is a field it will fill."""
        offered = set(ExtractedFact.model_fields)

        assert not offered & {"fact_id", "t_created", "t_expired", "superseded_by"}
