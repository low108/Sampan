"""Communities — her chapters.

The third tier of the graph, after Zep §2.3. Clusters of entities that keep
turning up together: the father, the coffee shop, Jalan Bandar, the kaya toast,
the Milo, the lorry driver who kept coming back. That cluster is not a
statistical artifact — it is *the coffee shop years*, which is how she would
describe it and how her son would want to find it.

Zep uses **label propagation rather than Leiden**, chosen for "straightforward
dynamic extension, which enables the system to maintain accurate community
representations for longer periods as new data enters the graph, delaying the
need for complete community refreshes". Both halves are implemented here:

    extend()   one recursive step -- a new entity joins the community held by
               the plurality of its neighbours. Cheap, runs per call.
    detect()   full propagation to convergence. The paper is explicit that
               dynamic updates drift and "periodic community refreshes remain
               necessary", so this is scheduled, not per call.

The community *name* carries key terms and is the search field for community
lookup, exactly as it is for entity names and fact text — so one artifact
serves both the chapters view and retrieval.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.facts import Fact
from sampan.models import Entity


class Community(BaseModel):
    """A chapter of her life."""

    community_id: str
    name: str = Field(
        default="", description="Key terms. The search field for this tier."
    )
    summary: str = ""
    member_ids: list[str] = Field(default_factory=list)

    @property
    def size(self) -> int:
        return len(self.member_ids)


def _adjacency(facts: list[Fact]) -> dict[str, set[str]]:
    """Who shares a fact with whom.

    Only current facts build the graph. A retired assertion should not go on
    holding two people together in a chapter — she has already said otherwise.
    """
    linked: dict[str, set[str]] = defaultdict(set)
    for fact in facts:
        if not fact.is_current or not fact.object_id:
            continue
        linked[fact.subject_id].add(fact.object_id)
        linked[fact.object_id].add(fact.subject_id)
    return linked


def hub_entities(entities: list[Entity], facts: list[Fact]) -> set[str]:
    """The one entity connected to so much of the graph that it cannot separate it.

    In her own archive that is her: nearly every fact is about her life, so she
    neighbours everyone, and label propagation pulls her estate childhood and
    her shop years into a single chapter because she is the only thing they
    share. She belongs to every chapter, which is exactly why she cannot be
    used to tell them apart.

    Found by dominance rather than by a threshold. In the real archive she has
    degree 8 and the next entity has 3 -- an outlier, not merely a busy node --
    whereas "more than half the graph" excluded nobody when only 17 of 28
    entities appear in any fact, and "at least half" would have thrown out the
    coffee shop as well.

    Found structurally rather than by name, because the narrator entity is
    called "Ah Khim" while the household record says "Lim Siew Khim". A name
    match silently excluded no one, and a filter that quietly does nothing is
    worse than no filter: the chapters look computed either way.
    """
    linked = _adjacency(facts)
    live = {e.entity_id for e in entities if e.merged_into is None}
    degrees = sorted(
        (
            (len(neighbours & live), node)
            for node, neighbours in linked.items()
            if node in live
        ),
        reverse=True,
    )
    if len(degrees) < 4:
        return set()

    (top, node), (runner_up, _) = degrees[0], degrees[1]
    return {node} if top >= 2 * runner_up else set()


def detect(
    entities: list[Entity],
    facts: list[Fact],
    *,
    exclude: set[str] | None = None,
    max_rounds: int = 20,
) -> list[list[str]]:
    """Full label propagation to convergence. The periodic refresh.

    Every node starts as its own community and repeatedly adopts the label held
    by the plurality of its neighbours. Ties break on the lowest label so the
    result is deterministic — the algorithm is normally randomised, and a
    chapter list that reshuffles between runs would be unreadable to a family
    watching it settle.

    `exclude` exists for the narrator, and it is not an optimisation. She is
    the subject of most facts in her own archive, which makes her a hub joining
    everything to everything: left in, her estate childhood and her marriage
    collapse into one chapter through her, because she is the only thing they
    share. She belongs to every chapter of her life, so she cannot distinguish
    between them, and the clustering has to run on everyone else.
    """
    skip = exclude or set()
    linked = _adjacency(facts)
    nodes = [
        e.entity_id
        for e in entities
        if e.merged_into is None and e.entity_id not in skip
    ]
    linked = {
        node: {n for n in neighbours if n not in skip}
        for node, neighbours in linked.items()
        if node not in skip
    }
    label = {node: node for node in nodes}

    for _ in range(max_rounds):
        changed = False
        for node in sorted(nodes):
            neighbours = linked.get(node, set())
            if not neighbours:
                continue
            counts = Counter(label[n] for n in neighbours if n in label)
            if not counts:
                continue
            best = max(counts.values())
            winner = min(lbl for lbl, count in counts.items() if count == best)
            if winner != label[node]:
                label[node] = winner
                changed = True
        if not changed:
            break

    grouped: dict[str, list[str]] = defaultdict(list)
    for node, lbl in label.items():
        grouped[lbl].append(node)

    # A lone entity is not a chapter.
    return [sorted(members) for members in grouped.values() if len(members) > 1]


def extend(
    entity_id: str, communities: list[Community], facts: list[Fact]
) -> list[Community]:
    """Place one new entity without recomputing anything. The dynamic step.

    Zep's single recursive step of label propagation: the new node surveys its
    neighbours and joins the community held by the plurality of them. Cheap
    enough to run as each call folds in, and drifting from what a full run
    would produce — which is why `detect` still has to be scheduled.
    """
    linked = _adjacency(facts)
    neighbours = linked.get(entity_id, set())
    if not neighbours:
        return communities

    home = Counter(
        community.community_id
        for community in communities
        for member in community.member_ids
        if member in neighbours
    )
    if not home:
        return communities

    best = max(home.values())
    winner = min(cid for cid, count in home.items() if count == best)
    return [
        community.model_copy(
            update={"member_ids": sorted({*community.member_ids, entity_id})}
        )
        if community.community_id == winner
        else community
        for community in communities
    ]


SUMMARY_PROMPT = """\
Below are people, places and things from one elderly woman's life that keep
appearing together, and the facts connecting them.

Give this cluster a name and a short summary, as a chapter of her life.

- `name`: three to six words a family member would recognise, in her world's
  terms — "The coffee shop years", "The estate childhood". Not a category like
  "Work" or "Family". This is also what gets searched, so use the words that
  actually occur: place names, people, the things themselves.
- `summary`: two or three sentences on what this part of her life was. Say only
  what the facts below support. Do not add colour, do not infer how she felt,
  and do not round the years off.

Members:
{members}

What is known:
{facts}
"""


class CommunitySummary(BaseModel):
    name: str
    summary: str


class CommunityNamer(Protocol):
    """Seam for the model call, so clustering is testable offline."""

    def describe(
        self, members: list[Entity], facts: list[Fact]
    ) -> CommunitySummary: ...


class GeminiCommunityNamer:
    def __init__(self, settings: Any) -> None:
        self._settings = settings
        self._cached_client: Any | None = None

    @property
    def _client(self) -> Any:
        if self._cached_client is None:
            from google import genai

            self._cached_client = genai.Client(
                vertexai=True,
                project=self._settings.project_id,
                location=self._settings.vertex_location,
            )
        return self._cached_client

    def describe(self, members: list[Entity], facts: list[Fact]) -> CommunitySummary:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self._settings.archivist_model,
            contents=SUMMARY_PROMPT.format(
                members="\n".join(
                    f"  {e.canonical_name}"
                    f"{f' ({e.role})' if e.role else ''}"
                    f"{f' — {e.detail[:60]}' if e.detail else ''}"
                    for e in members
                ),
                facts="\n".join(f"  {f.render()}" for f in facts),
            ),
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CommunitySummary,
                temperature=0.3,
            ),
        )
        parsed = response.parsed
        if parsed is None:
            return CommunitySummary(name="", summary="")
        return parsed


def build_communities(
    entities: list[Entity],
    facts: list[Fact],
    namer: CommunityNamer | None = None,
    *,
    exclude: set[str] | None = None,
) -> list[Community]:
    """Cluster, then name. The full refresh, end to end.

    Ordered largest first, because that is the part of her life the archive
    knows most about and the one a family opens first.
    """
    by_id = {e.entity_id: e for e in entities}
    communities: list[Community] = []

    for index, members in enumerate(detect(entities, facts, exclude=exclude)):
        member_entities = [by_id[m] for m in members if m in by_id]
        member_facts = [
            f
            for f in facts
            if f.is_current
            and (f.subject_id in set(members) or (f.object_id or "") in set(members))
        ]
        described = (
            namer.describe(member_entities, member_facts)
            if namer is not None
            else CommunitySummary(name="", summary="")
        )
        communities.append(
            Community(
                community_id=f"com_{index:02d}",
                name=described.name,
                summary=described.summary,
                member_ids=members,
            )
        )

    return sorted(communities, key=lambda c: -c.size)


class RefreshResult(BaseModel):
    """What one narrator's refresh did. Returned rather than printed, so the
    script and the scheduled endpoint can report the same thing."""

    narrator_id: str
    entities: int = 0
    facts: int = 0
    chapters: int = 0
    excluded: list[str] = Field(default_factory=list)
    names: list[str] = Field(default_factory=list)
    saved: bool = False
    skipped: str = ""


def refresh_narrator(
    repository: Any,
    narrator_id: str,
    namer: CommunityNamer | None,
    *,
    save: bool,
) -> RefreshResult:
    """Recompute one narrator's chapters, and optionally store them.

    The shared core. `scripts/refresh_communities.py` and the scheduled
    `/internal/communities` endpoint both call this, because two copies of a
    clustering pass would drift and the one running unattended would be the
    copy nobody noticed had drifted.
    """
    entities = repository.load_entities(narrator_id)
    facts = repository.load_facts(narrator_id)

    if not facts:
        return RefreshResult(
            narrator_id=narrator_id,
            entities=len(entities),
            skipped="no facts yet -- nothing to cluster",
        )

    # She is in every chapter of her own life, so she cannot separate them.
    # Found by connectivity, not by name.
    hubs = hub_entities(entities, facts)
    chapters = build_communities(entities, facts, namer, exclude=hubs)

    if save:
        repository.save_communities(narrator_id, chapters)

    by_id = {e.entity_id: e.canonical_name for e in entities}
    return RefreshResult(
        narrator_id=narrator_id,
        entities=len(entities),
        facts=len(facts),
        chapters=len(chapters),
        excluded=[by_id[h] for h in hubs if h in by_id],
        names=[c.name or f"(unnamed, {c.size} members)" for c in chapters],
        saved=save,
    )
