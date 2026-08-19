class TestGivenName:
    """A bell that names the surname names nobody: half the household shares it."""

    def test_the_surname_is_dropped(self) -> None:
        from sampan.notifications import given_name

        assert given_name("Lim Siew Khim") == "Siew Khim"
        assert given_name("Tan Wei Lun") == "Wei Lun"
        assert given_name("Tan Xin Yi") == "Xin Yi"

    def test_a_single_name_survives_intact(self) -> None:
        from sampan.notifications import given_name

        assert given_name("Khim") == "Khim"


class TestEveryWaitingQuestion:
    """A question queued behind another must not go silent.

    The call carries one question and only one, deliberately — two would turn
    a conversation into an inbox. The bell is not the call. Reusing the
    delivery queue for the notification list meant a second question was
    invisible to everyone: the sender watched nothing change, and the person
    it was for was never told anybody was waiting. Two real messages sat
    behind a stale one for a day before anybody noticed.
    """

    @staticmethod
    def _repo():
        from sampan.repository import Repository
        from sampan.store import InMemoryDocumentStore

        return Repository(InMemoryDocumentStore())

    @staticmethod
    def _members():
        from sampan.household import Member

        return [
            Member(
                narrator_id="ah_khim",
                display_name="Lim Siew Khim",
                relation="grandmother",
            ),
            Member(narrator_id="wei_lun", display_name="Tan Wei Lun", relation="son"),
        ]

    EARLY = "2026-08-17T01:00:00+00:00"
    LATE = "2026-08-18T23:22:00+00:00"
    LATEST = "2026-08-18T23:35:00+00:00"

    def _queue(self, repo, ask_id: str, who: str, question: str, at: str) -> None:
        from sampan.models import Ask

        repo.queue_ask(
            "ah_khim",
            Ask(ask_id=ask_id, from_name=who, question=question, created_at=at),
        )

    def test_the_bell_lists_all_of_them_not_just_the_next_one(self) -> None:
        from sampan.notifications import NotificationKind, notifications_for

        repo = self._repo()
        self._queue(repo, "a1", "Xin Yi", "shop name?", self.EARLY)
        self._queue(repo, "a2", "Wei Lun", "how are you doing", self.LATE)
        self._queue(repo, "a3", "Wei Lun", "how are you feeling", self.LATEST)

        items = notifications_for(repo, "ah_khim", self._members())
        asks = [n for n in items if n.kind is NotificationKind.ASKED_YOU]

        assert len(asks) == 3
        assert {n.from_name for n in asks} == {"Xin Yi", "Wei Lun"}

    def test_the_call_still_carries_only_the_oldest(self) -> None:
        repo = self._repo()
        self._queue(repo, "a1", "Xin Yi", "shop name?", self.EARLY)
        self._queue(repo, "a2", "Wei Lun", "how are you doing", self.LATE)

        waiting = repo.pending_ask("ah_khim")

        assert waiting is not None
        assert waiting.ask_id == "a1"

    def test_a_delivered_question_stops_ringing(self) -> None:
        from sampan.notifications import NotificationKind, notifications_for

        repo = self._repo()
        self._queue(repo, "a1", "Xin Yi", "shop name?", self.EARLY)
        self._queue(repo, "a2", "Wei Lun", "how are you doing", self.LATE)
        repo.mark_ask_delivered("ah_khim", "a1")

        items = notifications_for(repo, "ah_khim", self._members())
        asks = [n for n in items if n.kind is NotificationKind.ASKED_YOU]

        assert [n.target for n in asks] == ["a2"]

    def test_the_newest_question_is_on_top(self) -> None:
        from sampan.notifications import NotificationKind, notifications_for

        repo = self._repo()
        self._queue(repo, "old", "Xin Yi", "shop name?", self.EARLY)
        self._queue(repo, "new", "Wei Lun", "how are you feeling", self.LATEST)

        items = notifications_for(repo, "ah_khim", self._members())
        asks = [n for n in items if n.kind is NotificationKind.ASKED_YOU]

        # Unseen and equally urgent, so the tiebreak is recency -- and it was
        # sorting ascending while the comment above it claimed "then newest".
        assert [n.target for n in asks] == ["new", "old"]


class TestAnsweringTheOneShePicked:
    """The call must carry the question she tapped, not the oldest one.

    The bell, the recording screen and the voice agent all read the same
    queue. While that queue was strictly first-in-first-out, tapping "Wei Lun
    asked you something" started a call in which the agent asked a different
    question and said a different person's name out loud — the archive
    contradicting itself in her ear, which is worse than on a screen.
    """

    EARLY = "2026-08-17T01:00:00+00:00"
    LATE = "2026-08-18T23:22:00+00:00"

    @staticmethod
    def _repo():
        from sampan.repository import Repository
        from sampan.store import InMemoryDocumentStore

        return Repository(InMemoryDocumentStore())

    def _two(self, repo) -> None:
        from sampan.models import Ask

        repo.queue_ask(
            "ah_khim",
            Ask(
                ask_id="old",
                from_name="Xin Yi",
                question="shop name?",
                created_at=self.EARLY,
            ),
        )
        repo.queue_ask(
            "ah_khim",
            Ask(
                ask_id="new",
                from_name="Wei Lun",
                question="how are you?",
                created_at=self.LATE,
            ),
        )

    def test_the_oldest_leads_until_she_chooses(self) -> None:
        repo = self._repo()
        self._two(repo)

        waiting = repo.pending_ask("ah_khim")

        assert waiting is not None
        assert waiting.from_name == "Xin Yi"

    def test_choosing_puts_that_question_in_front(self) -> None:
        repo = self._repo()
        self._two(repo)

        assert repo.choose_ask("ah_khim", "new") is True
        waiting = repo.pending_ask("ah_khim")

        assert waiting is not None
        assert waiting.ask_id == "new"
        assert waiting.from_name == "Wei Lun"

    def test_choosing_again_moves_the_front_rather_than_adding_to_it(self) -> None:
        repo = self._repo()
        self._two(repo)

        repo.choose_ask("ah_khim", "new")
        repo.choose_ask("ah_khim", "old")
        waiting = repo.pending_ask("ah_khim")

        assert waiting is not None
        assert waiting.ask_id == "old"

    def test_answering_it_hands_the_front_back_to_the_queue(self) -> None:
        repo = self._repo()
        self._two(repo)
        repo.choose_ask("ah_khim", "new")

        repo.mark_ask_delivered("ah_khim", "new")
        waiting = repo.pending_ask("ah_khim")

        # Not still pinned to the answered one, and not empty either.
        assert waiting is not None
        assert waiting.ask_id == "old"

    def test_choosing_a_question_that_is_not_waiting_is_refused(self) -> None:
        repo = self._repo()
        self._two(repo)
        repo.mark_ask_delivered("ah_khim", "old")

        assert repo.choose_ask("ah_khim", "old") is False
        assert repo.choose_ask("ah_khim", "nonsense") is False

    def test_the_choice_survives_a_round_trip_through_the_store(self) -> None:
        from sampan.models import Ask

        repo = self._repo()
        self._two(repo)
        repo.choose_ask("ah_khim", "new")

        # Reading it back must still parse as an Ask: the bookkeeping fields
        # are stored beside the model, not on it.
        waiting = repo.pending_ask("ah_khim")

        assert isinstance(waiting, Ask)
        assert waiting.question == "how are you?"
