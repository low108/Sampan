"""Routing a disagreement to the right time axis.

The distinction under test is the one thing this system does differently from
the paper it follows, and it is invisible if you get it wrong: the fields are
all populated either way, and only the meaning is nonsense.
"""

from __future__ import annotations

from sampan.contradiction import (
    Disagreement,
    Judgement,
    apply_conflicting_testimony,
    apply_state_change,
    candidates,
    reconcile,
)
from sampan.facts import Fact, Predicate
from sampan.models import Precision, When


def year(value: int) -> When:
    return When(
        raw_phrase=str(value),
        start_year=value,
        precision=Precision.YEAR,
        confidence=0.9,
    )


def fact(
    fact_id: str,
    statement: str,
    *,
    subject: str = "ent_father",
    predicate: Predicate = Predicate.OWNED,
    valid_from: When | None = None,
    valid_to: When | None = None,
) -> Fact:
    return Fact(
        fact_id=fact_id,
        subject_id=subject,
        predicate=predicate,
        object_literal="a coffee shop",
        statement=statement,
        valid_from=valid_from,
        valid_to=valid_to,
        episode_id="conv_001",
        quote="a sentence long enough to satisfy the quote check comfortably",
        confidence=0.8,
    )


class Always:
    """A judge with its mind made up, so routing is tested and not the model."""

    def __init__(self, kind: Disagreement) -> None:
        self.kind = kind

    def judge(self, new: Fact, existing: Fact) -> Judgement:  # noqa: ARG002
        return Judgement(kind=self.kind)


class TestCandidates:
    def test_only_the_same_subject_and_relation_are_compared(self) -> None:
        """Zep constrains deduplication to edges between the same entity pair.
        It stops nonsense comparisons and keeps the model calls affordable."""
        new = fact("f_new", "her father ran a coffee shop")
        held = [
            fact("f_same", "her father ran a shop on Jalan Bandar"),
            fact(
                "f_other_subject", "her mother ran a coffee shop", subject="ent_mother"
            ),
            fact(
                "f_other_pred",
                "her father lived above the shop",
                predicate=Predicate.LIVED_AT,
            ),
        ]

        assert [f.fact_id for f in candidates(new, held)] == ["f_same"]

    def test_an_already_retired_fact_is_not_reconsidered(self) -> None:
        new = fact("f_new", "her father ran a coffee shop")
        retired = apply_conflicting_testimony(
            fact("f_old", "her father ran a stall"), new
        )

        assert candidates(new, [retired]) == []

    def test_a_fact_is_never_compared_with_itself(self) -> None:
        new = fact("f_new", "her father ran a coffee shop")

        assert candidates(new, [new]) == []


class TestStateChange:
    """The world moved on. Zep's rule as written, and right here."""

    def test_the_old_interval_closes_where_the_new_one_opens(self) -> None:
        old = fact("f_old", "she lived above the shop", valid_from=year(1969))
        new = fact("f_new", "she lived in a flat in Ipoh", valid_from=year(2016))

        amended = apply_state_change(old, new)

        assert amended.valid_to is not None
        assert amended.valid_to.start_year == 2016

    def test_the_old_fact_stays_current(self) -> None:
        """It was true, and the archive can still say when. Nothing expired."""
        old = fact("f_old", "she lived above the shop", valid_from=year(1969))

        amended = apply_state_change(old, fact("f_new", "x", valid_from=year(2016)))

        assert amended.is_current
        assert amended.superseded_by is None

    def test_an_undated_new_fact_changes_nothing(self) -> None:
        """Without a start there is nothing to close the old interval against,
        and inventing a boundary would be worse than leaving it open."""
        old = fact("f_old", "she lived above the shop", valid_from=year(1969))

        assert apply_state_change(old, fact("f_new", "x")).valid_to is None


class TestConflictingTestimony:
    """She remembers it differently. Where this departs from the paper."""

    def test_the_assertion_expires_on_the_transaction_timeline(self) -> None:
        old = fact("f_old", "the shop closed in 1969", valid_to=year(1969))
        new = fact("f_new", "the shop closed in 1970", valid_to=year(1970))

        amended = apply_conflicting_testimony(old, new)

        assert not amended.is_current
        assert amended.superseded_by == "f_new"

    def test_valid_time_is_left_completely_alone(self) -> None:
        """The load-bearing assertion.

        Zep's rule literally applied sets the old edge's valid-time end to the
        new edge's start, which reads as "her father ran a coffee shop, and
        that stopped being true in 1970" -- a claim she never made. The shop
        closed once. Only the archive's belief about *when* changed.
        """
        old = fact(
            "f_old",
            "the shop closed in 1969",
            valid_from=year(1958),
            valid_to=year(1969),
        )

        amended = apply_conflicting_testimony(
            old, fact("f_new", "the shop closed in 1970", valid_to=year(1970))
        )

        assert amended.valid_from is not None
        assert amended.valid_from.start_year == 1958
        assert amended.valid_to is not None
        assert amended.valid_to.start_year == 1969

    def test_what_she_said_survives(self) -> None:
        """Nothing is deleted. She said it, and that stays true about her."""
        old = fact("f_old", "the shop closed in 1969", valid_to=year(1969))

        amended = apply_conflicting_testimony(old, fact("f_new", "later telling"))

        assert amended.statement == "the shop closed in 1969"
        assert amended.quote


class TestReconcile:
    def test_agreement_leaves_everything_alone(self) -> None:
        held = [fact("f_old", "her father ran a coffee shop")]
        new = [fact("f_new", "her father ran a coffee shop at Jalan Bandar")]

        changed, questions = reconcile(new, held, Always(Disagreement.NONE))

        assert [f.fact_id for f in changed] == ["f_new"]
        assert questions == []

    def test_a_disputed_telling_becomes_a_question(self) -> None:
        """A contradiction is not the database's to settle. It reaches the next
        call the way a missing field does, and she decides."""
        held = [fact("f_old", "the shop closed in 1969", valid_to=year(1969))]
        new = [fact("f_new", "the shop closed in 1970", valid_to=year(1970))]

        _, questions = reconcile(new, held, Always(Disagreement.CONFLICTING_TESTIMONY))

        assert len(questions) == 1
        assert "1969" in questions[0] and "1970" in questions[0]

    def test_a_state_change_raises_no_question(self) -> None:
        """Nothing to ask her. Both are true, one after the other."""
        held = [fact("f_old", "she lived above the shop", valid_from=year(1969))]
        new = [fact("f_new", "she lived in a flat", valid_from=year(2016))]

        _, questions = reconcile(new, held, Always(Disagreement.STATE_CHANGE))

        assert questions == []

    def test_the_amended_fact_comes_back_to_be_saved(self) -> None:
        held = [fact("f_old", "the shop closed in 1969", valid_to=year(1969))]
        new = [fact("f_new", "the shop closed in 1970", valid_to=year(1970))]

        changed, _ = reconcile(new, held, Always(Disagreement.CONFLICTING_TESTIMONY))

        retired = next(f for f in changed if f.fact_id == "f_old")
        assert not retired.is_current

    def test_one_new_fact_retires_at_most_each_rival_once(self) -> None:
        held = [
            fact("f_a", "the shop closed in 1969", valid_to=year(1969)),
            fact("f_b", "the shop closed in 1968", valid_to=year(1968)),
        ]
        new = [fact("f_new", "the shop closed in 1970", valid_to=year(1970))]

        changed, _ = reconcile(new, held, Always(Disagreement.CONFLICTING_TESTIMONY))

        assert len([f for f in changed if not f.is_current]) == 2
