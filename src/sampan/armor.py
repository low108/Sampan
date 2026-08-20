"""Screening the transcript before any of it reaches the database.

    Transcript ──> Model Armor ──> de-identified text ──> save_conversation
                                                     └──> extraction, facts

One screen, before the first write, and the *screened* text is what everything
downstream sees. That last part is not a detail. `build_facts` refuses a fact
whose quote is not present in the transcript, so extracting from the original
while storing the redacted version would silently start refusing facts whose
quotes contain a redaction — the archive would lose exactly the sentences that
had something in them worth protecting.

The tension this sits in, stated plainly because it cannot be designed away:
the product's promise is that her words are the artefact, kept verbatim (O3),
and this deliberately alters them. That is the right trade only for identifiers
nobody wants in a database — an account number, an IC, a phone number — and it
would be the wrong trade for anything that carries meaning. Model Armor's SDP
filter is what draws that line, not this module.

Fail open, and loudly. If screening cannot run the plain transcript is stored
and the failure is logged and recorded on the conversation. This is the
opposite of the posture the service takes on a missing project or key (D2), and
the reason is what is being protected: there, failing closed protects the
archive from silent data loss; here, failing closed *causes* it. Losing an
eighty-year-old's account of her own life because a screening API had a bad
minute is a worse outcome than holding an unscreened transcript in a private
database for as long as it takes to notice the log line.

The failure is recorded on the conversation, so "which calls went through
unscreened" is a query rather than a guess (D24, superseded).
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pydantic import BaseModel, Field

from sampan.config import Settings

# The first logger in the service, and it earns its place: this is the one
# event where the system knowingly does the less safe thing, and it has to be
# findable in Cloud Logging afterwards.
log = logging.getLogger("sampan.armor")


class Finding(BaseModel):
    """One thing the screen objected to."""

    filter: str = Field(description="sdp | rai | prompt_injection | malicious_uri")
    detail: str = ""


class Screened(BaseModel):
    """The result of screening one transcript.

    `stored` is the whole question: false means nothing goes in the database,
    and the caller must not write the text anyway.
    """

    text: str = ""
    findings: list[Finding] = Field(default_factory=list)
    stored: bool = True
    reason: str = ""
    # True when the text was stored without ever being checked. Not the same
    # as "nothing was found", and the difference is the whole audit trail.
    unscreened: bool = False

    @property
    def redacted(self) -> bool:
        return any(f.filter == "sdp" for f in self.findings)


class Screen(Protocol):
    """Model Armor, behind a seam. Everything downstream of screening is
    exercisable without a network by passing a fake."""

    def sanitize(self, text: str) -> Screened: ...


class AllowAll:
    """No screening configured. Used when no template is set, and in tests
    that are about something else."""

    def sanitize(self, text: str) -> Screened:
        return Screened(text=text, stored=True)


class ModelArmorScreen:
    """The real thing: one `sanitizeUserPrompt` call against a template.

    The template carries the policy — which info types to de-identify, which
    responsible-AI categories to block — because that is a decision for whoever
    runs the deployment and not one to hard-code here.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def sanitize(self, text: str) -> Screened:
        from google.api_core.client_options import ClientOptions
        from google.cloud import modelarmor_v1 as ma

        location = self._settings.armor_location
        client = ma.ModelArmorClient(
            client_options=ClientOptions(
                api_endpoint=f"modelarmor.{location}.rep.googleapis.com"
            )
        )
        template = (
            f"projects/{self._settings.project_id}/locations/{location}"
            f"/templates/{self._settings.armor_template}"
        )
        response = client.sanitize_user_prompt(
            request=ma.SanitizeUserPromptRequest(
                name=template,
                user_prompt_data=ma.DataItem(text=text),
            )
        )
        return _read(response.sanitization_result, text)


def _read(result: Any, original: str) -> Screened:
    """Turn Model Armor's result into the two things the caller needs: the text
    to store, and whether it was actually checked.

    The second is not a formality. Model Armor answers 200 with
    `invocation_result: FAILURE` and `execution_state: EXECUTION_SKIPPED` when
    its service agent lacks permission on the DLP templates — no exception, no
    error field, just a filter that quietly did not run. Read naively that is
    indistinguishable from a clean transcript, which is the worst shape a
    security control can have: it reports success while protecting nothing.
    Observed, not hypothesised: it is what the first live call returned.
    """
    from google.cloud import modelarmor_v1 as ma

    findings: list[Finding] = []
    text = original
    skipped: list[str] = []

    if getattr(result, "invocation_result", None) == ma.InvocationResult.FAILURE:
        skipped.append("invocation failed")

    for name, filter_result in (result.filter_results or {}).items():
        sdp = getattr(filter_result, "sdp_filter_result", None)
        deidentified = getattr(sdp, "deidentify_result", None) if sdp else None

        if deidentified is not None:
            state = getattr(deidentified, "execution_state", None)
            if state == ma.FilterExecutionState.EXECUTION_SKIPPED:
                skipped.extend(
                    m.message for m in getattr(deidentified, "message_items", []) or []
                )
                continue
            if getattr(deidentified, "data", None):
                # The whole reason for the screen: identifiers replaced, and
                # the replacement is what gets stored and extracted from.
                replacement = getattr(deidentified.data, "text", "")
                if replacement:
                    text = replacement
                findings.append(
                    Finding(
                        filter="sdp",
                        # Strings on the wire, not objects with `.name`.
                        detail=", ".join(
                            str(getattr(i, "name", i))
                            for i in getattr(deidentified, "info_types", []) or []
                        ),
                    )
                )
                continue

        matched = getattr(filter_result, "match_state", None)
        if matched == ma.FilterMatchState.MATCH_FOUND:
            findings.append(Finding(filter=str(name)))

    if skipped:
        reason = "; ".join(skipped)[:500]
        log.error(
            "Model Armor reported success but the filter did not run; "
            "storing the transcript unscreened. %s",
            reason,
        )
        return Screened(
            text=original, findings=findings, stored=True, unscreened=True,
            reason=reason,
        )

    return Screened(text=text, findings=findings, stored=True)


def screen(text: str, screener: Screen | None) -> Screened:
    """Screen a transcript, or store it plainly and say so.

    Never raises. A screening failure returns the original text with
    `unscreened=True` and a reason, and logs at ERROR: the call survives, and
    the fact that it went through unchecked is on the record in two places.
    """
    if screener is None:
        return Screened(text=text, stored=True)
    try:
        return screener.sanitize(text)
    except Exception as error:  # noqa: BLE001 -- see the module docstring
        reason = f"{type(error).__name__}: {error}"
        log.error(
            "Model Armor screening failed; storing the transcript unscreened. %s",
            reason,
        )
        return Screened(text=text, stored=True, unscreened=True, reason=reason)


def build_screen(settings: Settings) -> Screen | None:
    """The screen this deployment should use, or None for no screening.

    None rather than a raise when unconfigured: a developer running against an
    in-memory store has nothing to protect, and making them provision a Model
    Armor template to see the app at all would be security theatre.
    """
    if not settings.configured or not settings.armor_template:
        return None
    return ModelArmorScreen(settings)
