"""Starting a call from stored memory, and folding the result back in.

This is where the loop closes. Everything else produces or consumes state;
this module is what makes the state survive a restart, and therefore what makes
session 5 differ from session 1 in production rather than only in a test.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sampan.archivist import StoryExtractor, ingest_conversation, mentions
from sampan.armor import Screen, screen
from sampan.companion import build_agent
from sampan.config import Settings
from sampan.contradiction import ContradictionJudge, reconcile
from sampan.entities import ensure_self
from sampan.fact_extraction import FactExtractor, Refusal, build_facts
from sampan.memories import MemoryRequest, publish
from sampan.opener import build_session_plan, render_plan
from sampan.preferences import fold_preferences
from sampan.repository import NarratorMemory, Repository
from sampan.tools import CallMemory, build_tools


@dataclass
class Transcript:
    """Both sides of one call, in order.

    Kept as plain turns because that is what the Archivist reads — the same
    shape as the seed transcripts, so production and fixtures stay identical.
    """

    turns: list[tuple[str, str]] = field(default_factory=list)

    def add(self, speaker: str, text: str) -> None:
        text = text.strip()
        if not text:
            return
        # The Live API streams transcription incrementally, so consecutive
        # fragments from one speaker are revisions rather than new turns.
        if self.turns and self.turns[-1][0] == speaker:
            self.turns[-1] = (speaker, text)
            return
        self.turns.append((speaker, text))

    def render(self) -> str:
        labels = {"user": "K", "agent": "A"}
        return "\n".join(
            f"{labels.get(speaker, speaker)}: {text}" for speaker, text in self.turns
        )

    def __len__(self) -> int:
        return len(self.turns)


@dataclass
class PreparedCall:
    agent: object
    memory: CallMemory
    stored: NarratorMemory
    conversation_id: str


def prepare_call(
    repository: Repository, settings: Settings, *, narrator_id: str
) -> PreparedCall:
    """Load everything this call should already know."""
    stored = repository.load_memory(narrator_id)
    # She has to be in her own graph, or every fact about her is refused for an
    # unknown subject and the archive can record everything except its subject.
    entities = ensure_self(
        repository.load_entities(narrator_id),
        narrator_id=narrator_id,
        display_name=stored.display_name or repository.display_name(narrator_id),
    )
    ask = repository.pending_ask(narrator_id)

    # Second resolution alone collides: Live API sessions cap at roughly
    # fifteen minutes, so a dropped call and its redial can land in the same
    # second, and the second call's stories would overwrite the first's.
    conversation_id = (
        f"conv_{narrator_id}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        f"_{uuid.uuid4().hex[:6]}"
    )

    memory = CallMemory(
        threads=stored.threads,
        entities=entities,
        preferences=stored.preferences,
        sensitivities=stored.sensitivities,
        ask=ask,
        # Only what the archive currently believes. Superseded facts stay in
        # the store because she said them, but the agent must not speak them.
        facts=repository.load_facts(narrator_id),
    )

    def deliver_concern(kind: str, detail: str) -> None:
        repository.raise_concern(narrator_id, kind, detail, conversation_id)

    memory.on_concern = deliver_concern
    memory.search_transcripts = lambda query: repository.search_transcripts(
        narrator_id, query
    )

    def forget(subject: str) -> None:
        repository.forget(narrator_id, subject)

    memory.on_forget = forget

    plan = build_session_plan(
        threads=stored.threads,
        sensitivities=stored.sensitivities,
        ask=ask,
        session_count=stored.session_count,
        last_closure=stored.last_closure,
    )

    memory.target_domain = plan.target_domain.value if plan.target_domain else ""

    agent = build_agent(
        settings,
        preferences=stored.preferences,
        sensitivities=stored.sensitivities,
        session_plan=render_plan(plan),
        tools=build_tools(memory),
    )

    return PreparedCall(
        agent=agent, memory=memory, stored=stored, conversation_id=conversation_id
    )


# Below this, a call was too short to have contained a story. Running the
# Archivist on a misdial wastes a model call and pollutes the archive.
MIN_TURNS_TO_EXTRACT = 4


def finish_call(
    repository: Repository,
    extractor: StoryExtractor,
    prepared: PreparedCall,
    transcript: Transcript,
    *,
    narrator_id: str,
    settings: Settings | None = None,
    fact_extractor: FactExtractor | None = None,
    judge: ContradictionJudge | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
    screener: Screen | None = None,
) -> NarratorMemory | None:
    """Fold a finished call back into stored memory.

    Returns the updated memory, or None if the call was too short to extract
    anything from.
    """
    # Screened before anything is written, and the screened text is what
    # everything downstream reads. Extracting from the original while storing
    # the redacted version would make `build_facts` refuse exactly the quotes
    # that had something worth protecting in them.
    checked = screen(transcript.render(), screener)
    rendered = checked.text

    # `unscreened` is recorded alongside the findings and is not the same as
    # an empty findings list: one means the screen ran and objected to
    # nothing, the other means it never ran. Which calls went through
    # unchecked has to be a query, not a guess.

    # Saved before the length check, like the transcript: a call too short to
    # extract from is exactly the one you want the tool record for.
    repository.save_conversation(
        narrator_id,
        prepared.conversation_id,
        rendered,
        turns=len(transcript),
        tool_calls=tool_calls or [],
        screened=[f.model_dump(mode="json") for f in checked.findings],
        unscreened=checked.unscreened,
        screen_error=checked.reason,
    )

    for subject in prepared.memory.private_marks:
        repository.mark_private(narrator_id, subject)

    if len(transcript) < MIN_TURNS_TO_EXTRACT:
        # The question is *not* consumed here. A call this short is a misdial,
        # a wrong moment, or a phone put down -- she may have heard his question
        # read out and had no chance to answer it. Burning it would tell Wei Lun
        # it had been delivered and leave her never asked again.
        return None

    # Consumed only by a call that was long enough to be a real exchange.
    if prepared.memory.ask_delivered and prepared.memory.ask is not None:
        repository.mark_ask_delivered(narrator_id, prepared.memory.ask.ask_id)

    settings = settings or Settings()

    # Everything she has ever asked to drop, including anything said on this
    # call -- `forget_this` writes through immediately, so the tombstone is
    # already here by the time extraction runs.
    forgotten = repository.forgotten(narrator_id)

    outcome = ingest_conversation(
        rendered,
        extractor,
        known_entities=prepared.memory.entities,
        known_threads=prepared.stored.threads,
        known_anchors=prepared.stored.anchors,
        known_preferences=prepared.stored.preferences,
        known_sensitivities=prepared.stored.sensitivities,
        forgotten=forgotten,
        conversation_id=prepared.conversation_id,
    )

    # Preferences the agent noticed mid-call, via note_preference, are folded
    # in alongside the ones extraction inferred afterwards.
    preferences = fold_preferences(
        outcome.preferences,
        prepared.memory.noted_preferences,
        conversation_id=prepared.conversation_id,
    )

    updated = NarratorMemory(
        narrator_id=narrator_id,
        display_name=prepared.stored.display_name,
        threads=outcome.threads,
        anchors=outcome.anchors,
        preferences=preferences,
        sensitivities=outcome.sensitivities,
        session_count=prepared.stored.session_count + 1,
        last_closure=outcome.closure.reason,
    )

    repository.save_memory(updated)
    repository.save_entities(narrator_id, outcome.entities)
    written = repository.save_stories(
        narrator_id, prepared.conversation_id, outcome.stories
    )

    # Ask for an image for each new story, and do not wait for one. Veo is tens
    # of seconds; the card is complete without it and acquires it later (D21).
    # `publish` never raises -- a picture is not worth a failed call.
    for story_id, story in zip(written, outcome.stories, strict=False):
        candidate = story.candidate
        publish(
            settings,
            MemoryRequest(
                narrator_id=narrator_id,
                story_id=story_id,
                title=candidate.title,
                sense_detail=candidate.sense_detail,
                where_said=candidate.where.raw_name,
                year=candidate.when.start_year if candidate.when else None,
            ),
        )

    # Facts are a second pass with its own schema, deliberately not another
    # field on the story extraction: a schema is part of the prompt, and one
    # carrying fields its instructions do not govern gets those fields filled.
    # Optional, so a call still folds in cleanly without it.
    if fact_extractor is not None:
        # What was dropped, and by which rule. Extraction is silent to the
        # agent by design; it should not also be silent to whoever is trying
        # to work out why a fact she plainly stated is not in the archive.
        refusals: list[Refusal] = []
        extracted = build_facts(
            fact_extractor.extract(rendered, outcome.entities),
            transcript=rendered,
            known_entities=outcome.entities,
            episode_id=prepared.conversation_id,
            on_refusal=refusals.append,
        )
        repository.record_refusals(
            narrator_id,
            prepared.conversation_id,
            [r.model_dump(mode="json") for r in refusals],
        )
        # Facts are extracted from the raw transcript, so they rebuild a
        # forgotten subject even when its story has already been dropped. The
        # quote is what to match on: it is the sentence she actually said.
        extracted = [
            fact
            for fact in extracted
            if not any(mentions(fact.quote, subject) for subject in forgotten)
        ]
        if judge is not None:
            # A later telling retires an earlier assertion; it never deletes
            # it, and where the disagreement is about her account rather than
            # about the world, valid time is left alone. Disputes come back as
            # questions for the next call, because which telling is right is
            # hers to settle.
            extracted, disputes = reconcile(
                extracted, repository.load_facts(narrator_id), judge
            )
            for dispute in disputes:
                repository.raise_concern(
                    narrator_id, "contradiction", dispute, prepared.conversation_id
                )
        repository.save_facts(narrator_id, extracted)

    return updated
